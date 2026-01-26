# Archive Cron Setup Guide

This guide explains how to set up automatic archiving of completed orders on Ubuntu server.

## 📋 Overview

The archive system automatically:
- ✅ Finds completed orders older than 30 days (configurable)
- ✅ Creates ZIP archives organized by branch and order
- ✅ Includes Order IDs in all filenames for easy searching
- ✅ Uploads archives to center's Telegram channel
- ✅ Deletes local files to free up storage
- ✅ Tracks archives in database for recovery

## 🚀 Quick Setup (Production)

### 1. Update Configuration

Edit `scripts/archive_cron.sh` and update these paths:

```bash
PROJECT_DIR="/home/wemard/app"              # Your Django project directory
VENV_PATH="/home/wemard/app/venv"          # Your Python virtual environment
LOG_DIR="/var/log/wowdash"                 # Log directory
```

Edit `scripts/install_archive_cron.sh` and update:

```bash
CRON_USER="wemard"  # Your application user (NOT root)
```

### 2. Run Installation Script

```bash
# Navigate to your project
cd /home/wemard/app

# Make installation script executable
chmod +x scripts/install_archive_cron.sh

# Run installation (requires sudo)
sudo bash scripts/install_archive_cron.sh
```

### 3. Verify Installation

```bash
# Check if cron job is installed
sudo crontab -u wemard -l

# You should see:
# WowDash Archive - Runs daily at 2 AM
# 0 2 * * * /home/wemard/app/scripts/archive_cron.sh
```

### 4. Test Manually (Optional)

```bash
# Test the archive script manually before waiting for cron
sudo -u wemard /home/wemard/app/scripts/archive_cron.sh

# Or use dry-run to see what would be archived
cd /home/wemard/app
source venv/bin/activate
python manage.py archive --run --all --dry-run
```

## ⚙️ Configuration Options

### Change Archive Schedule

Edit crontab to change when archiving runs:

```bash
sudo crontab -u wemard -e
```

Examples:
```bash
# Daily at 2 AM (default)
0 2 * * * /home/wemard/app/scripts/archive_cron.sh

# Twice daily (2 AM and 2 PM)
0 2,14 * * * /home/wemard/app/scripts/archive_cron.sh

# Every 6 hours
0 */6 * * * /home/wemard/app/scripts/archive_cron.sh

# Weekly on Sundays at 3 AM
0 3 * * 0 /home/wemard/app/scripts/archive_cron.sh

# Monthly on 1st day at midnight
0 0 1 * * /home/wemard/app/scripts/archive_cron.sh
```

### Adjust Archive Settings

Edit `WowDash/archive_config.py` or add to `.env`:

```env
# Minimum age for archiving (days)
ARCHIVE_MIN_AGE_DAYS=30

# Minimum total size to trigger archiving (MB)
ARCHIVE_MIN_SIZE_MB=100

# Maximum archive size before splitting (MB)
ARCHIVE_MAX_SIZE_MB=1500

# Maximum orders per archive
ARCHIVE_MAX_ORDERS_PER_BATCH=500

# Compression level (0-9, higher = smaller but slower)
ARCHIVE_COMPRESSION_LEVEL=6

# Delete local files after archiving
ARCHIVE_DELETE_LOCAL_FILES=True
```

## 📊 Monitoring

### View Logs

```bash
# Watch live logs
tail -f /var/log/wowdash/archive.log

# View errors only
tail -f /var/log/wowdash/archive_error.log

# View recent activity
tail -n 100 /var/log/wowdash/archive.log

# Search logs for specific center
grep "Center: YourCenterName" /var/log/wowdash/archive.log
```

### Check Archive Status

```bash
# View archive configuration
cd /home/wemard/app
source venv/bin/activate
python manage.py archive --config

# Validate configuration
python manage.py archive --config --validate

# Check what would be archived (dry-run)
python manage.py archive --run --all --dry-run
```

## 🔧 Troubleshooting

### Cron Job Not Running

1. **Check cron service:**
   ```bash
   sudo systemctl status cron
   sudo systemctl restart cron
   ```

2. **Check user permissions:**
   ```bash
   # Script must be executable
   ls -l /home/wemard/app/scripts/archive_cron.sh
   
   # Should show: -rwxr-xr-x
   ```

3. **Test script manually:**
   ```bash
   sudo -u wemard /home/wemard/app/scripts/archive_cron.sh
   ```

4. **Check logs for errors:**
   ```bash
   cat /var/log/wowdash/archive_error.log
   ```

### Archive Not Creating

1. **No eligible orders:**
   - Orders must be `completed` status
   - Must be older than `MIN_AGE_DAYS` (default 30 days)
   - Must have files attached

2. **Below size threshold:**
   - Total size must exceed `MIN_SIZE_MB` (default 100MB)
   - Use `--force` flag to ignore size threshold

3. **Center not configured:**
   - Center must have `bot_token` set
   - Center must have `company_orders_channel_id` set

### Upload Failing

1. **Check bot token:**
   - Verify token is valid in center settings
   - Test bot manually in Telegram

2. **Check channel ID:**
   - Must be chat ID format (e.g., `-1001234567890`)
   - Bot must be admin in the channel

3. **File too large:**
   - Telegram limit is 2GB
   - Reduce `MAX_SIZE_MB` if hitting limits

## 🗑️ Uninstallation

```bash
# Remove cron job
sudo crontab -u wemard -e
# Delete the line containing 'archive_cron.sh'

# Or remove all cron jobs for user (careful!)
sudo crontab -u wemard -r

# Remove log files (optional)
sudo rm -rf /var/log/wowdash/archive*.log*
```

## 📞 Support

For issues or questions:
1. Check logs: `/var/log/wowdash/archive.log`
2. Run dry-run: `python manage.py archive --run --all --dry-run`
3. Validate config: `python manage.py archive --config --validate`
4. Test manually: `sudo -u wemard /home/wemard/app/scripts/archive_cron.sh`
