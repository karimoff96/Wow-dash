"""
Unified management command for file archiving

Usage:
    # Archive files
    python manage.py archive --run --center <id>    # Archive for specific center
    python manage.py archive --run --all            # Archive for all centers
    
    # View configuration
    python manage.py archive --config               # Show current config
    python manage.py archive --config --validate    # Validate config
    python manage.py archive --config --preset BALANCED  # Show preset
"""
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from organizations.models import TranslationCenter
from core.storage_service import StorageArchiveService
from WowDash.archive_config import ArchiveConfig, ArchivePresets


class Command(BaseCommand):
    help = 'Unified command for file archiving and configuration management'
    
    def add_arguments(self, parser):
        # Main action group
        action_group = parser.add_mutually_exclusive_group(required=True)
        action_group.add_argument(
            '--run',
            action='store_true',
            help='Run archiving process'
        )
        action_group.add_argument(
            '--config',
            action='store_true',
            help='Show or manage configuration'
        )
        
        # Archive execution options
        parser.add_argument(
            '--center',
            type=int,
            help='Center ID to archive files for'
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Archive files for all active centers'
        )
        parser.add_argument(
            '--age-days',
            type=int,
            help='Minimum age in days for orders to archive'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force archiving even if below size threshold'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be archived without actually doing it'
        )
        
        # Configuration options
        parser.add_argument(
            '--validate',
            action='store_true',
            help='Validate configuration settings'
        )
        parser.add_argument(
            '--preset',
            type=str,
            choices=['AGGRESSIVE', 'BALANCED', 'CONSERVATIVE'],
            help='Show recommended settings for a preset'
        )
    
    def handle(self, *args, **options):
        if options['config']:
            self._handle_config(options)
        elif options['run']:
            self._handle_archive(options)
    
    def _handle_config(self, options):
        """Handle configuration display and management"""
        # Show current configuration
        if not options['validate'] and not options['preset']:
            self.stdout.write(self.style.SUCCESS("\n" + "=" * 60))
            self.stdout.write(self.style.SUCCESS("CURRENT ARCHIVE CONFIGURATION"))
            self.stdout.write(self.style.SUCCESS("=" * 60))
            
            settings = ArchiveConfig.get_all_settings()
            for key, value in settings.items():
                if isinstance(value, bool):
                    value_str = self.style.SUCCESS("✓ Enabled") if value else self.style.ERROR("✗ Disabled")
                else:
                    value_str = str(value)
                self.stdout.write(f"{key:<35} {value_str}")
            
            self.stdout.write(self.style.SUCCESS("=" * 60))
        
        # Validate settings
        if options['validate']:
            self.stdout.write("\n" + self.style.WARNING("Validating configuration..."))
            warnings = ArchiveConfig.validate_settings()
            
            for warning in warnings:
                if "✅" in warning:
                    self.stdout.write(self.style.SUCCESS(warning))
                elif "⚠️" in warning:
                    self.stdout.write(self.style.WARNING(warning))
                elif "❌" in warning:
                    self.stdout.write(self.style.ERROR(warning))
                else:
                    self.stdout.write(warning)
        
        # Show preset configuration
        if options['preset']:
            self.stdout.write("\n" + self.style.SUCCESS(f"Showing '{options['preset']}' preset configuration:"))
            self.stdout.write("=" * 60)
            
            preset = ArchivePresets.apply_preset(options['preset'])
            
            self.stdout.write("\n" + self.style.WARNING("To apply this preset, add to your .env file:"))
            self.stdout.write("-" * 60)
            for key, value in preset.items():
                self.stdout.write(f"ARCHIVE_{key}={value}")
            self.stdout.write("-" * 60)
    
    def _handle_archive(self, options):
        """Handle archiving execution"""
        # Use configured age or default from config
        age_days = options['age_days'] if options['age_days'] else ArchiveConfig.MIN_AGE_DAYS
        service = StorageArchiveService()
        
        # Get centers to process
        if options['center']:
            try:
                centers = [TranslationCenter.objects.get(id=options['center'])]
            except TranslationCenter.DoesNotExist:
                raise CommandError(f"Center with ID {options['center']} does not exist")
        elif options['all']:
            centers = TranslationCenter.objects.filter(is_active=True)
        else:
            raise CommandError("Please specify either --center <id> or --all with --run")
        
        if not centers:
            self.stdout.write(self.style.WARNING('No centers to process'))
            return
        
        self.stdout.write(f"Processing {len(centers)} center(s)...")
        
        total_archived = 0
        total_size = 0
        
        for center in centers:
            self.stdout.write(f"\n{'='*60}")
            self.stdout.write(f"Center: {center.name} (ID: {center.id})")
            self.stdout.write(f"{'='*60}")
            
            # Get archivable orders
            orders = service.get_archivable_orders(center, age_days)
            
            if not orders.exists():
                self.stdout.write(self.style.WARNING(f"  No orders to archive"))
                continue
            
            # Calculate size
            size_bytes = service.calculate_total_size(orders)
            size_mb = size_bytes / (1024 * 1024)
            
            self.stdout.write(f"  Orders found: {orders.count()}")
            self.stdout.write(f"  Total size: {size_mb:.2f} MB")
            
            # Check if center has required configuration
            if not center.bot_token:
                self.stdout.write(self.style.ERROR(f"  ✗ No bot token configured - skipping"))
                continue
            
            if not center.company_orders_channel_id:
                self.stdout.write(self.style.ERROR(f"  ✗ No company orders channel configured - skipping"))
                continue
            
            if options['dry_run']:
                self.stdout.write(self.style.WARNING(f"  [DRY RUN] Would archive {orders.count()} orders"))
                continue
            
            # Perform archiving
            result = service.archive_orders(
                center=center,
                age_days=age_days,
                force=options['force']
            )
            
            if result['success']:
                self.stdout.write(self.style.SUCCESS(
                    f"  ✓ Successfully archived {result['orders_count']} orders"
                ))
                self.stdout.write(f"    Archive: {result['archive_name']}")
                self.stdout.write(f"    Size: {result['archive_size'] / (1024 * 1024):.2f} MB")
                self.stdout.write(f"    Message ID: {result['message_id']}")
                
                total_archived += result['orders_count']
                total_size += result['archive_size']
            else:
                self.stdout.write(self.style.ERROR(f"  ✗ Failed: {result['error']}"))
        
        # Summary
        self.stdout.write(f"\n{'='*60}")
        self.stdout.write(self.style.SUCCESS("SUMMARY"))
        self.stdout.write(f"{'='*60}")
        self.stdout.write(f"Total orders archived: {total_archived}")
        self.stdout.write(f"Total size archived: {total_size / (1024 * 1024):.2f} MB")
        self.stdout.write(f"Timestamp: {timezone.now()}")
