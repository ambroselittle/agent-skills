#!/usr/bin/env python3
"""
Tear down all AWS resources provisioned by deploy-aws.
Reads .deploy-aws.json from the current directory and deletes resources
in the correct order (App Runner → ECR → RDS → security group → IAM).
"""

import argparse
import json
import sys
import time
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

ECR_ACCESS_POLICY_ARN = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"


def load_config() -> dict:
    p = Path(".deploy-aws.json")
    if not p.exists():
        print("Error: .deploy-aws.json not found in the current directory.")
        print("Run this from the project root where you originally deployed from.")
        sys.exit(1)
    return json.loads(p.read_text())


# ── App Runner ────────────────────────────────────────────────────────────────


def delete_apprunner_service(apprunner, arn: str, name: str) -> None:
    print(f"  Deleting App Runner service: {name}")
    try:
        apprunner.delete_service(ServiceArn=arn)
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code in ("ResourceNotFoundException", "InvalidStateException"):
            # InvalidStateException can fire if already in DELETED state
            msg = e.response["Error"]["Message"]
            if "DELETED" in msg or "not found" in msg.lower():
                print(f"    Already deleted: {name}")
                return
        raise

    # App Runner has no delete waiter — poll manually
    print(f"    Waiting for {name} to be deleted (up to ~3 min)...")
    for attempt in range(20):
        time.sleep(10)
        try:
            resp = apprunner.describe_service(ServiceArn=arn)
            status = resp["Service"]["Status"]
            if status == "DELETED":
                print(f"    Deleted: {name}")
                return
            print(f"    Status: {status} (attempt {attempt + 1}/20)")
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                print(f"    Deleted: {name}")
                return
            raise

    print(f"  Warning: timed out waiting for {name} to delete — continuing anyway")


# ── ECR ──────────────────────────────────────────────────────────────────────


def parse_ecr_repo_name(uri: str) -> str:
    """Extract repo name from a full ECR URI.

    Example: 886511954473.dkr.ecr.us-east-1.amazonaws.com/test-graphql-api
             → test-graphql-api
    """
    return uri.split("/", 1)[-1]


def delete_ecr_repo(ecr, uri: str) -> None:
    repo_name = parse_ecr_repo_name(uri)
    print(f"  Deleting ECR repo: {repo_name}")
    try:
        ecr.delete_repository(repositoryName=repo_name, force=True)
        print(f"    Deleted: {repo_name}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "RepositoryNotFoundException":
            print(f"    Already deleted: {repo_name}")
        else:
            raise


# ── RDS ──────────────────────────────────────────────────────────────────────


def delete_rds_instance(rds, identifier: str) -> None:
    print(f"  Deleting RDS instance: {identifier}")
    try:
        rds.delete_db_instance(
            DBInstanceIdentifier=identifier,
            SkipFinalSnapshot=True,
            DeleteAutomatedBackups=True,
        )
    except ClientError as e:
        if e.response["Error"]["Code"] == "DBInstanceNotFound":
            print(f"    Already deleted: {identifier}")
            return
        raise

    print(f"    Waiting for {identifier} to be deleted (this can take 3-5 min)...")
    waiter = rds.get_waiter("db_instance_deleted")
    waiter.wait(
        DBInstanceIdentifier=identifier,
        WaiterConfig={"Delay": 15, "MaxAttempts": 40},
    )
    print(f"    Deleted: {identifier}")


def delete_security_group(ec2, sg_name: str) -> None:
    print(f"  Deleting security group: {sg_name}")
    try:
        sgs = ec2.describe_security_groups(
            Filters=[{"Name": "group-name", "Values": [sg_name]}]
        )["SecurityGroups"]
    except ClientError:
        raise

    if not sgs:
        print(f"    Already deleted: {sg_name}")
        return

    sg_id = sgs[0]["GroupId"]
    try:
        ec2.delete_security_group(GroupId=sg_id)
        print(f"    Deleted: {sg_name} ({sg_id})")
    except ClientError as e:
        if e.response["Error"]["Code"] == "InvalidGroup.NotFound":
            print(f"    Already deleted: {sg_name}")
        else:
            raise


# ── IAM ──────────────────────────────────────────────────────────────────────


def delete_iam_role(iam, role_arn: str) -> None:
    # Extract role name from ARN: arn:aws:iam::123:role/my-role-name
    role_name = role_arn.split("/")[-1]
    print(f"  Deleting IAM role: {role_name}")

    # Detach managed policies first
    try:
        attached = iam.list_attached_role_policies(RoleName=role_name)[
            "AttachedPolicies"
        ]
        for policy in attached:
            print(f"    Detaching policy: {policy['PolicyName']}")
            iam.detach_role_policy(RoleName=role_name, PolicyArn=policy["PolicyArn"])
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchEntity":
            print(f"    Already deleted: {role_name}")
            return
        raise

    try:
        iam.delete_role(RoleName=role_name)
        print(f"    Deleted: {role_name}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchEntity":
            print(f"    Already deleted: {role_name}")
        else:
            raise


# ── Main ─────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Tear down AWS resources provisioned by deploy-aws"
    )
    parser.add_argument(
        "--keep-config",
        action="store_true",
        help="Keep .deploy-aws.json after cleanup (default: delete it)",
    )
    args = parser.parse_args()

    config = load_config()
    app = config["app"]
    region = config["region"]
    services = config.get("services", {})
    database = config.get("database", {})
    iam_role_arn = config.get("iam_role_arn")

    session = boto3.Session(region_name=region)

    print(f"\nCleaning up AWS resources for '{app}' in {region}")
    print("=" * 55)

    # 1. App Runner services
    if services:
        print("\nApp Runner services:")
        apprunner = session.client("apprunner")
        for svc_name, svc_info in services.items():
            arn = svc_info.get("apprunner_arn")
            if arn:
                delete_apprunner_service(apprunner, arn, f"{app}-{svc_name}")
            else:
                print(f"  Skipping {svc_name} — no apprunner_arn in config")

    # 2. ECR repos
    if services:
        print("\nECR repositories:")
        ecr = session.client("ecr")
        for svc_name, svc_info in services.items():
            uri = svc_info.get("ecr_repo")
            if uri:
                delete_ecr_repo(ecr, uri)
            else:
                print(f"  Skipping {svc_name} — no ecr_repo in config")

    # 3. RDS instance (only if provisioned by us, not external)
    if database and database.get("identifier"):
        print("\nRDS instance:")
        rds = session.client("rds")
        delete_rds_instance(rds, database["identifier"])

        # 4. Security group (only after RDS is gone)
        print("\nSecurity group:")
        ec2 = session.client("ec2")
        delete_security_group(ec2, f"{app}-rds-sg")

    # 5. IAM role
    if iam_role_arn:
        print("\nIAM role:")
        iam = session.client("iam")
        delete_iam_role(iam, iam_role_arn)

    # 6. Config file
    if not args.keep_config:
        Path(".deploy-aws.json").unlink(missing_ok=True)
        print("\nDeleted .deploy-aws.json")
    else:
        print("\nKept .deploy-aws.json (--keep-config)")

    print("\n── Cleanup complete ────────────────────────────────")
    print(f"  All '{app}' resources removed from {region}\n")


if __name__ == "__main__":
    main()
