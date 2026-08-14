#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "${SCRIPT_DIR}")"
BACKUP_SCRIPT="${SCRIPT_DIR}/backup-innovationdesign-full.sh"
CRON_LOG="${PROJECT_DIR}/logs/full_backup_cron.log"
CRON_ENTRY="0 1 * * * cd ${PROJECT_DIR} && ${BACKUP_SCRIPT} >> ${CRON_LOG} 2>&1"
CURRENT_CRONTAB="$(crontab -l 2>/dev/null || true)"
FILTERED_CRONTAB="$(printf '%s\n' "${CURRENT_CRONTAB}" | grep -Fv "${BACKUP_SCRIPT}" || true)"
UPDATED_CRONTAB="$(printf '%s\n%s\n' "${FILTERED_CRONTAB}" "${CRON_ENTRY}" | awk 'NF && !seen[$0]++')"

echo "Setting up Innovation Design full backup cron job at 1:00 AM..."

chmod +x "${BACKUP_SCRIPT}"
mkdir -p "${PROJECT_DIR}/backups/full/daily" "${PROJECT_DIR}/logs"

if crontab -l 2>/dev/null | grep -Fq "${BACKUP_SCRIPT}"; then
    echo "Cron job already exists. Updating entry..."
else
    echo "Adding new cron job..."
fi

printf '%s\n' "${UPDATED_CRONTAB}" | crontab -

echo
echo "Full backup cron configured successfully."
echo "Schedule: 0 1 * * *"
echo "Script: ${BACKUP_SCRIPT}"
echo "Cron log: ${CRON_LOG}"
echo
echo "Current active crontab entries:"
crontab -l | grep -v '^#' | grep -v '^$' || echo "(no active cron jobs)"