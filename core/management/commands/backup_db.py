"""
Django management command to backup the database.

This command creates a backup of the database (PostgreSQL or SQLite)
with automatic compression and rotation of old backups.

Usage:
    python manage.py backup_db
    python manage.py backup_db --keep 7  # Keep last 7 backups
"""

import os
import gzip
import shutil
import subprocess
import hashlib
from datetime import datetime
from pathlib import Path
from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = 'Creates a backup of the database with automatic rotation'

    def add_arguments(self, parser):
        parser.add_argument(
            '--keep',
            type=int,
            default=30,
            help='Number of backups to keep (default: 30)'
        )
        parser.add_argument('--encrypt', action='store_true', help='Encrypt the compressed backup before retention')
        parser.add_argument('--upload-telegram', action='store_true', help='Upload encrypted backup parts to the platform backup channel')
        parser.add_argument(
            '--backup-dir',
            type=str,
            default=None,
            help='Custom backup directory path'
        )

    def handle(self, *args, **options):
        keep_backups = options['keep']
        custom_backup_dir = options['backup_dir']
        
        # Get database settings
        db_settings = settings.DATABASES['default']
        db_engine = db_settings['ENGINE']
        
        # Determine backup directory
        if custom_backup_dir:
            backup_dir = Path(custom_backup_dir)
        else:
            backup_dir = settings.BASE_DIR / 'backups' / 'database'
        
        # Create backup directory if it doesn't exist
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate backup filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        self.stdout.write(self.style.SUCCESS(f'Starting database backup...'))
        
        try:
            if 'postgresql' in db_engine:
                backup_path = self._backup_postgresql(db_settings, backup_dir, timestamp)
            elif 'sqlite3' in db_engine:
                backup_path = self._backup_sqlite(db_settings, backup_dir, timestamp)
            else:
                self.stdout.write(
                    self.style.ERROR(f'Unsupported database engine: {db_engine}')
                )
                return
            
            if options['encrypt']:
                backup_path = self._encrypt_backup(backup_path)
            if options['upload_telegram']:
                self._upload_to_telegram(backup_path)

            self._rotate_backups(backup_dir, keep_backups)
            
            self.stdout.write(
                self.style.SUCCESS(f'✓ Backup completed successfully!')
            )
            self.stdout.write(f'  Backup location: {backup_dir}')
            self.stdout.write(f'  Keeping last {keep_backups} backups')
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'✗ Backup failed: {str(e)}')
            )
            raise

    def _backup_postgresql(self, db_settings, backup_dir, timestamp):
        """Backup PostgreSQL database using pg_dump"""
        db_name = db_settings['NAME']
        db_user = db_settings['USER']
        db_password = db_settings['PASSWORD']
        db_host = db_settings['HOST']
        db_port = db_settings['PORT']
        
        backup_file = backup_dir / f'backup_postgres_{timestamp}.sql'
        compressed_file = backup_dir / f'backup_postgres_{timestamp}.sql.gz'
        
        self.stdout.write(f'Backing up PostgreSQL database: {db_name}')
        
        # Set environment variable for password
        env = os.environ.copy()
        env['PGPASSWORD'] = db_password
        
        # Run pg_dump
        cmd = [
            'pg_dump',
            '-h', db_host,
            '-p', str(db_port),
            '-U', db_user,
            '-F', 'p',  # Plain text format
            '-f', str(backup_file),
            db_name
        ]
        
        result = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            raise Exception(f'pg_dump failed: {result.stderr}')
        
        # Compress the backup
        self.stdout.write('Compressing backup...')
        with open(backup_file, 'rb') as f_in:
            with gzip.open(compressed_file, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        # Remove uncompressed file
        backup_file.unlink()
        
        file_size = compressed_file.stat().st_size / (1024 * 1024)
        self.stdout.write(f'Backup size: {file_size:.2f} MB')
        return compressed_file

    def _backup_sqlite(self, db_settings, backup_dir, timestamp):
        """Backup SQLite database"""
        db_path = Path(db_settings['NAME'])
        
        if not db_path.exists():
            raise Exception(f'Database file not found: {db_path}')
        
        backup_file = backup_dir / f'backup_sqlite_{timestamp}.db'
        compressed_file = backup_dir / f'backup_sqlite_{timestamp}.db.gz'
        
        self.stdout.write(f'Backing up SQLite database: {db_path.name}')
        
        # Copy the database file
        shutil.copy2(db_path, backup_file)
        
        # Compress the backup
        self.stdout.write('Compressing backup...')
        with open(backup_file, 'rb') as f_in:
            with gzip.open(compressed_file, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        # Remove uncompressed file
        backup_file.unlink()
        
        file_size = compressed_file.stat().st_size / (1024 * 1024)
        self.stdout.write(f'Backup size: {file_size:.2f} MB')
        return compressed_file

    def _encrypt_backup(self, backup_path):
        password = os.getenv('BACKUP_ENCRYPTION_PASSWORD', '')
        if not password:
            raise Exception('BACKUP_ENCRYPTION_PASSWORD is required for encrypted backups')
        encrypted_path = Path(f"{backup_path}.enc")
        env = os.environ.copy()
        env['WOWDASH_BACKUP_PASSWORD'] = password
        result = subprocess.run(
            [
                'openssl', 'enc', '-aes-256-cbc', '-salt', '-pbkdf2',
                '-in', str(backup_path), '-out', str(encrypted_path),
                '-pass', 'env:WOWDASH_BACKUP_PASSWORD',
            ],
            env=env,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise Exception(f'Backup encryption failed: {result.stderr}')
        backup_path.unlink()
        self.stdout.write(f'Encrypted backup: {encrypted_path.name}')
        return encrypted_path

    def _upload_to_telegram(self, backup_path):
        import telebot

        token = getattr(settings, 'SUPPORT_BOT_TOKEN', '')
        channel_id = os.getenv('PLATFORM_BACKUP_CHANNEL_ID', '')
        if not token or not channel_id:
            raise Exception('ADMIN_BOT_TOKEN and PLATFORM_BACKUP_CHANNEL_ID are required for backup upload')

        max_part_size = 45 * 1024 * 1024
        total_size = backup_path.stat().st_size
        total_parts = max(1, (total_size + max_part_size - 1) // max_part_size)
        digest = hashlib.sha256()
        with open(backup_path, 'rb') as backup_source:
            for chunk in iter(lambda: backup_source.read(1024 * 1024), b''):
                digest.update(chunk)
        checksum = digest.hexdigest()
        bot = telebot.TeleBot(token, parse_mode='HTML', threaded=False)
        part_paths = []
        try:
            with open(backup_path, 'rb') as source:
                for part_number in range(1, total_parts + 1):
                    part_path = Path(f"{backup_path}.part{part_number:03d}-of-{total_parts:03d}")
                    part_path.write_bytes(source.read(max_part_size))
                    part_paths.append(part_path)
                    with open(part_path, 'rb') as part_file:
                        bot.send_document(
                            channel_id,
                            part_file,
                            caption=(
                                f"🔐 Database backup {backup_path.name}\n"
                                f"Part {part_number}/{total_parts}\n"
                                f"SHA-256: <code>{checksum}</code>"
                            ),
                        )
        finally:
            for part_path in part_paths:
                part_path.unlink(missing_ok=True)
        self.stdout.write(f'Uploaded {total_parts} encrypted backup part(s) to Telegram')

    def _rotate_backups(self, backup_dir, keep_backups):
        """Remove old backups, keeping only the most recent ones"""
        # Get all backup files
        backup_files = sorted(
            list(backup_dir.glob('backup_*.gz')) + list(backup_dir.glob('backup_*.gz.enc')),
            key=lambda x: x.stat().st_mtime,
            reverse=True
        )
        
        # Remove old backups
        if len(backup_files) > keep_backups:
            self.stdout.write(f'Removing old backups...')
            for old_backup in backup_files[keep_backups:]:
                old_backup.unlink()
                self.stdout.write(f'  Removed: {old_backup.name}')
