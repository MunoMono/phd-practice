# Database Backup System

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
./scripts/restore-database.sh backups/epistemic_drift_backup_YYYYMMDD_HHMMSS.sql.gz
```

## Directory Structure

```
ai-methods/
├── backups/                          # Backup files stored here
│   ├── epistemic_drift_backup_*.sql.gz
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
BACKUP_DIR=/Users/graham/Documents/repos/ai-methods/backups
LOG_DIR=/Users/graham/Documents/repos/ai-methods/logs
RETENTION_DAYS=30

# Database credentials (from .env or defaults)
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=epistemic_drift
CONTAINER_NAME=epistemic-drift-db

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
epistemic_drift_backup_YYYYMMDD_HHMMSS.sql.gz
```

Example: `epistemic_drift_backup_20251211_020000.sql.gz`

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
gunzip -t backups/epistemic_drift_backup_YYYYMMDD_HHMMSS.sql.gz
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
docker exec epistemic-drift-db pg_dump -U postgres epistemic_drift | gzip > emergency_backup_$(date +%Y%m%d_%H%M%S).sql.gz
```

## Troubleshooting

### Backup Failed - Container Not Running

```bash
# Start the database
docker-compose up -d db

# Verify container is running
docker ps | grep epistemic-drift-db
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
