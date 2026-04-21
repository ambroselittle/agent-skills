#!/usr/bin/env python3
"""
Create or update an App Runner service for a given service.
Reads state from .deploy-aws.json and writes back the live URL.

Service ordering: always deploy API before web. The web service needs
the API's live URL to set API_HOST correctly.
"""

import argparse
import json
import sys
import time
from pathlib import Path

import boto3
from botocore.exceptions import ClientError


def load_config() -> dict:
    p = Path(".deploy-aws.json")
    if not p.exists():
        print("ERROR: .deploy-aws.json not found. Run provision.py first.", file=sys.stderr)
        sys.exit(1)
    return json.loads(p.read_text())


def save_config(config: dict) -> None:
    Path(".deploy-aws.json").write_text(json.dumps(config, indent=2) + "\n")


def service_name(app: str, service: str) -> str:
    return f"{app}-{service}"


def build_env_vars(service: str, config: dict) -> list[dict]:
    """Build environment variable list for the App Runner service."""
    env = []
    db = config.get("database")

    if service == "api":
        # PORT that the API listens on
        env.append({"name": "PORT", "value": "3001"})
        env.append({"name": "NODE_ENV", "value": "production"})
        if db and "url" in db:
            env.append({"name": "DATABASE_URL", "value": db["url"]})

    elif service == "web":
        # API_HOST: URL of the deployed API service (no trailing slash)
        api_url = config.get("services", {}).get("api", {}).get("url", "")
        if api_url:
            env.append({"name": "API_HOST", "value": api_url.rstrip("/")})
        else:
            print("  WARNING: API URL not found in config — API_HOST will not be set")

    return env


def find_or_create_service(
    apprunner, svc_name: str, image_uri: str, role_arn: str, port: int, env_vars: list[dict]
) -> tuple[str, str]:
    """Create or update App Runner service. Returns (service_arn, status)."""
    # Check if service exists
    try:
        resp = apprunner.list_services()
        for svc in resp.get("ServiceSummaryList", []):
            if svc["ServiceName"] == svc_name:
                arn = svc["ServiceArn"]
                status = svc.get("Status", "")
                print(f"  Service exists: {arn} (status: {status})")

                if status == "CREATE_FAILED":
                    # Delete the failed service and recreate fresh
                    print("  Service is in CREATE_FAILED — deleting before recreating...")
                    apprunner.delete_service(ServiceArn=arn)
                    # Poll until deleted
                    for _ in range(30):
                        time.sleep(10)
                        try:
                            apprunner.describe_service(ServiceArn=arn)
                        except ClientError as e:
                            if (
                                "ResourceNotFoundException" in str(e)
                                or "does not exist" in str(e).lower()
                            ):
                                break
                    print("  Deleted. Creating fresh service...")
                    break  # fall through to create

                # Update the existing service
                apprunner.update_service(
                    ServiceArn=arn,
                    SourceConfiguration={
                        "ImageRepository": {
                            "ImageIdentifier": image_uri,
                            "ImageRepositoryType": "ECR",
                            "ImageConfiguration": {
                                "Port": str(port),
                                "RuntimeEnvironmentVariables": {
                                    v["name"]: v["value"] for v in env_vars
                                },
                            },
                        },
                        "AuthenticationConfiguration": {"AccessRoleArn": role_arn},
                        "AutoDeploymentsEnabled": False,
                    },
                )
                print("  Triggered update")
                return arn, "UPDATING"
    except ClientError as e:
        print(f"  Warning: could not list services: {e}")

    # Create new service
    resp = apprunner.create_service(
        ServiceName=svc_name,
        SourceConfiguration={
            "ImageRepository": {
                "ImageIdentifier": image_uri,
                "ImageRepositoryType": "ECR",
                "ImageConfiguration": {
                    "Port": str(port),
                    "RuntimeEnvironmentVariables": {v["name"]: v["value"] for v in env_vars},
                },
            },
            "AuthenticationConfiguration": {"AccessRoleArn": role_arn},
            "AutoDeploymentsEnabled": False,
        },
        InstanceConfiguration={"Cpu": "0.25 vCPU", "Memory": "0.5 GB"},
    )
    arn = resp["Service"]["ServiceArn"]
    print(f"  Created service: {arn}")
    return arn, "CREATING"


