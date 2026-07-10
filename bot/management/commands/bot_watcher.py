"""
Bot Token Watcher - Automatically restarts bots when tokens change.

This command watches for changes in Translation Center bot tokens
and automatically restarts the bot process when changes are detected.

Usage:
    python manage.py bot_watcher
"""
import time
import subprocess
import hashlib
import logging
from django.db import close_old_connections
from django.core.management.base import BaseCommand
from bot.access import active_bot_centers

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Watch for bot token changes and auto-restart bot process'

    def __init__(self):
        super().__init__()
        self.last_token_hash = None

    def get_token_hash(self):
        """Hash bot tokens plus subscription state to detect lifecycle changes."""
        from organizations.models import TranslationCenter

        centers = active_bot_centers().filter(
            bot_delivery_mode=TranslationCenter.BOT_DELIVERY_POLLING
        ).values_list(
            'id', 'bot_token', 'subscription__start_date', 'subscription__end_date'
        ).order_by('id')
        
        token_string = '|'.join(
            f"{center_id}:{token}:{start_date}:{end_date}"
            for center_id, token, start_date, end_date in centers
        )
        return hashlib.md5(token_string.encode()).hexdigest()

    def restart_bots(self):
        """Restart the bot supervisor process."""
        try:
            result = subprocess.run(
                ['supervisorctl', 'restart', 'wowdash-bots'],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                self.stdout.write(self.style.SUCCESS('✓ Bot process restarted successfully'))
                logger.info('Bot process restarted due to token change')
            else:
                self.stdout.write(self.style.ERROR(f'✗ Failed to restart: {result.stderr}'))
                logger.error(f'Failed to restart bots: {result.stderr}')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Error restarting bots: {e}'))
            logger.error(f'Error restarting bots: {e}')

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🤖 Bot Token Watcher started'))
        self.stdout.write('Watching for bot token and subscription changes every 30 seconds...')
        
        self.last_token_hash = self.get_token_hash()
        self.stdout.write(f'Initial token hash: {self.last_token_hash}')

        while True:
            try:
                time.sleep(30)  # Check every 30 seconds

                # Ensure DB connections are fresh for long-running process
                try:
                    close_old_connections()
                except Exception:
                    # Best-effort: don't crash watcher if closing connections fails
                    logger.debug('Failed to close old DB connections', exc_info=True)

                current_hash = self.get_token_hash()
                
                if current_hash != self.last_token_hash:
                    self.stdout.write(self.style.WARNING(
                        f'⚡ Bot configuration changed! Old: {self.last_token_hash}, New: {current_hash}'
                    ))
                    self.restart_bots()
                    self.last_token_hash = current_hash
                    
            except KeyboardInterrupt:
                self.stdout.write(self.style.WARNING('\n👋 Bot watcher stopped'))
                break
            except Exception as e:
                logger.error(f'Bot watcher error: {e}')
                time.sleep(5)  # Wait before retrying
