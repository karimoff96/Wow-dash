"""
Multi-tenant Telegram Bot Webhook Manager

This module handles webhook setup and management for multiple translation centers,
each with their own Telegram bot. Uses efficient webhook approach where Telegram
pushes updates to our server (no polling overhead).

Updated for multi-worker support using Django cache instead of in-memory dict.
"""
import logging
import telebot
from telebot import apihelper
from django.conf import settings
from django.core.cache import cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse, HttpResponse
from functools import lru_cache
import ssl
import requests
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager

logger = logging.getLogger(__name__)

# Cache timeout for bot instances (1 hour)
BOT_CACHE_TIMEOUT = 3600

# SSL workaround for development
class NoSSLAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        kwargs["ssl_context"] = ssl._create_unverified_context()
        return super().init_poolmanager(*args, **kwargs)


def get_ssl_session():
    """Get requests session with SSL verification disabled (dev only)"""
    session = requests.Session()
    session.mount("https://", NoSSLAdapter())
    return session


def _create_bot_instance(token):
    """Create a new TeleBot instance with proper configuration"""
    apihelper.SESSION = get_ssl_session()
    return telebot.TeleBot(token, parse_mode="HTML")


def get_bot_for_center(center):
    """
    Get or create a TeleBot instance for a specific center.
    
    Note: In multi-worker environments, bot instances cannot be truly shared
    across processes. Each worker will create its own instance, but that's OK
    because TeleBot is stateless - all state is in Telegram's servers.
    
    We use cache to store token validation status and reduce database hits.
    
    Args:
        center: TranslationCenter instance with bot_token
        
    Returns:
        TeleBot instance or None if no token configured
    """
    if not center or not center.bot_token:
        return None
    
    center_id = center.id
    cache_key = f"bot_token_valid:{center_id}"
    
    try:
        # Check if token is still valid (cached check)
        cached_token = cache.get(cache_key)
        
        if cached_token == center.bot_token:
            # Token unchanged, create instance
            return _create_bot_instance(center.bot_token)
        
        # Token changed or not cached, create new instance and cache token
        bot = _create_bot_instance(center.bot_token)
        cache.set(cache_key, center.bot_token, BOT_CACHE_TIMEOUT)
        
        logger.info(f"Created bot instance for center {center_id}: {center.name}")
        return bot
        
    except Exception as e:
        logger.error(f"Failed to create bot for center {center_id}: {e}")
        return None


def invalidate_bot_cache(center_id):
    """Remove a bot from cache (call when token changes)"""
    cache_key = f"bot_token_valid:{center_id}"
    cache.delete(cache_key)
    logger.info(f"Invalidated bot cache for center {center_id}")


def setup_webhook_for_center(center, base_url=None):
    """
    Set up Telegram webhook for a center's bot.
    
    Args:
        center: TranslationCenter instance
        base_url: Base URL of your server (e.g., https://yourdomain.com)
        
    Returns:
        dict with success status and message
    """
    if not center.bot_token:
        return {"success": False, "error": "No bot token configured"}
    
    bot = get_bot_for_center(center)
    if not bot:
        return {"success": False, "error": "Failed to create bot instance"}
    
    # Use provided base_url or try to get from settings
    if not base_url:
        base_url = getattr(settings, 'SITE_URL', None)
        if not base_url:
            return {"success": False, "error": "No base URL configured. Set SITE_URL in settings."}
    
    # Construct webhook URL
    webhook_url = f"{base_url.rstrip('/')}/bot/webhook/{center.id}/"
    
    try:
        # Remove existing webhook first
        bot.remove_webhook()
        
        # Set new webhook
        result = bot.set_webhook(
            url=webhook_url,
            drop_pending_updates=True  # Don't process old messages
        )
        
        if result:
            logger.info(f"Webhook set for center {center.id}: {webhook_url}")
            return {"success": True, "webhook_url": webhook_url}
        else:
            return {"success": False, "error": "Telegram returned False"}
            
    except Exception as e:
        logger.error(f"Failed to set webhook for center {center.id}: {e}")
        return {"success": False, "error": str(e)}


def remove_webhook_for_center(center):
    """Remove webhook for a center's bot"""
    if not center.bot_token:
        return {"success": False, "error": "No bot token configured"}
    
    bot = get_bot_for_center(center)
    if not bot:
        return {"success": False, "error": "Failed to create bot instance"}
    
    try:
        bot.remove_webhook()
        invalidate_bot_cache(center.id)
        logger.info(f"Webhook removed for center {center.id}")
        return {"success": True}
    except Exception as e:
        logger.error(f"Failed to remove webhook for center {center.id}: {e}")
        return {"success": False, "error": str(e)}


