from django.core.management.base import BaseCommand
from bot.webhook_manager import (
    get_webhook_info, remove_webhook_for_center, setup_all_webhooks,
    setup_webhook_for_center,
)
from organizations.models import TranslationCenter


class Command(BaseCommand):
    help = 'Manage Telegram bot webhooks for translation centers'

    def add_arguments(self, parser):
        parser.add_argument(
            '--action',
            type=str,
            choices=['setup', 'setup-all', 'remove', 'info', 'list'],
            default='list',
            help='Action to perform: setup (single center), setup-all, info, list'
        )
        parser.add_argument(
            '--center-id',
            type=int,
            help='Center ID for single center operations'
        )
        parser.add_argument(
            '--base-url',
            type=str,
            help='Base URL for webhooks (e.g., https://yourdomain.com)'
        )

    def handle(self, *args, **options):
        action = options['action']
        center_id = options.get('center_id')
        base_url = options.get('base_url')

        if action == 'list':
            self.list_centers()
        elif action == 'setup-all':
            self.setup_all(base_url)
        elif action == 'setup':
            if not center_id:
                self.stderr.write(self.style.ERROR('--center-id is required for setup'))
                return
            self.setup_single(center_id, base_url)
        elif action == 'remove':
            if not center_id:
                self.stderr.write(self.style.ERROR('--center-id is required for remove'))
                return
            self.remove_single(center_id)
        elif action == 'info':
            if not center_id:
                self.stderr.write(self.style.ERROR('--center-id is required for info'))
                return
            self.get_info(center_id)

    def list_centers(self):
        """List all centers and their bot configuration status"""
        centers = TranslationCenter.objects.all()
        
        self.stdout.write(self.style.SUCCESS('\n=== Translation Centers ===\n'))
        
        for center in centers:
            has_token = '✅' if center.bot_token else '❌'
            has_channel = '✅' if center.company_orders_channel_id else '❌'
            
            self.stdout.write(
                f"ID: {center.id} | {center.name}\n"
                f"   Bot Token: {has_token} | Company Channel: {has_channel}\n"
            )
        
        self.stdout.write(f"\nTotal: {centers.count()} centers")

    def setup_all(self, base_url):
        """Set up webhooks for all configured centers"""
        if not base_url:
            self.stderr.write(self.style.ERROR(
                'Please provide --base-url (e.g., https://yourdomain.com)'
            ))
            return
        
        self.stdout.write(self.style.WARNING(f'\nSetting up webhooks with base URL: {base_url}\n'))
        
        results = setup_all_webhooks(base_url)
        
        for center_id, data in results.items():
            name = data['name']
            result = data['result']
            
            if result['success']:
                self.stdout.write(self.style.SUCCESS(
                    f"✅ {name}: {result.get('webhook_url', 'OK')}"
                ))
            else:
                self.stdout.write(self.style.ERROR(
                    f"❌ {name}: {result.get('error', 'Failed')}"
                ))
        
        self.stdout.write(f'\nProcessed {len(results)} centers')

    def setup_single(self, center_id, base_url):
        """Set up webhook for a single center"""
        if not base_url:
            self.stderr.write(self.style.ERROR(
                'Please provide --base-url (e.g., https://yourdomain.com)'
            ))
            return
        
        try:
            center = TranslationCenter.objects.get(id=center_id)
        except TranslationCenter.DoesNotExist:
            self.stderr.write(self.style.ERROR(f'Center with ID {center_id} not found'))
            return
        
        self.stdout.write(f'\nSetting up webhook for: {center.name}')
        
        result = setup_webhook_for_center(center, base_url)
        
        if result['success']:
            self.stdout.write(self.style.SUCCESS(
                f"✅ Webhook set: {result.get('webhook_url')}"
            ))
        else:
            self.stdout.write(self.style.ERROR(
                f"❌ Failed: {result.get('error')}"
            ))

    def get_info(self, center_id):
        """Get webhook info for a center"""
        try:
            center = TranslationCenter.objects.get(id=center_id)
        except TranslationCenter.DoesNotExist:
            self.stderr.write(self.style.ERROR(f'Center with ID {center_id} not found'))
            return
        
        self.stdout.write(f'\nWebhook info for: {center.name}\n')
        
        info = get_webhook_info(center)
        
        if info['success']:
            self.stdout.write(f"URL: {info.get('url', 'Not set')}")
            self.stdout.write(f"Pending updates: {info.get('pending_update_count', 0)}")
            if info.get('last_error_message'):
                self.stdout.write(self.style.WARNING(
                    f"Last error: {info.get('last_error_message')}"
                ))
        else:
            self.stdout.write(self.style.ERROR(f"Error: {info.get('error')}"))

    def remove_single(self, center_id):
        """Remove a webhook and return one center to polling delivery."""
        try:
            center = TranslationCenter.objects.get(id=center_id)
        except TranslationCenter.DoesNotExist:
            self.stderr.write(self.style.ERROR(f'Center with ID {center_id} not found'))
            return
        result = remove_webhook_for_center(center)
        if result['success']:
            self.stdout.write(self.style.SUCCESS(
                f"✅ Webhook removed for {center.name}; delivery mode is polling"
            ))
        else:
            self.stdout.write(self.style.ERROR(f"❌ Failed: {result.get('error')}"))
