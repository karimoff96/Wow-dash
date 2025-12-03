"""
Multi-tenant Telegram Bot Polling Command

This command runs all configured Telegram bots in polling mode for local development.
Each Translation Center with a bot_token will have its bot started in a separate thread.

Usage:
    python manage.py run_bots              # Run all bots
    python manage.py run_bots --center-id 1  # Run only specific center's bot
    python manage.py run_bots --list         # List all centers
"""
import threading
import time
import signal
import sys
from django.core.management.base import BaseCommand
from organizations.models import TranslationCenter
from bot.webhook_manager import get_ssl_session
import telebot
from telebot import apihelper
import logging

logger = logging.getLogger(__name__)


def copy_handlers_from_template(template_bot, target_bot):
    """
    Copy all handlers from template bot to target bot.
    The template bot is just used to get the handler definitions.
    """
    # Copy message handlers
    target_bot.message_handlers = template_bot.message_handlers.copy()
    
    # Copy callback query handlers  
    target_bot.callback_query_handlers = template_bot.callback_query_handlers.copy()
    
    # Copy other handlers
    target_bot.inline_handlers = template_bot.inline_handlers.copy()
    target_bot.chosen_inline_handlers = template_bot.chosen_inline_handlers.copy()
    target_bot.edited_message_handlers = template_bot.edited_message_handlers.copy()


class BotThread(threading.Thread):
    """Thread class for running a single bot with polling"""
    
    def __init__(self, center, bot_instance, stdout):
        super().__init__(daemon=True)
        self.center = center
        self.bot = bot_instance  # This is the actual bot object (telebot.TeleBot)
        self.running = True
        self.stdout = stdout
        self.name = f"Bot-{center.id}-{center.name}"
    
    def run(self):
        """Run the bot with infinity polling"""
        logger.info(f"Starting bot for center: {self.center.name} (ID: {self.center.id})")
        
        try:
            # Remove any existing webhook first
            self.bot.remove_webhook()
            time.sleep(0.5)  # Brief pause to ensure webhook is cleared
            
            # Start polling
            while self.running:
                try:
                    self.bot.infinity_polling(
                        timeout=30, 
                        long_polling_timeout=25,
                        allowed_updates=["message", "callback_query"]
                    )
                except Exception as e:
                    logger.error(f"Bot {self.center.name} polling error: {e}")
                    if self.running:
                        logger.info(f"Restarting bot {self.center.name} in 5 seconds...")
                        time.sleep(5)
        except Exception as e:
            logger.error(f"Bot thread for {self.center.name} crashed: {e}")
    
    def stop(self):
        """Stop the bot polling"""
        self.running = False
        try:
            self.bot.stop_polling()
        except Exception:
            pass


