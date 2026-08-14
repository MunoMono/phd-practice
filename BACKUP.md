# Backup System

This repository now has two backup paths:

- `scripts/backup-database.sh`: the older database-only backup flow already in the repo.
- `scripts/backup-innovationdesign-full.sh`: the new full nightly backup flow for Innovation Design.

The new full backup mirrors the wealth-management production backup pattern for staged archives, checksum generation, Spaces upload, and restore documentation, while keeping the local repo's existing shell-script and cron setup conventions.

## Full Nightly Backup

The full backup script creates a nightly package containing:

- A PostgreSQL dump from the running database container.
- A compressed application/configuration archive of the repository, including `.env` and deployment files.
- Metadata and verification manifests.
- A top-level `.tar.gz` archive and matching `.sha256` checksum.
- Automatic remote pruning of older Spaces backups under the same `daily/` prefix.

### Files Mirrored For The New Flow

The implementation mirrors these existing patterns:

- `scripts/backup-database.sh`: local logging, container checks, retention cleanup.
- `scripts/setup-backup-cron.sh`: cron installation/update behavior.
- wealth-management `tools/production_backup/backup_production.sh`: staged full-backup packaging, checksum generation, Spaces upload layout, restore-oriented archive structure.
- wealth-management `tools/production_backup/backup-spaces.env.example`: isolated Spaces credential file pattern.

### Full Backup Schedule

Install the nightly 1:00 AM cron job with:

```bash
./scripts/setup-full-backup-cron.sh
```

The cron entry created is:

```bash
0 1 * * * cd /path/to/innovation-design && ./scripts/backup-innovationdesign-full.sh >> logs/full_backup_cron.log 2>&1
```

### Manual Test Command

Use this command for a local validation run without requiring Spaces credentials:

```bash
REQUIRE_UPLOAD=0 ./scripts/backup-innovationdesign-full.sh
```

For a production-equivalent run with Spaces upload enabled:

```bash
cp scripts/backup-full-spaces.env.example scripts/backup-full-spaces.env
./scripts/backup-innovationdesign-full.sh
```

### Spaces Upload Layout

By default, uploads go to:

```text
s3://archive-media/innovationdesign-backups/innovationdesign-full/daily/<backup-name>/
```

Each uploaded backup directory contains:

- `<backup-name>.tar.gz`
- `<backup-name>.tar.gz.sha256`
- `<backup-name>.verification.txt`

After a successful upload, the script also prunes older remote backup prefixes and keeps the most recent `REMOTE_RETENTION_COUNT` backups. The default is `14`.

### Required Environment

The full backup script automatically loads:

- `.env` from the project root, if present
- `scripts/backup-full-spaces.env`, if present

Create the Spaces env file from the example:

```bash
cp scripts/backup-full-spaces.env.example scripts/backup-full-spaces.env
```

Expected variables:

```bash
SPACES_BUCKET=archive-media
SPACES_PREFIX=innovationdesign-backups/innovationdesign-full
SPACES_ENDPOINT=https://lon1.digitaloceanspaces.com
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
```

If upload is enabled and the bucket/prefix/endpoint are missing, the script exits with a clear error. Credentials can come from environment variables or the standard AWS shared credentials file.

### Local Output

The full backup script writes to:

```text
backups/full/daily/
logs/full-backups/
logs/full_backup_cron.log
```

Naming convention:

```text
innovationdesign-full-YYYYMMDD_HHMMSS.tar.gz
innovationdesign-full-YYYYMMDD_HHMMSS.tar.gz.sha256
innovationdesign-full-YYYYMMDD_HHMMSS.verification.txt
```

Remote retention is count-based, not day-based:

```bash
REMOTE_RETENTION_COUNT=14
```

### Restore Notes

Use the dedicated full restore script:

```bash
./scripts/restore-innovationdesign-full.sh backups/full/daily/innovationdesign-full-YYYYMMDD_HHMMSS.tar.gz
```

For non-interactive disaster recovery runs:

```bash
./scripts/restore-innovationdesign-full.sh --yes backups/full/daily/innovationdesign-full-YYYYMMDD_HHMMSS.tar.gz
```

1. Verify the checksum:

```bash
shasum -a 256 -c backups/full/daily/innovationdesign-full-YYYYMMDD_HHMMSS.tar.gz.sha256
```

2. Extract the archive:

