@echo off
REM Database Backup Script
REM This script backs up the database and keeps the last 7 backups

cd /d "%~dp0"

echo ========================================
echo Starting Database Backup
echo ========================================
echo.

python manage.py backup_db --keep 7

echo.
echo ========================================
echo Backup completed!
echo ========================================
pause
