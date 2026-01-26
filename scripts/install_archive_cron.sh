#!/bin/bash
#
# Install Archive Cron Job
# This script sets up the cron job for automatic archiving
#
# Usage: sudo bash install_archive_cron.sh
#

set -e

echo "=========================================="
echo "WowDash Archive Cron Installation"
echo "=========================================="
echo ""

# Check if running as root or with sudo
if [ "$EUID" -ne 0 ]; then 
    echo "ERROR: Please run with sudo"
    echo "Usage: sudo bash install_archive_cron.sh"
    exit 1
fi

# Configuration
PROJECT_DIR="/home/wemard/app"
SCRIPT_PATH="${PROJECT_DIR}/scripts/archive_cron.sh"
CRON_USER="wemard"  # Change this to your application user

# Verify script exists
if [ ! -f "${SCRIPT_PATH}" ]; then
    echo "ERROR: Archive script not found: ${SCRIPT_PATH}"
    echo "Please ensure the script exists and the path is correct"
    exit 1
fi

# Make script executable
chmod +x "${SCRIPT_PATH}"
echo "✓ Made archive script executable"

# Create log directory with proper permissions
mkdir -p /var/log/wowdash
chown ${CRON_USER}:${CRON_USER} /var/log/wowdash
echo "✓ Created log directory: /var/log/wowdash"

# Backup existing crontab
BACKUP_FILE="/tmp/crontab_backup_$(date +%Y%m%d_%H%M%S).txt"
crontab -u ${CRON_USER} -l > "${BACKUP_FILE}" 2>/dev/null || echo "# New crontab" > "${BACKUP_FILE}"
echo "✓ Backed up existing crontab to: ${BACKUP_FILE}"

# Check if cron job already exists
if crontab -u ${CRON_USER} -l 2>/dev/null | grep -q "archive_cron.sh"; then
    echo ""
    echo "WARNING: Archive cron job already exists in crontab"
    echo "Please remove the old entry manually or it will run twice"
    echo ""
    read -p "Do you want to continue and add it anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Installation cancelled"
        exit 1
    fi
fi

# Add cron job (runs daily at 2 AM)
(crontab -u ${CRON_USER} -l 2>/dev/null; echo "# WowDash Archive - Runs daily at 2 AM") | crontab -u ${CRON_USER} -
(crontab -u ${CRON_USER} -l 2>/dev/null; echo "0 2 * * * ${SCRIPT_PATH}") | crontab -u ${CRON_USER} -

echo "✓ Added cron job to run daily at 2:00 AM"

# Display installed cron job
echo ""
echo "=========================================="
echo "Installed Cron Jobs:"
echo "=========================================="
crontab -u ${CRON_USER} -l | grep -A 1 "WowDash Archive" || echo "No archive cron jobs found"

echo ""
echo "=========================================="
echo "Installation Complete!"
echo "=========================================="
echo ""
echo "Configuration:"
echo "  - User: ${CRON_USER}"
echo "  - Script: ${SCRIPT_PATH}"
echo "  - Schedule: Daily at 2:00 AM"
echo "  - Logs: /var/log/wowdash/archive.log"
echo "  - Error logs: /var/log/wowdash/archive_error.log"
echo ""
echo "To verify the cron job:"
echo "  sudo crontab -u ${CRON_USER} -l"
echo ""
echo "To test manually:"
echo "  sudo -u ${CRON_USER} ${SCRIPT_PATH}"
echo ""
echo "To view logs:"
echo "  tail -f /var/log/wowdash/archive.log"
echo ""
echo "To remove the cron job:"
echo "  sudo crontab -u ${CRON_USER} -e"
echo "  (then delete the line containing 'archive_cron.sh')"
echo ""
