"""
Management command to fix OrderMedia records with corrupted file paths.
Cleans up file paths that contain Telegram file IDs or are otherwise invalid.
"""
from django.core.management.base import BaseCommand
from django.core.files.storage import default_storage
from orders.models import OrderMedia
import os
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Fix OrderMedia records with corrupted file paths'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be fixed without making changes',
        )
        parser.add_argument(
            '--delete-missing',
            action='store_true',
            help='Delete OrderMedia records where files are missing',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        delete_missing = options['delete_missing']
        
        self.stdout.write('Scanning OrderMedia records...')
        
        all_media = OrderMedia.objects.all()
        total = all_media.count()
        
        corrupted = []
        missing = []
        valid = []
        
        for media in all_media:
            file_path = str(media.file) if media.file else ""
            
            # Check if path looks corrupted (contains Telegram file_id pattern)
            if 'AgAC' in file_path or 'BAAC' in file_path or len(os.path.basename(file_path)) > 150:
                corrupted.append(media)
                self.stdout.write(
                    self.style.WARNING(
                        f'Corrupted path: OrderMedia #{media.id} - {file_path[:100]}'
                    )
                )
            # Check if file exists
            elif file_path and not default_storage.exists(file_path):
                missing.append(media)
                self.stdout.write(
                    self.style.ERROR(
                        f'Missing file: OrderMedia #{media.id} - {file_path}'
                    )
                )
            else:
                valid.append(media)
        
        self.stdout.write('\n' + '='*60)
        self.stdout.write(f'Total OrderMedia records: {total}')
        self.stdout.write(self.style.SUCCESS(f'Valid records: {len(valid)}'))
        self.stdout.write(self.style.WARNING(f'Corrupted paths: {len(corrupted)}'))
        self.stdout.write(self.style.ERROR(f'Missing files: {len(missing)}'))
        self.stdout.write('='*60 + '\n')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - No changes made'))
            return
        
        # Fix corrupted records by clearing the file field but keeping other data
        if corrupted:
            self.stdout.write('\nFixing corrupted records...')
            for media in corrupted:
                old_path = str(media.file)
                # Clear the corrupted file path but keep the record with telegram_file_id
                media.file = ''
                media.save()
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Fixed OrderMedia #{media.id} - cleared corrupted path'
                    )
                )
        
        # Optionally delete records with missing files
        if delete_missing and missing:
            self.stdout.write('\nDeleting records with missing files...')
            for media in missing:
                order_count = media.order_set.count()
                if order_count > 0:
                    self.stdout.write(
                        self.style.WARNING(
                            f'Skipping OrderMedia #{media.id} - attached to {order_count} order(s)'
                        )
                    )
                else:
                    media.delete()
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'Deleted OrderMedia #{media.id} - file missing and no orders attached'
                        )
                    )
        
        self.stdout.write('\n' + self.style.SUCCESS('Done!'))
