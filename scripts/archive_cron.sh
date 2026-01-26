#!/bin/bash
#
# WowDash Archive Cron Script
# Automatically archives completed orders and uploads to Telegram
#
# This script should be executed by cron periodically (e.g., daily at 2 AM)
#

# Exit on any error
set -e

# Configuration - UPDATE THESE PATHS FOR YOUR SERVER
PROJECT_DIR="/home/wemard/app"
VENV_PATH="/home/wemard/app/venv"
LOG_DIR="/var/log/wowdash"
LOG_FILE="${LOG_DIR}/archive.log"
ERROR_LOG="${LOG_DIR}/archive_error.log"

# Create log directory if it doesn't exist
mkdir -p "${LOG_DIR}"

# Function to log messages
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "${LOG_FILE}"
}

log_error() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $1" | tee -a "${ERROR_LOG}"
}

# Start logging
log_message "=========================================="
log_message "Starting archive process"
log_message "=========================================="

# Change to project directory
cd "${PROJECT_DIR}" || {
    log_error "Failed to change to project directory: ${PROJECT_DIR}"
    exit 1
}

# Activate virtual environment
if [ -f "${VENV_PATH}/bin/activate" ]; then
    source "${VENV_PATH}/bin/activate"
    log_message "Virtual environment activated: ${VENV_PATH}"
else
    log_error "Virtual environment not found: ${VENV_PATH}"
    exit 1
fi

# Check if Django is available
if ! python -c "import django" 2>/dev/null; then
    log_error "Django is not installed in the virtual environment"
    exit 1
fi

# Run archive command for all centers
log_message "Running archive command for all centers..."

if python manage.py archive --run --all >> "${LOG_FILE}" 2>> "${ERROR_LOG}"; then
    log_message "Archive process completed successfully"
    EXIT_CODE=0
else
    log_error "Archive process failed with exit code: $?"
    EXIT_CODE=1
fi

# Log completion
log_message "Archive process finished"
log_message "=========================================="
echo "" >> "${LOG_FILE}"

# Rotate logs if they get too large (keep last 10MB)
if [ -f "${LOG_FILE}" ]; then
    LOG_SIZE=$(stat -f%z "${LOG_FILE}" 2>/dev/null || stat -c%s "${LOG_FILE}" 2>/dev/null || echo 0)
    if [ "${LOG_SIZE}" -gt 10485760 ]; then  # 10MB
        log_message "Rotating log file (size: ${LOG_SIZE} bytes)"
        mv "${LOG_FILE}" "${LOG_FILE}.old"
        gzip "${LOG_FILE}.old"
        # Keep only last 5 rotated logs
        find "${LOG_DIR}" -name "archive.log.old.gz" -mtime +30 -delete
    fi
fi

exit ${EXIT_CODE}