class MultiCenterBotRunner:
    """
    Runs multiple bots for different centers using subprocess-based isolation.
    Each center's bot runs in its own subprocess for better isolation.
    """
    
    def __init__(self, stdout, stderr):
        self.stdout = stdout
        self.stderr = stderr
        self.processes = []
        self.running = True
    
    def start_bot_subprocess(self, center_id):
        """Start a bot in a subprocess"""
        import subprocess
        import os
        
        # Get the manage.py path
        manage_py = os.path.join(os.getcwd(), 'manage.py')
        
        # Start the subprocess
        process = subprocess.Popen(
            [sys.executable, manage_py, 'run_bots', f'--center-id={center_id}'],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        return process
    
    def run_all(self, centers):
        """Run all center bots in separate subprocesses"""
        for center in centers:
            try:
                process = self.start_bot_subprocess(center.id)
                self.processes.append((center, process))
                self.stdout.write(f'  📱 Started subprocess for: {center.name} (PID: {process.pid})\n')
            except Exception as e:
                self.stderr.write(f'  ❌ Failed to start bot for {center.name}: {e}\n')
        
        return len(self.processes) > 0
    
    def monitor(self):
        """Monitor all subprocesses"""
        while self.running and self.processes:
            for center, process in self.processes:
                # Check if process is still running
                if process.poll() is not None:
                    self.stdout.write(f'  ⚠️ Bot for {center.name} stopped (exit code: {process.returncode})\n')
            time.sleep(1)
    
    def shutdown(self):
        """Shutdown all subprocesses"""
        self.running = False
        for center, process in self.processes:
            try:
                process.terminate()
                process.wait(timeout=5)
            except Exception:
                process.kill()


class Command(BaseCommand):
    help = 'Run all Telegram bots with polling (for local development)'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot_threads = []
        self.running = True
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--center-id',
            type=int,
            help='Run only a specific center\'s bot'
        )
        parser.add_argument(
            '--list',
            action='store_true',
            help='List all centers with bot tokens configured'
        )
    
    def handle(self, *args, **options):
        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        if options.get('list'):
            self.list_centers()
            return
        
        center_id = options.get('center_id')
        
        # Get centers with bot tokens
        if center_id:
            centers = TranslationCenter.objects.filter(
                id=center_id,
                bot_token__isnull=False,
                is_active=True
            ).exclude(bot_token='')
            
            if not centers.exists():
                self.stderr.write(self.style.ERROR(
                    f'Center {center_id} not found or has no bot token configured'
                ))
                return
        else:
            centers = TranslationCenter.objects.filter(
                bot_token__isnull=False,
                is_active=True
            ).exclude(bot_token='')
        
        if not centers.exists():
            self.stderr.write(self.style.WARNING(
                'No centers with bot tokens found. '
                'Configure a bot token in the admin panel for your Translation Center.'
            ))
            return
        
        self.stdout.write(self.style.SUCCESS(
            f'\n{"="*60}\n'
            f'  Multi-Tenant Bot Manager - Starting {centers.count()} bot(s)\n'
            f'{"="*60}\n'
        ))
        
        # Set up SSL session for all bots
        apihelper.SESSION = get_ssl_session()
        
        # If running all bots (no center_id), use subprocesses for isolation
        if not center_id and centers.count() > 1:
            self.stdout.write(self.style.WARNING(
                '\n  Running multiple bots using subprocesses for isolation...\n'
            ))
            
            runner = MultiCenterBotRunner(self.stdout, self.stderr)
            if runner.run_all(centers):
                self.stdout.write(self.style.SUCCESS(
                    f'\n✅ {len(runner.processes)} bot(s) running in subprocesses. Press Ctrl+C to stop.\n'
                ))
                try:
                    runner.monitor()
                except KeyboardInterrupt:
                    pass
                finally:
                    runner.shutdown()
            return
        
        # Import the bot module and update the global bot's token
        # This is necessary because handlers use the global 'bot' object
        import bot.main as bot_module
        
        # Start a bot thread for each center (single bot mode)
        for center in centers:
            self.start_bot_for_center(center, bot_module)
        
        if not self.bot_threads:
            self.stderr.write(self.style.ERROR('No bots were started'))
            return
        
        self.stdout.write(self.style.SUCCESS(
            f'\n✅ {len(self.bot_threads)} bot(s) running. Press Ctrl+C to stop.\n'
        ))
        
        # Keep main thread alive
        try:
            while self.running:
                # Check if all threads are still alive
                alive_threads = [t for t in self.bot_threads if t.is_alive()]
                if not alive_threads:
                    self.stdout.write(self.style.WARNING('All bot threads have stopped'))
                    break
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            self.shutdown()
    
    def start_bot_for_center(self, center, bot_module):
        """Create and start a bot thread for a center"""
        try:
            # IMPORTANT: Replace the global bot's token with this center's token
            # This is necessary because all handlers reference the global 'bot' object
            bot_module.bot.token = center.bot_token
            
            self.stdout.write(
                f'  📱 Starting bot for: {self.style.SUCCESS(center.name)}\n'
                f'     Token: {center.bot_token[:20]}...{center.bot_token[-10:]}\n'
            )
            
            # Create and start thread using the global bot (now with correct token)
            thread = BotThread(center, bot_module.bot, self.stdout)
            thread.start()
            self.bot_threads.append(thread)
            
        except Exception as e:
            self.stderr.write(self.style.ERROR(
                f'  ❌ Failed to start bot for {center.name}: {e}'
            ))
            import traceback
            traceback.print_exc()
    
    def list_centers(self):
        """List all centers and their bot configuration"""
        centers = TranslationCenter.objects.all()
        
        self.stdout.write(self.style.SUCCESS('\nTranslation Centers:\n' + '='*60))
        
        for center in centers:
            has_token = bool(center.bot_token)
            status = self.style.SUCCESS('✅ Token configured') if has_token else self.style.WARNING('❌ No token')
            active = self.style.SUCCESS('Active') if center.is_active else self.style.ERROR('Inactive')
            
            self.stdout.write(
                f'\n  ID: {center.id}\n'
                f'  Name: {center.name}\n'
                f'  Owner: {center.owner}\n'
                f'  Status: {active}\n'
                f'  Bot: {status}\n'
            )
            
            if has_token:
                self.stdout.write(f'  Token: {center.bot_token[:15]}...{center.bot_token[-8:]}\n')
                
                if center.company_orders_channel_id:
                    self.stdout.write(f'  Company Channel: {center.company_orders_channel_id}\n')
        
        self.stdout.write('\n' + '='*60 + '\n')
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.stdout.write(self.style.WARNING('\n\nShutdown signal received...'))
        self.running = False
    
    def shutdown(self):
        """Gracefully shut down all bot threads"""
        self.stdout.write(self.style.WARNING('\nStopping all bots...'))
        
        for thread in self.bot_threads:
            thread.stop()
        
        # Wait for threads to finish
        for thread in self.bot_threads:
            thread.join(timeout=5)
        
        self.stdout.write(self.style.SUCCESS('All bots stopped. Goodbye! 👋\n'))