```bash
tar -xzf backups/full/daily/innovationdesign-full-YYYYMMDD_HHMMSS.tar.gz
```

3. Restore the database dump from the extracted backup directory:

```bash
gunzip -c innovationdesign-full-YYYYMMDD_HHMMSS/database.sql.gz | docker exec -i phd-practice-db psql -U postgres testamentary-traces
```

4. Restore application files as needed:

```bash
tar -xzf innovationdesign-full-YYYYMMDD_HHMMSS/application-files.tar.gz -C /restore/target/path
```

Adjust `DB_CONTAINER_NAME`, `POSTGRES_USER`, `POSTGRES_DB`, and restore target paths if your environment differs.

Useful restore flags:

```bash
SKIP_APP_RESTORE=1 ./scripts/restore-innovationdesign-full.sh <archive>
SKIP_DB_RESTORE=1 ./scripts/restore-innovationdesign-full.sh <archive>
RESTORE_TARGET_DIR=/restore/target/path ./scripts/restore-innovationdesign-full.sh <archive>
ASSUME_YES=1 ./scripts/restore-innovationdesign-full.sh <archive>
./scripts/restore-innovationdesign-full.sh --yes <archive>
```

### Backup Status Check

Use the status script to verify the latest local backup plus the latest remote Spaces backup prefix:

```bash
./scripts/check-full-backup-status.sh
```

The script writes a dated report to:

```text
logs/full-backups/full_backup_status_YYYY-MM-DD.log
```

If you want a local-only check, disable remote verification explicitly:

```bash
CHECK_REMOTE=0 ./scripts/check-full-backup-status.sh
```

If `MAIL_TO` is set and `mail` or `mailx` is installed, it also emails the same report:

```bash
MAIL_TO=ops@example.com ./scripts/check-full-backup-status.sh
```

## Database Backup System

**Mission-critical automated backup system for PhD research data**

## Overview

This backup system provides automated daily backups of your PostgreSQL database at 2:00 AM local time, with 30-day retention and optional S3 storage.

## Features

- ✅ **Automated daily backups** at 2:00 AM via cron
- ✅ **30-day retention policy** (configurable)
- ✅ **Compressed backups** using gzip
- ✅ **Timestamped filenames** for easy tracking
- ✅ **Comprehensive logging** of all operations
- ✅ **S3-compatible storage** support (MinIO/AWS S3)
- ✅ **Safe restore** with automatic pre-restore backups
- ✅ **Error handling** and validation

## Quick Start

### 1. Initial Setup

The cron job has already been configured to run daily at 2:00 AM:

```bash
# View current cron configuration
crontab -l
```

### 2. Manual Backup

To create a backup manually at any time:

```bash
./scripts/backup-database.sh
```

### 3. Restore from Backup

To restore from a backup file:

```bash
# List available backups
ls -lht backups/*.sql.gz

# Restore specific backup
./scripts/restore-database.sh backups/testamentary-traces_backup_YYYYMMDD_HHMMSS.sql.gz
```

## Directory Structure

```
phd-practice/
├── backups/                          # Backup files stored here
│   ├── testamentary-traces_backup_*.sql.gz
│   └── volume_info_*.json
├── logs/                             # Backup operation logs
│   ├── backup_YYYY-MM-DD.log
│   └── backup_cron.log
└── scripts/
    ├── backup-database.sh            # Main backup script
    ├── setup-backup-cron.sh          # Cron setup script
    └── restore-database.sh           # Database restore script
```

## Configuration

### Environment Variables

The backup script uses the following environment variables (with defaults):

```bash
# Backup configuration
BACKUP_DIR=/Users/graham/Documents/repos/phd-practice/backups
LOG_DIR=/Users/graham/Documents/repos/phd-practice/logs
RETENTION_DAYS=30

# Database credentials (from .env or defaults)
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=testamentary-traces
CONTAINER_NAME=phd-practice-db

# Optional S3 storage
S3_BUCKET=your-bucket-name
S3_ENDPOINT=https://s3.amazonaws.com
S3_ACCESS_KEY=your-access-key
S3_SECRET_KEY=your-secret-key
```

### Customize Retention Period

To change the retention period, edit the script or set the environment variable:

```bash
RETENTION_DAYS=60 ./scripts/backup-database.sh
```

### Modify Backup Schedule

To change the backup time, edit your crontab:

```bash
crontab -e
```