def get_webhook_info(center):
    """Get current webhook info for a center's bot"""
    if not center.bot_token:
        return {"success": False, "error": "No bot token configured"}
    
    bot = get_bot_for_center(center)
    if not bot:
        return {"success": False, "error": "Failed to create bot instance"}
    
    try:
        info = bot.get_webhook_info()
        return {
            "success": True,
            "url": info.url,
            "has_custom_certificate": info.has_custom_certificate,
            "pending_update_count": info.pending_update_count,
            "last_error_date": info.last_error_date,
            "last_error_message": info.last_error_message,
            "max_connections": info.max_connections,
        }
    except Exception as e:
        logger.error(f"Failed to get webhook info for center {center.id}: {e}")
        return {"success": False, "error": str(e)}


def setup_all_webhooks(base_url=None):
    """
    Set up webhooks for all centers that have bot tokens configured.
    Call this on server startup or via management command.
    
    Returns:
        dict with results for each center
    """
    from organizations.models import TranslationCenter
    
    results = {}
    centers = TranslationCenter.objects.exclude(bot_token__isnull=True).exclude(bot_token='')
    
    for center in centers:
        results[center.id] = {
            "name": center.name,
            "result": setup_webhook_for_center(center, base_url)
        }
    
    return results


# ============================================================================
# Webhook View Handler
# ============================================================================

@csrf_exempt
@require_http_methods(["GET", "POST"])
def webhook_handler(request, center_id):
    """
    Handle incoming webhook updates for a specific center's bot.
    
    URL: /bot/webhook/<center_id>/
    """
    from organizations.models import TranslationCenter
    
    # GET request - health check
    if request.method == "GET":
        try:
            center = TranslationCenter.objects.get(id=center_id)
            return HttpResponse(
                f"<h1>Webhook Active</h1><p>Center: {center.name}</p>",
                status=200
            )
        except TranslationCenter.DoesNotExist:
            return HttpResponse("<h1>Center Not Found</h1>", status=404)
    
    # POST request - process update
    try:
        import json
        
        # Get center
        try:
            center = TranslationCenter.objects.get(id=center_id)
        except TranslationCenter.DoesNotExist:
            logger.warning(f"Webhook received for non-existent center: {center_id}")
            return JsonResponse({"ok": False, "error": "Center not found"}, status=404)
        
        if not center.bot_token:
            logger.warning(f"Webhook received for center without token: {center_id}")
            return JsonResponse({"ok": False, "error": "No bot token"}, status=400)
        
        # Import the global bot with handlers from bot.main
        try:
            import bot.main as bot_module
            bot = bot_module.bot
            
            # Update bot token to match this center
            bot.token = center.bot_token
        except Exception as e:
            logger.error(f"Failed to import bot handlers: {e}")
            return JsonResponse({"ok": False, "error": "Bot handlers unavailable"}, status=500)
        
        # Parse update
        update_data = request.body.decode("utf-8")
        update_dict = json.loads(update_data)
        
        # Ignore messages from bots
        if "message" in update_dict:
            if update_dict["message"].get("from", {}).get("is_bot", False):
                return JsonResponse({"ok": True}, status=200)
        
        if "callback_query" in update_dict:
            if update_dict["callback_query"].get("from", {}).get("is_bot", False):
                return JsonResponse({"ok": True}, status=200)
        
        logger.debug(f"Processing update for center {center_id}: {update_data[:100]}...")
        
        # Process the update with the center-specific bot
        # We need to inject center context into the update processing
        update = telebot.types.Update.de_json(update_data)
        
        # Store center context for handlers to access
        if hasattr(update, 'message') and update.message:
            update.message._center = center
            update.message._center_bot = bot
        if hasattr(update, 'callback_query') and update.callback_query:
            update.callback_query._center = center
            update.callback_query._center_bot = bot
        
        # Process the update
        bot.process_new_updates([update])
        
        return JsonResponse({"ok": True}, status=200)
        
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in webhook: {e}")
        return JsonResponse({"ok": False, "error": "Invalid JSON"}, status=400)
    except Exception as e:
        logger.error(f"Error processing webhook for center {center_id}: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({"ok": False, "error": str(e)}, status=200)
