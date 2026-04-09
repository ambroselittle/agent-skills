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
import time
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


def smoke_test(service: str, tag: str) -> None:
    """Run the container locally and verify the health endpoint responds.

    Uses native arch (fast on any machine). The API health endpoint doesn't
    touch the DB so a dummy DATABASE_URL is sufficient.
    API smoke test: GET /api/health → {"status":"ok"}
    Web smoke test: GET / → 200 (nginx serving static assets)
    """
    import urllib.request
    import urllib.error

    host_port = 3001 if service == "api" else 3080
    container_port = 3001 if service == "api" else 80
    health_url = (
        f"http://localhost:{host_port}/api/health"
        if service == "api"
        else f"http://localhost:{host_port}/"
    )
    env_args = ["-e", f"PORT={container_port}"]
    if service == "api":
        env_args += ["-e", "DATABASE_URL=postgresql://test:test@localhost:5432/test"]
        env_args += ["-e", "NODE_ENV=production"]

    print(f"\nSmoke testing '{service}' locally...")
    cid_result = subprocess.run(
        ["docker", "run", "-d", "--rm", "-p", f"{host_port}:{container_port}"] + env_args + [tag],
        capture_output=True, text=True
    )
    if cid_result.returncode != 0:
        print(f"  ERROR: container failed to start", file=sys.stderr)
        print(cid_result.stderr, file=sys.stderr)
        sys.exit(1)
    cid = cid_result.stdout.strip()

    try:
        for attempt in range(10):
            time.sleep(2)
            try:
                with urllib.request.urlopen(health_url, timeout=3) as resp:
                    if resp.status < 400:
                        print(f"  Smoke test passed ({resp.status} {health_url})")
                        return
            except (urllib.error.URLError, OSError):
                pass
        # Last attempt — show container logs before failing
        logs = subprocess.run(["docker", "logs", cid], capture_output=True, text=True)
        print(f"  ERROR: smoke test failed — container did not respond at {health_url}", file=sys.stderr)
        if logs.stdout or logs.stderr:
            print("  Container logs:", file=sys.stderr)
            print((logs.stdout + logs.stderr)[-1000:], file=sys.stderr)
        sys.exit(1)
    finally:
        subprocess.run(["docker", "stop", cid], capture_output=True)


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

    # Build locally first for smoke test, then push amd64 to ECR.
    # Local build uses native arch (fast, no emulation) — enough to verify startup.
    # Push step forces linux/amd64 for App Runner compatibility (critical on Apple Silicon).
    local_tag = f"{tag}-smoke"
    print("\nBuilding image locally for smoke test...")
    run(["docker", "build", "-f", dockerfile, "-t", local_tag, "."])

    smoke_test(service, local_tag)

    # Clean up local smoke image
    subprocess.run(["docker", "rmi", local_tag], capture_output=True)

    print("\nBuilding and pushing linux/amd64 image to ECR...")
    ecr_login(session, region, account_id)
    run([
        "docker", "buildx", "build",
        "--platform", "linux/amd64",
        "-f", dockerfile,
        "-t", tag,
        "--push",
        ".",
    ])

    # Fetch the digest from the registry (buildx --push writes directly, no local image).
    # Compute digest from the raw manifest — the --format template is unreliable across
    # Docker versions for multi-platform manifest lists.
    result = subprocess.run(
        ["docker", "buildx", "imagetools", "inspect", tag, "--raw"],
        capture_output=True,
    )
    if result.returncode == 0 and result.stdout:
        import hashlib
        digest = f"sha256:{hashlib.sha256(result.stdout).hexdigest()}"
        image_uri = f"{ecr_repo}@{digest}"
    else:
        image_uri = tag

    # Update config
    config["services"][service]["image_uri"] = image_uri
    config["services"][service]["dockerfile"] = dockerfile
    save_config(config)

    print(f"\n  Pushed: {image_uri}")
    print(f"  Updated .deploy-aws.json\n")


if __name__ == "__main__":
    main()