Current schedule: `0 2 * * *` (2:00 AM daily)

Examples:
- `0 3 * * *` - 3:00 AM daily
- `0 2 * * 0` - 2:00 AM on Sundays only
- `0 */6 * * *` - Every 6 hours

## Backup File Naming

Backups use the following naming convention:

```
testamentary-traces_backup_YYYYMMDD_HHMMSS.sql.gz
```

Example: `testamentary-traces_backup_20251211_020000.sql.gz`

## Logs

### Daily Backup Logs

Each backup creates a daily log file:

```bash
# View today's backup log
cat logs/backup_$(date +%Y-%m-%d).log

# Monitor backup in real-time
tail -f logs/backup_$(date +%Y-%m-%d).log
```

### Cron Execution Logs

Cron output is logged separately:

```bash
# View cron execution log
tail -f logs/backup_cron.log
```

## S3 Storage Integration

To enable automatic S3 uploads:

1. Set S3 environment variables in your `.env` file:

```bash
S3_BUCKET=my-phd-backups
S3_ENDPOINT=https://s3.amazonaws.com
S3_ACCESS_KEY=your-access-key
S3_SECRET_KEY=your-secret-key
```

2. Install AWS CLI (if not already installed):

```bash
brew install awscli
```

3. Configure AWS credentials:

```bash
aws configure
```

Backups will automatically upload to S3 after local backup completes.

## Monitoring & Verification

### Check Backup Status

```bash
# List all backups with sizes
ls -lht backups/*.sql.gz

# Count number of backups
ls backups/*.sql.gz | wc -l

# Check total backup size
du -sh backups/
```

### Verify Cron Job

```bash
# Check if cron job exists
crontab -l | grep backup-database

# View cron service status (macOS)
sudo launchctl list | grep cron
```

### Test Backup Integrity

```bash
# Verify a backup file can be decompressed
gunzip -t backups/testamentary-traces_backup_YYYYMMDD_HHMMSS.sql.gz
```

## Disaster Recovery

### Complete Database Restore

1. Stop the application:
```bash
docker-compose down
```

2. Restore from backup:
```bash
docker-compose up -d db
./scripts/restore-database.sh backups/your-backup-file.sql.gz
```

3. Restart application:
```bash
docker-compose up -d
```

### Emergency Manual Backup

If the automated backup fails:

```bash
# Direct PostgreSQL backup
docker exec phd-practice-db pg_dump -U postgres testamentary-traces | gzip > emergency_backup_$(date +%Y%m%d_%H%M%S).sql.gz
```

## Troubleshooting

### Backup Failed - Container Not Running

```bash
# Start the database
docker-compose up -d db

# Verify container is running
docker ps | grep phd-practice-db
```

### Permission Issues

```bash
# Make scripts executable
chmod +x scripts/*.sh

# Verify backup directory permissions
ls -la backups/
```

### Cron Not Running (macOS)

```bash
# Grant cron Full Disk Access in System Preferences > Security & Privacy
# Or check system logs
log show --predicate 'process == "cron"' --last 1h
```

### Disk Space Issues

```bash
# Check available space
df -h

# Reduce retention period
RETENTION_DAYS=7 ./scripts/backup-database.sh
```

## Best Practices

1. **Verify backups regularly** - Test restore at least monthly
2. **Monitor disk space** - Ensure sufficient space for retention period
3. **Keep off-site copies** - Enable S3 storage for redundancy
4. **Document recovery procedures** - Practice disaster recovery
5. **Alert on failures** - Check backup logs regularly

## Maintenance

### Update Cron Job

```bash
# Re-run setup script
./scripts/setup-backup-cron.sh
```

### Remove Old Backups Manually

```bash
# Delete backups older than 90 days
find backups/ -name "*.sql.gz" -mtime +90 -delete
```

### Backup the Backup Scripts

The backup scripts themselves are part of your git repository, but ensure they're committed:

```bash
git add scripts/backup-database.sh scripts/restore-database.sh scripts/setup-backup-cron.sh
git commit -m "Add database backup system"
```

## Support

For issues or questions:
1. Check the logs: `cat logs/backup_$(date +%Y-%m-%d).log`
2. Test manually: `./scripts/backup-database.sh`
3. Verify container status: `docker ps`

---

**Remember**: Your PhD research data is mission-critical. Always verify backups are running and test restore procedures regularly!