def get_apprunner_events(apprunner, service_arn: str, max_lines: int = 10) -> list[str]:
    """Fetch recent App Runner service events for diagnostics."""
    try:
        resp = apprunner.list_operations(ServiceArn=service_arn)
        events = []
        for op in resp.get("OperationSummaryList", [])[:3]:
            events.append(
                f"  [{op.get('Status', '?')}] {op.get('Type', '?')} @ {op.get('StartedAt', '?')}"
            )
        return events
    except Exception:
        return []


def wait_for_running(apprunner, service_arn: str, timeout_s: int = 1200) -> str:
    """Poll until service reaches RUNNING. Returns the service URL.

    First deploys typically take 10-20 minutes on App Runner.
    Prints recent events log on timeout for diagnostics.
    """
    print(f"  Waiting for service to reach RUNNING state (timeout: {timeout_s // 60}m)...")
    deadline = time.time() + timeout_s
    last_status = None
    while time.time() < deadline:
        resp = apprunner.describe_service(ServiceArn=service_arn)
        svc = resp["Service"]
        status = svc["Status"]
        url = svc.get("ServiceUrl", "")
        if status != last_status:
            elapsed = int(time.time() - (deadline - timeout_s))
            print(f"    [{elapsed:3d}s] {status}")
            last_status = status
        if status == "RUNNING":
            return f"https://{url}"
        if status in ("CREATE_FAILED", "DELETE_FAILED"):
            print(f"ERROR: service entered {status} state", file=sys.stderr)
            events = get_apprunner_events(apprunner, service_arn)
            if events:
                print("Recent events:", file=sys.stderr)
                for e in events:
                    print(e, file=sys.stderr)
            sys.exit(1)
        time.sleep(10)

    print(f"ERROR: timed out after {timeout_s // 60}m waiting for RUNNING", file=sys.stderr)
    events = get_apprunner_events(apprunner, service_arn)
    if events:
        print("Recent events:", file=sys.stderr)
        for e in events:
            print(e, file=sys.stderr)
    sys.exit(1)


