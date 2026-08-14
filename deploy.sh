#!/bin/bash
set -euo pipefail

echo "ERROR: deploy.sh is intentionally disabled." >&2
echo "Use ./deploy-to-droplet.sh from your local git workspace so git stays the code source of truth and the droplet stays a deploy/runtime target." >&2
exit 1
