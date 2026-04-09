#!/usr/bin/env python3
"""
Idempotent AWS infrastructure provisioner for deploy-aws skill.
Creates ECR repos, IAM role, and optionally RDS instance.
Saves state to .deploy-aws.json in the current directory.
"""

import argparse
import json
import os
import random
import string
import sys
import time
from pathlib import Path

import boto3
from botocore.exceptions import ClientError


def load_config() -> dict:
    p = Path(".deploy-aws.json")
    if p.exists():
        return json.loads(p.read_text())
    return {}


def save_config(config: dict) -> None:
    Path(".deploy-aws.json").write_text(json.dumps(config, indent=2) + "\n")
    print("  Saved .deploy-aws.json")


def get_account_id(session: boto3.Session) -> str:
    return session.client("sts").get_caller_identity()["Account"]


# ── ECR ──────────────────────────────────────────────────────────────────────


def ensure_ecr_repo(ecr, app: str, service: str) -> str:
    """Create ECR repo if it doesn't exist. Returns the repo URI."""
    name = f"{app}-{service}"
    try:
        resp = ecr.describe_repositories(repositoryNames=[name])
        uri = resp["repositories"][0]["repositoryUri"]
        print(f"  ECR repo already exists: {uri}")
        return uri
    except ClientError as e:
        if e.response["Error"]["Code"] != "RepositoryNotFoundException":
            raise
    resp = ecr.create_repository(
        repositoryName=name,
        imageScanningConfiguration={"scanOnPush": True},
        imageTagMutability="MUTABLE",
    )
    uri = resp["repository"]["repositoryUri"]
    print(f"  Created ECR repo: {uri}")
    return uri


# ── IAM ──────────────────────────────────────────────────────────────────────

APPRUNNER_TRUST_POLICY = json.dumps({
    "Version": "2012-10-17",
    "Statement": [{
        "Effect": "Allow",
        "Principal": {"Service": "build.apprunner.amazonaws.com"},
        "Action": "sts:AssumeRole",
    }],
})

ECR_ACCESS_POLICY_ARN = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"


def ensure_apprunner_role(iam, app: str) -> str:
    """Create App Runner ECR access role if it doesn't exist. Returns the role ARN."""
    role_name = f"{app}-apprunner-ecr-role"
    try:
        resp = iam.get_role(RoleName=role_name)
        arn = resp["Role"]["Arn"]
        print(f"  IAM role already exists: {arn}")
        return arn
    except ClientError as e:
        if e.response["Error"]["Code"] != "NoSuchEntity":
            raise
    resp = iam.create_role(
        RoleName=role_name,
        AssumeRolePolicyDocument=APPRUNNER_TRUST_POLICY,
        Description=f"App Runner ECR pull role for {app}",
    )
    iam.attach_role_policy(RoleName=role_name, PolicyArn=ECR_ACCESS_POLICY_ARN)
    arn = resp["Role"]["Arn"]
    print(f"  Created IAM role: {arn}")
    # IAM propagation delay
    time.sleep(10)
    return arn


# ── RDS ──────────────────────────────────────────────────────────────────────


def gen_password(length: int = 24) -> str:
    chars = string.ascii_letters + string.digits
    return "".join(random.SystemRandom().choice(chars) for _ in range(length))


def ensure_rds_security_group(ec2, app: str) -> str:
    """Create a security group that allows Postgres from anywhere (App Runner uses NAT IPs).
    Returns the SG id."""
    sg_name = f"{app}-rds-sg"
    sgs = ec2.describe_security_groups(
        Filters=[{"Name": "group-name", "Values": [sg_name]}]
    )["SecurityGroups"]
    if sgs:
        sg_id = sgs[0]["GroupId"]
        print(f"  Security group already exists: {sg_id}")
        return sg_id
    sg = ec2.create_security_group(
        GroupName=sg_name,
        Description=f"RDS access for {app} App Runner services",
    )
    sg_id = sg["GroupId"]
    ec2.authorize_security_group_ingress(
        GroupId=sg_id,
        IpPermissions=[{
            "IpProtocol": "tcp",
            "FromPort": 5432,
            "ToPort": 5432,
            "IpRanges": [{"CidrIp": "0.0.0.0/0", "Description": "App Runner egress IPs (dynamic)"}],
        }],
    )
    print(f"  Created security group: {sg_id}")
    return sg_id