def verify_deployment(service: str, url: str) -> None:
    """Verify the deployment end-to-end — not just that the container is up.

    API checks:
      1. GET /api/health → {"status":"ok"} or "ok"
      2a. GraphQL: POST /api/graphql { users { email } } → alice + bob in seed data (DB check)
      2b. tRPC fallback: GET /api/trpc/user.list → alice + bob (if not GraphQL)

    Web checks:
      1. GET /api/health via nginx proxy (confirms nginx → API routing works)
      2. Playwright: load URL in headless browser, wait for "API status: ok" rendered text
         (confirms browser JS → API → DB full stack, not just proxy connectivity)
    """
    import json as _json
    import urllib.error
    import urllib.request

    print(f"\n  Verifying deployment at {url}...")

    def get(path: str, label: str):
        try:
            with urllib.request.urlopen(f"{url}{path}", timeout=10) as resp:
                body = resp.read().decode()
                print(f"  ✓ {label} ({resp.status})")
                return True, body
        except urllib.error.HTTPError as e:
            print(f"  ✗ {label} (HTTP {e.code})", file=sys.stderr)
            return False, ""
        except Exception as e:
            print(f"  ✗ {label} ({e})", file=sys.stderr)
            return False, ""

    def graphql(query: str, label: str):
        try:
            data = _json.dumps({"query": query}).encode()
            req = urllib.request.Request(
                f"{url}/api/graphql",
                data=data,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                return _json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None  # not a GraphQL service
            print(f"  ✗ {label} (HTTP {e.code})", file=sys.stderr)
            return {}
        except Exception as e:
            print(f"  ✗ {label} ({e})", file=sys.stderr)
            return {}

    if service == "api":
        # 1. Health endpoint
        ok, body = get("/api/health", "GET /api/health")
        if ok and '"ok"' not in body and "'ok'" not in body and "ok" not in body.lower():
            print(f"  ✗ Health response unexpected: {body[:100]}", file=sys.stderr)

        # 2. Seed data check — confirms API → DB connectivity with real data
        result = graphql("{ users { email } }", "GraphQL users query")
        if result is None:
            # Not a GraphQL service — try tRPC
            try:
                ok, body = get(
                    "/api/trpc/user.list?input=%7B%22json%22%3Anull%7D", "tRPC user.list"
                )
                if ok:
                    data = _json.loads(body)
                    emails = [
                        u.get("email", "")
                        for u in (data.get("result", {}).get("data", {}).get("json") or [])
                    ]
                    if "alice@example.com" in emails and "bob@example.com" in emails:
                        print("  ✓ Seed data present (alice, bob)")
                    else:
                        print(f"  ✗ Seed data missing — got: {emails[:5]}", file=sys.stderr)
            except Exception as e:
                print(f"  ~ Data check skipped: {e}")
        elif result:
            users = result.get("data", {}).get("users", [])
            emails = [u.get("email", "") for u in users]
            if "alice@example.com" in emails and "bob@example.com" in emails:
                print("  ✓ Seed data present (alice, bob) via GraphQL")
            else:
                print(f"  ✗ Seed data missing — got: {emails[:5]}", file=sys.stderr)

    elif service == "web":
        # 1. Proxy check — confirms nginx routes /api/ to the API service
        get("/api/health", "GET /api/health (via nginx proxy)")

        # 2. Playwright — load the real page, confirm the React app renders API data
        print("  Launching headless browser to verify rendered UI...")
        try:
            from playwright.sync_api import Error as PlaywrightError
            from playwright.sync_api import sync_playwright

            with sync_playwright() as pw:
                # Install chromium if missing (first run after deploy-aws env setup)
                try:
                    browser = pw.chromium.launch(headless=True)
                except Exception:
                    import subprocess

                    print("  Installing Chromium (first run)...")
                    subprocess.run(
                        ["python", "-m", "playwright", "install", "chromium"],
                        capture_output=True,
                    )
                    browser = pw.chromium.launch(headless=True)

                page = browser.new_page()
                page.goto(url, timeout=30000)
                try:
                    # Both fullstack-ts (tRPC) and fullstack-graphql show this
                    # text when API is reachable
                    page.wait_for_selector("text=API status: ok", timeout=20000)
                    print("  ✓ Browser rendered 'API status: ok' (web → API → DB confirmed)")
                except PlaywrightError:
                    content = page.content()
                    # Look for error state
                    if "API status: error" in content:
                        print(
                            "  ✗ Browser shows 'API status: error' — web cannot reach API",
                            file=sys.stderr,
                        )
                    elif "API status: loading" in content:
                        print(
                            "  ✗ Browser stuck on 'loading...' — API call timed out",
                            file=sys.stderr,
                        )
                    else:
                        print(
                            "  ✗ Expected 'API status: ok' not found in rendered page",
                            file=sys.stderr,
                        )
                finally:
                    browser.close()
        except ImportError:
            print(
                "  ~ Playwright not installed — skipping browser check"
                " (run: uv sync in skills/deploy-aws)"
            )


def main():
    parser = argparse.ArgumentParser(description="Deploy a service to App Runner")
    parser.add_argument("--service", required=True, help="Service name (e.g. api, web)")
    args = parser.parse_args()

    config = load_config()
    region = config["region"]
    app = config["app"]
    service = args.service

    svc_config = config.get("services", {}).get(service)
    if not svc_config:
        print(f"ERROR: service '{service}' not in .deploy-aws.json", file=sys.stderr)
        sys.exit(1)

    image_uri = svc_config.get("image_uri")
    if not image_uri:
        print(f"ERROR: no image_uri for '{service}' — run build-push.py first", file=sys.stderr)
        sys.exit(1)

    role_arn = config.get("iam_role_arn")
    if not role_arn:
        print(
            "ERROR: iam_role_arn not in .deploy-aws.json — run provision.py first", file=sys.stderr
        )
        sys.exit(1)

    # Port: api runs on 3001, web nginx on 80
    port = 3001 if service == "api" else 80

    env_vars = build_env_vars(service, config)
    svc_name = service_name(app, service)

    print(f"\nDeploying '{service}' to App Runner")
    print(f"  Service name: {svc_name}")
    print(f"  Image: {image_uri}")
    if env_vars:
        for v in env_vars:
            display = "***" if v["name"] in ("DATABASE_URL",) else v["value"]
            print(f"  Env: {v['name']}={display}")
    print()

    session = boto3.Session(region_name=region)
    apprunner = session.client("apprunner")

    service_arn, _ = find_or_create_service(
        apprunner, svc_name, image_uri, role_arn, port, env_vars
    )

    url = wait_for_running(apprunner, service_arn)

    verify_deployment(service, url)

    # Save URL and ARN to config
    config["services"][service]["url"] = url
    config["services"][service]["apprunner_arn"] = service_arn
    save_config(config)

    print(f"\n  Live: {url}\n")


if __name__ == "__main__":
    main()
