"""
Test contact request notification
Creates a test contact request and sends notification to admin
"""
from django.core.management.base import BaseCommand
from landing.models import ContactRequest
from bot.admin_bot_service import send_contact_request_notification, ADMIN_TELEGRAM_IDS, ADMIN_BOT_TOKEN
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Test contact request notification to admin bot'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('\n=== Testing Contact Request Notification ===\n'))
        
        # Check configuration
        if not ADMIN_BOT_TOKEN:
            self.stdout.write(self.style.ERROR('❌ ADMIN_BOT_TOKEN not configured'))
            return
        
        if not ADMIN_TELEGRAM_IDS:
            self.stdout.write(self.style.ERROR('❌ ADMIN_TELEGRAM_IDS not configured'))
            return
        
        self.stdout.write(f'✅ Bot token: configured')
        self.stdout.write(f'✅ Admin IDs: {ADMIN_TELEGRAM_IDS}\n')
        
        # Create test contact request
        self.stdout.write('📝 Creating test contact request...')
        
        contact_request = ContactRequest.objects.create(
            name='Test User',
            email='test@example.com',
            company='Test Company',
            phone='+1234567890',
            message='This is a test contact request to verify admin notification is working correctly.'
        )
        
        self.stdout.write(self.style.SUCCESS(f'✅ Created contact request #{contact_request.id}\n'))
        
        # Send notification
        self.stdout.write('📤 Sending notification to admin...')
        
        try:
            result = send_contact_request_notification(contact_request)
            
            if result:
                self.stdout.write(self.style.SUCCESS(
                    '\n✅ SUCCESS! Notification sent successfully.\n'
                    '   Check your Telegram channel/group to verify you received it.\n'
                ))
            else:
                self.stdout.write(self.style.ERROR(
                    '\n❌ FAILED! Notification was not sent.\n'
                    '   Check the logs above for errors.\n'
                    '\n💡 Common issues:\n'
                    '   1. Bot is not added as admin to the channel/group\n'
                    '   2. Channel/Group ID is incorrect\n'
                    '   3. Bot doesn\'t have permission to post messages\n'
                ))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\n❌ ERROR: {e}\n'))
            import traceback
            self.stdout.write(traceback.format_exc())
        
        # Cleanup
        self.stdout.write(f'\n🧹 Cleaning up test data...')
        contact_request.delete()
        self.stdout.write('✅ Test contact request deleted\n')
