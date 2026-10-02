#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DROPLET_IP="104.248.170.26"
DROPLET_USER="root"
REMOTE_APP_DIR="/root/phd-practice"

files=(
  frontend/src/App.jsx
  frontend/src/main.jsx
  frontend/src/api/client.js
  frontend/src/api/viz.js
  frontend/src/utils/normalizers.js
  frontend/src/components/styles/pages/VisualAnalytics.scss
  frontend/src/pages/VisualAnalytics/VisualAnalyticsWorkbench.jsx
  frontend/src/pages/VisualAnalytics/VisualAnalytics.scss
  backend/app/api/routes/viz.py
  backend/app/models/research_outputs.py
  scripts/apply-db-migrations.sh
  scripts/migrations/20261002_01_visual_analytics_research_records.sql
  scripts/migrations/20261002_02_visual_annotations.sql
  scripts/migrations/20261002_03_visual_critical_probes.sql
  scripts/migrations/20261002_04_visual_annotation_ownership.sql
  scripts/migrations/20261002_05_visual_temporal_periods.sql
  scripts/migrations/20261002_06_aligned_umap_provenance.sql
  scripts/migrations/20261002_07_aligned_umap_slice_membership.sql
  scripts/migrations/20261002_08_reducer_checkpoint_compatibility.sql
)

cd "$SCRIPT_DIR"

git diff --check

for file in "${files[@]}"; do
  [[ -f "$file" ]] || { echo "Missing required deployment file: $file" >&2; exit 1; }
done

printf '%s\n' "${files[@]}" | rsync -avz --files-from=- --relative ./ "${DROPLET_USER}@${DROPLET_IP}:${REMOTE_APP_DIR}/"

ssh "${DROPLET_USER}@${DROPLET_IP}" <<'ENDSSH'
set -euo pipefail
cd /root/phd-practice

[[ -f .env ]] || { echo "Missing production .env; refusing deployment." >&2; exit 1; }
COMPOSE_FILE=docker-compose.prod.yml bash scripts/apply-db-migrations.sh
docker compose -f docker-compose.prod.yml build frontend backend
docker compose -f docker-compose.prod.yml up -d --no-deps --force-recreate frontend backend
docker compose -f docker-compose.prod.yml ps frontend backend
ENDSSH

echo "Surgical UMAP deployment complete. Only the listed Visual Analytics files were transferred."
