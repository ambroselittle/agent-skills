#!/usr/bin/env python3
"""
Build a Docker image and push it to ECR.
Reads .deploy-aws.json for the ECR repo URI.
Updates .deploy-aws.json with the pushed image URI.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

import boto3


def load_config() -> dict:
    p = Path(".deploy-aws.json")
    if not p.exists():
        print("ERROR: .deploy-aws.json not found. Run provision.py first.", file=sys.stderr)
        sys.exit(1)
    return json.loads(p.read_text())


def save_config(config: dict) -> None:
    Path(".deploy-aws.json").write_text(json.dumps(config, indent=2) + "\n")


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    print(f"  $ {' '.join(cmd)}")
    result = subprocess.run(cmd, **kwargs)
    if result.returncode != 0:
        print(f"ERROR: command failed (exit {result.returncode})", file=sys.stderr)
        sys.exit(result.returncode)
    return result


def find_dockerfile(service: str, config: dict) -> str:
    """Find the Dockerfile for a service. Checks config first, then common paths."""
    svc_config = config.get("services", {}).get(service, {})
    if "dockerfile" in svc_config:
        return svc_config["dockerfile"]
    candidates = [
        f"apps/{service}/Dockerfile",
        f"{service}/Dockerfile",
        "Dockerfile",
    ]
    for c in candidates:
        if Path(c).exists():
            return c
    print(f"ERROR: no Dockerfile found for service '{service}'", file=sys.stderr)
    print(f"  Tried: {candidates}", file=sys.stderr)
    sys.exit(1)


def ecr_login(session: boto3.Session, region: str, account_id: str) -> None:
    """Authenticate Docker to ECR."""
    ecr = session.client("ecr")
    token = ecr.get_authorization_token(registryIds=[account_id])
    import base64
    auth = token["authorizationData"][0]
    decoded = base64.b64decode(auth["authorizationToken"]).decode()
    username, password = decoded.split(":", 1)
    registry = auth["proxyEndpoint"]
    run(["docker", "login", "--username", username, "--password-stdin", registry],
        input=password.encode(), capture_output=True)
    print(f"  Logged in to ECR registry")


def main():
    parser = argparse.ArgumentParser(description="Build and push a service image to ECR")
    parser.add_argument("--service", required=True, help="Service name (e.g. api, web)")
    args = parser.parse_args()

    config = load_config()
    region = config["region"]
    account_id = config["account"]
    app = config["app"]
    service = args.service

    svc_config = config.get("services", {}).get(service)
    if not svc_config:
        print(f"ERROR: service '{service}' not found in .deploy-aws.json", file=sys.stderr)
        sys.exit(1)

    ecr_repo = svc_config["ecr_repo"]
    dockerfile = find_dockerfile(service, config)
    tag = f"{ecr_repo}:latest"

    print(f"\nBuilding and pushing '{service}'")
    print(f"  Dockerfile: {dockerfile}")
    print(f"  Target:     {tag}\n")

    session = boto3.Session(region_name=region)

    # ECR login
    ecr_login(session, region, account_id)

    # Build
    print("\nBuilding image...")
    run(["docker", "build", "-f", dockerfile, "-t", tag, "."])

    # Push
    print("\nPushing image...")
    run(["docker", "push", tag])

    # Get the image digest for pinning
    result = subprocess.run(
        ["docker", "inspect", "--format={{index .RepoDigests 0}}", tag],
        capture_output=True, text=True
    )
    image_uri = result.stdout.strip() if result.returncode == 0 and result.stdout.strip() else tag

    # Update config
    config["services"][service]["image_uri"] = image_uri
    config["services"][service]["dockerfile"] = dockerfile
    save_config(config)

    print(f"\n  Pushed: {image_uri}")
    print(f"  Updated .deploy-aws.json\n")


if __name__ == "__main__":
    main()
