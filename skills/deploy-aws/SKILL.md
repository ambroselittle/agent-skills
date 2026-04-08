---
name: deploy-aws
description: Deploy a project to AWS using App Runner (containers) + RDS (Postgres). Detects Dockerfiles, provisions infra, builds and pushes images, deploys services, and prints live URLs. Optimized for agent-skills templates but works on any repo with Dockerfiles.
argument-hint: "[update]"
---

# Deploy to AWS

You are a deployment assistant. Your job is to get this project running on AWS with minimal friction — provisioning infra, building images, deploying services, and handing back live URLs.

**Arguments:** $ARGUMENTS
- `update` — skip interview, re-deploy using existing `.deploy-aws.json` config

**Pre-loaded context:**

- AWS auth: !`~/.claude/skills/deploy-aws/scripts/context.sh auth-status`
- Dockerfiles found: !`~/.claude/skills/deploy-aws/scripts/context.sh dockerfiles`
- Existing deploy config: !`~/.claude/skills/deploy-aws/scripts/context.sh deploy-config`
- Repo template type: !`~/.claude/skills/deploy-aws/scripts/context.sh template-type`

---

## Step 0: Auth Check

If the AWS auth pre-loaded context shows an error or is empty:

> "AWS CLI isn't authenticated. Run `aws login` in your terminal (it opens a browser), then retry."

Stop here until auth is confirmed.

---

## Step 1: Assess State

If `$ARGUMENTS` includes `update` **and** `.deploy-aws.json` exists with a valid config:
- Skip the interview entirely
- Jump to Step 3 (build + push)

If `.deploy-aws.json` exists but `update` was not passed:
- Tell the user: "Found existing deploy config for `<app>` in `<region>`. This will update the running services. Proceed?"
- If yes: skip interview, jump to Step 3
- If no: proceed with interview (may overwrite config)

---

## Step 2: Interview

Use `AskUserQuestion` for every question. Batch independent questions in one call (max 4 per call).

**AskUserQuestion constraints:**
- `questions`: array of 1–4 question objects
- Each: `question` (string), `header` (max 12 chars), `options` (2–4 items), `multiSelect` (boolean)
- Each option: `label` (1–5 words), `description`
- Tool auto-adds "Other" for free text — don't add it yourself
- Put the most common/default first

### Batch 1 — App basics

Ask these together:

**Question 1 — App name:**
- header: `"App Name"`
- question: `"What should this deployment be called? (used for ECR repos, App Runner service names, and RDS identifier)"`
- options (always provide exactly 2):
  - label: derived from repo directory name (e.g. `"test-graphql"`), description: `"Derived from repo name — recommended"`
  - label: derived name + `-app` suffix (e.g. `"test-graphql-app"`), description: `"Alternate slug if the base name is taken in AWS"`

**Question 2 — AWS region:**
- header: `"Region"`
- question: `"Which AWS region?"`
- options:
  - `"us-east-1"` — US East (N. Virginia) — lowest latency to most US users, most services available
  - `"us-west-2"` — US West (Oregon) — good US West Coast latency
  - `"eu-west-1"` — EU (Ireland) — EU users

### Batch 2 — Services (only if 3+ Dockerfiles found)

**Default: deploy all services found.** Do not ask unless there are 3 or more Dockerfiles — at that point it's worth confirming the user doesn't want to skip any.

If 1–2 Dockerfiles found: skip this question, deploy all of them automatically.

If 3+ Dockerfiles found, ask one opt-out question:

**Question — Skip any services?:**
- header: `"Skip Any?"`
- question: `"Found N services (list them). Deploy all of them?"`
- options:
  - `"Deploy all"` — deploy everything found (default)
  - `"Skip some"` — I'll tell you which ones to leave out
- If they choose "Skip some": follow up asking which to exclude (free text or another question)

### Batch 3 — Database

**Question — Database:**
- header: `"Database"`
- question: `"Does this app need a Postgres database on RDS?"`
- options:
  - `"Yes, create RDS"` — Provision a free-tier RDS Postgres instance (db.t3.micro)
  - `"No database"` — Skip RDS (app uses an external DB or none)
  - `"Use existing"` — I'll provide a DATABASE_URL

If "Use existing": ask for the DATABASE_URL as free text.

### Confirm

Summarize the plan:
- App name, region
- Services to deploy (with Dockerfile paths)
- Database choice
- Estimated AWS costs (App Runner: ~$0–5/mo on free tier; RDS free tier: $0 for 12 months)

Ask: "Ready to deploy?" before proceeding.

---

## Step 3: Provision Infrastructure

Run the provision script. This is idempotent — safe to re-run.

```bash
uv run --project ~/.claude/skills/deploy-aws python ~/.claude/skills/deploy-aws/scripts/provision.py \
  --app <app-name> \
  --region <region> \
  --services <comma-separated service names, e.g. "api,web"> \
  --db <"rds"|"external:<DATABASE_URL>"|"none">
```

This creates:
- ECR repository for each service
- IAM role for App Runner to pull from ECR
- RDS Postgres instance + security group (if `--db rds`)

It saves state to `.deploy-aws.json` in the current directory and prints a summary.

If it fails: read the error, diagnose (common issues: region not enabled, service limits, insufficient permissions), fix or guide the user, then retry once.

---

## Step 4: Build and Push Images

For each service being deployed, build its Docker image and push to ECR.

```bash
uv run --project ~/.claude/skills/deploy-aws python ~/.claude/skills/deploy-aws/scripts/build-push.py \
  --service <service-name>
```

Run these **sequentially** — Docker builds are CPU/memory intensive. Show progress as each service builds.

If a build fails: show the last 20 lines of output, diagnose the error (missing files, wrong context path, etc.), and ask the user how to proceed.

---

## Step 5: Deploy Services

Deploy each service to App Runner. For fullstack apps, **always deploy API before web** (web needs the API's live URL for `API_HOST`).

```bash
uv run --project ~/.claude/skills/deploy-aws python ~/.claude/skills/deploy-aws/scripts/deploy.py \
  --service <service-name>
```

The script waits for the service to reach RUNNING state (polls every 10s, times out at 5 min).

If deploying web after api: the script automatically reads the API's live URL from `.deploy-aws.json` and sets `API_HOST` accordingly.

---

## Step 6: Done

Print a clean summary:

```
Deployed successfully!

Services:
  api  → https://<id>.us-east-1.awsapprunner.com
  web  → https://<id>.us-east-1.awsapprunner.com

Database: <endpoint>:5432/<db-name>  (RDS free tier — remember to delete when done)

Config saved to .deploy-aws.json — run /deploy-aws update to redeploy.
```

If any service URL is for the web app, open it: `open <url>`.

---

## Guidelines

- **Always provision before build** — ECR repos must exist before pushing images.
- **API before web** — web's `API_HOST` env var needs the API's live URL.
- **Idempotency** — all scripts are safe to re-run. Re-running provision won't duplicate resources.
- **Free tier** — remind the user to delete RDS when done if they don't need it long-term (`aws rds delete-db-instance --db-instance-identifier <id> --skip-final-snapshot`).
- **Secrets** — never log or print DATABASE_URL or passwords to the terminal. The scripts handle this.
