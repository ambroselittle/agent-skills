#!/bin/bash
# Pre-loads deploy context for the SKILL.md prompt

case "$1" in
  auth-status)
    aws sts get-caller-identity 2>/dev/null || echo '{"error": "not authenticated"}'
    ;;

  dockerfiles)
    # Find Dockerfiles, exclude node_modules/.git, output as JSON array of relative paths
    find . -name "Dockerfile" \
      -not -path "*/node_modules/*" \
      -not -path "*/.git/*" \
      -not -path "*/dist/*" \
      2>/dev/null \
      | sort \
      | sed 's|^\./||' \
      | python3 -c "
import sys, json
files = [l.strip() for l in sys.stdin if l.strip()]
# Annotate with service name derived from path
services = []
for f in files:
    parts = f.split('/')
    # apps/api/Dockerfile -> api, apps/web/Dockerfile -> web, Dockerfile -> app
    if len(parts) >= 3 and parts[0] == 'apps':
        name = parts[1]
    elif len(parts) == 1:
        name = 'app'
    else:
        name = parts[-2]
    services.append({'name': name, 'dockerfile': f})
print(json.dumps(services, indent=2))
"
    ;;

  deploy-config)
    if [ -f .deploy-aws.json ]; then
      cat .deploy-aws.json
    else
      echo '{}'
    fi
    ;;

  template-type)
    python3 - <<'PYEOF'
import os, json

def detect():
    has_pkg = os.path.exists('package.json')
    has_pyproject = os.path.exists('pyproject.toml')
    has_apps_api = os.path.exists('apps/api')
    has_apps_web = os.path.exists('apps/web')

    if has_pkg and has_pyproject:
        return 'fullstack-python'
    if has_pyproject and not has_pkg:
        return 'api-python'
    if has_pkg:
        # Check for GraphQL markers
        if os.path.exists('apps/api/src/yoga.ts') or os.path.exists('apps/api/src/schema.ts'):
            return 'fullstack-graphql'
        if has_apps_api and has_apps_web:
            return 'fullstack-ts'
        if has_apps_api and not has_apps_web:
            return 'api-ts'
    return 'unknown'

print(detect())
PYEOF
    ;;

  *)
    echo "Usage: context.sh <auth-status|dockerfiles|deploy-config|template-type>" >&2
    exit 1
    ;;
esac