def ensure_rds_instance(rds, ec2, app: str, existing_password: str | None) -> dict:
    """Create free-tier RDS Postgres instance. Returns db info dict."""
    identifier = f"{app}-db"
    db_name = app.replace("-", "_")
    password = existing_password or gen_password()

    try:
        resp = rds.describe_db_instances(DBInstanceIdentifier=identifier)
        db = resp["DBInstances"][0]
        endpoint = db.get("Endpoint", {})
        if endpoint:
            host = endpoint["Address"]
            port = endpoint["Port"]
            print(f"  RDS instance already exists: {host}:{port}")
            return {
                "identifier": identifier,
                "endpoint": host,
                "port": port,
                "name": db_name,
                "username": "postgres",
                "password": password,  # may differ from actual if not first run
            }
        else:
            print(f"  RDS instance exists but not yet available, waiting...")
    except ClientError as e:
        if e.response["Error"]["Code"] != "DBInstanceNotFound":
            raise

    sg_id = ensure_rds_security_group(ec2, app)

    rds.create_db_instance(
        DBInstanceIdentifier=identifier,
        DBName=db_name,
        DBInstanceClass="db.t3.micro",
        Engine="postgres",
        EngineVersion="16",
        MasterUsername="postgres",
        MasterUserPassword=password,
        AllocatedStorage=20,
        StorageType="gp2",
        PubliclyAccessible=True,
        VpcSecurityGroupIds=[sg_id],
        BackupRetentionPeriod=1,
        MultiAZ=False,
        Tags=[{"Key": "app", "Value": app}],
    )
    print(f"  Created RDS instance {identifier} (free tier: db.t3.micro, 20GB)")
    print("  Waiting for RDS to become available (this takes 3-5 minutes)...")

    waiter = rds.get_waiter("db_instance_available")
    waiter.wait(
        DBInstanceIdentifier=identifier,
        WaiterConfig={"Delay": 15, "MaxAttempts": 40},
    )

    resp = rds.describe_db_instances(DBInstanceIdentifier=identifier)
    db = resp["DBInstances"][0]
    endpoint = db["Endpoint"]
    host = endpoint["Address"]
    port = endpoint["Port"]
    print(f"  RDS ready: {host}:{port}")

    return {
        "identifier": identifier,
        "endpoint": host,
        "port": port,
        "name": db_name,
        "username": "postgres",
        "password": password,
    }


# ── DB Migration ─────────────────────────────────────────────────────────────


def _run_db_migrate(db_url: str) -> None:
    """Run prisma db push and db:seed from the repo root using the production DATABASE_URL.

    Uses pnpm workspace filter to target the db package. Seed uses upsert so it's
    safe to re-run on every deploy — idempotent by design.
    """
    import subprocess as sp
    import os

    env = {**os.environ, "DATABASE_URL": db_url}

    print("\nDatabase migration:")
    print("  Running db:push...")
    result = sp.run(
        ["pnpm", "--filter", "**/db", "db:push", "--accept-data-loss"],
        env=env, capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"  WARNING: db:push failed (exit {result.returncode})", file=sys.stderr)
        print(result.stderr[-500:] if result.stderr else "(no output)", file=sys.stderr)
    else:
        print("  db:push: done")

    print("  Running db:seed...")
    result = sp.run(
        ["pnpm", "--filter", "**/db", "db:seed"],
        env=env, capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"  WARNING: db:seed failed (exit {result.returncode})", file=sys.stderr)
        print(result.stderr[-500:] if result.stderr else "(no output)", file=sys.stderr)
    else:
        print("  db:seed: done")


# ── Main ─────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Provision AWS infra for deployment")
    parser.add_argument("--app", required=True, help="App name (used for resource naming)")
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--services", required=True, help="Comma-separated service names, e.g. api,web")
    parser.add_argument("--db", default="none", help="'rds', 'none', or 'external:<DATABASE_URL>'")
    parser.add_argument("--skip-migrate", action="store_true", help="Skip db:push and db:seed after RDS provisioning")
    args = parser.parse_args()

    services = [s.strip() for s in args.services.split(",")]
    session = boto3.Session(region_name=args.region)
    account_id = get_account_id(session)

    config = load_config()
    config.setdefault("app", args.app)
    config.setdefault("region", args.region)
    config["account"] = account_id
    config.setdefault("services", {})

    print(f"\nProvisioning infrastructure for '{args.app}' in {args.region}")
    print(f"Account: {account_id}\n")

    # ECR repos
    ecr = session.client("ecr")
    print("ECR repositories:")
    for service in services:
        uri = ensure_ecr_repo(ecr, args.app, service)
        config["services"].setdefault(service, {})
        config["services"][service]["ecr_repo"] = uri

    # IAM role
    print("\nIAM role:")
    iam = session.client("iam")
    role_arn = ensure_apprunner_role(iam, args.app)
    config["iam_role_arn"] = role_arn

    # Database
    if args.db == "rds":
        print("\nRDS Postgres:")
        rds = session.client("rds")
        ec2 = session.client("ec2")
        existing_password = config.get("database", {}).get("password")
        db_info = ensure_rds_instance(rds, ec2, args.app, existing_password)
        config["database"] = db_info
        # sslmode=no-verify: RDS requires SSL but the Prisma pg adapter doesn't
        # enable it by default, and sslmode=require triggers full cert verification
        # (no CA cert in container). no-verify encrypts without cert chain check.
        db_url = (
            f"postgresql://{db_info['username']}:{db_info['password']}"
            f"@{db_info['endpoint']}:{db_info['port']}/{db_info['name']}"
            f"?sslmode=no-verify"
        )
        config["database"]["url"] = db_url
    elif args.db.startswith("external:"):
        db_url = args.db[len("external:"):]
        config["database"] = {"url": db_url, "source": "external"}
        print(f"\nDatabase: using external URL")
    else:
        print("\nDatabase: none")
        config.pop("database", None)

    save_config(config)

    # Run db migrations + seed after RDS is up
    if "database" in config and "url" in config["database"] and not args.skip_migrate:
        _run_db_migrate(config["database"]["url"])

    print("\n── Provision complete ──────────────────────────────")
    for service in services:
        print(f"  {service}: {config['services'][service]['ecr_repo']}")
    if "database" in config and "endpoint" in config["database"]:
        db = config["database"]
        print(f"  db: {db['endpoint']}:{db['port']}/{db['name']}")
    print()


if __name__ == "__main__":
    main()
