"""
Multi-tenant Telegram Bot Webhook Manager

This module handles webhook setup and management for multiple translation centers,
each with their own Telegram bot. Uses efficient webhook approach where Telegram
pushes updates to our server (no polling overhead).

Updated for multi-worker support using Django cache instead of in-memory dict.
"""
import logging
import json
import secrets
import telebot
from telebot import apihelper
from django.conf import settings
from django.core.cache import cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse, HttpResponse
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

# Cache timeout for bot instances (1 hour)
BOT_CACHE_TIMEOUT = 3600


class RetryHTTPAdapter(HTTPAdapter):
    def __init__(self, **kwargs):
        retry = Retry(
            total=5,
            connect=5,
            read=5,
            backoff_factor=0.5,
            status_forcelist=(429, 502, 503, 504),
            allowed_methods=frozenset(["HEAD", "GET", "POST", "PUT", "DELETE", "OPTIONS"]),
            respect_retry_after_header=True,
            raise_on_status=False,
        )
        super().__init__(max_retries=retry, **kwargs)

def get_ssl_session():
    """Get a retrying requests session without weakening TLS verification."""
    session = requests.Session()
    session.mount("https://", RetryHTTPAdapter())
    return session


def _create_bot_instance(token):
    """Create a new TeleBot instance with proper configuration"""
    apihelper.SESSION = get_ssl_session()
    return telebot.TeleBot(token, parse_mode="HTML", threaded=False)


_bot_instances = {}


def get_bot_for_center(center, allow_inactive=False):
    """
    Get or create a TeleBot instance for a specific center.
    
    Note: In multi-worker environments, bot instances cannot be truly shared
    across processes. Each worker will create its own instance, but that's OK
    because TeleBot is stateless - all state is in Telegram's servers.
    
    We use cache to store token validation status and reduce database hits.
    
    Args:
        center: TranslationCenter instance with bot_token
        allow_inactive: Permit administrative operations such as removing or
            inspecting an existing webhook after the subscription has ended.
        
    Returns:
        TeleBot instance or None if no token configured
    """
    from bot.access import center_can_run_bot

    if not center or not center.bot_token:
        return None

    if not allow_inactive and not center_can_run_bot(center):
        logger.info(
            "Bot access denied for center %s: center or subscription is inactive",
            getattr(center, "id", None),
        )
        return None
    
    center_id = center.id
    cache_key = f"bot_token_valid:{center_id}"
    
    try:
        # Check if token is still valid (cached check)
        cached_token = cache.get(cache_key)
        instance_key = (center_id, center.bot_token)

        if cached_token == center.bot_token and instance_key in _bot_instances:
            return _bot_instances[instance_key]
        
        if cached_token == center.bot_token:
            # Token unchanged, create instance
            bot = _create_bot_instance(center.bot_token)
            _bot_instances[instance_key] = bot
            return bot
        
        # Token changed or not cached, create new instance and cache token
        bot = _create_bot_instance(center.bot_token)
        _bot_instances[instance_key] = bot
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
    for instance_key in list(_bot_instances):
        if instance_key[0] == center_id:
            _bot_instances.pop(instance_key, None)
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
    from bot.access import center_can_run_bot

    if not center.bot_token:
        return {"success": False, "error": "No bot token configured"}

    if not center_can_run_bot(center):
        return {"success": False, "error": "Center subscription is not active"}
    
    bot = get_bot_for_center(center, allow_inactive=True)
    if not bot:
        return {"success": False, "error": "Failed to create bot instance"}
    
    # Use provided base_url or try to get from settings
    if not base_url:
        base_url = getattr(settings, 'SITE_URL', None)
        if not base_url:
            return {"success": False, "error": "No base URL configured. Set SITE_URL in settings."}
    
    # Construct webhook URL
    webhook_url = f"{base_url.rstrip('/')}/bot/webhook/v2/{center.webhook_identifier}/"
    
    try:
        # Remove existing webhook first
        bot.remove_webhook()
        
        # Set new webhook
        result = bot.set_webhook(
            url=webhook_url,
            secret_token=center.webhook_secret,
            drop_pending_updates=True,
            allowed_updates=["message", "callback_query"],
        )
        
        if result:
            center.bot_delivery_mode = center.BOT_DELIVERY_WEBHOOK
            center.save(update_fields=["bot_delivery_mode", "updated_at"])
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
    
    bot = get_bot_for_center(center, allow_inactive=True)
    if not bot:
        return {"success": False, "error": "Failed to create bot instance"}
    
    try:
        bot.remove_webhook()
        invalidate_bot_cache(center.id)
        center.bot_delivery_mode = center.BOT_DELIVERY_POLLING
        center.save(update_fields=["bot_delivery_mode", "updated_at"])
        logger.info(f"Webhook removed for center {center.id}")
        return {"success": True}
    except Exception as e:
        logger.error(f"Failed to remove webhook for center {center.id}: {e}")
        return {"success": False, "error": str(e)}


def get_webhook_info(center):
    """Get current webhook info for a center's bot"""
    if not center.bot_token:
        return {"success": False, "error": "No bot token configured"}
    
    bot = get_bot_for_center(center, allow_inactive=True)
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
    from bot.access import active_bot_centers
    
    results = {}
    centers = active_bot_centers()
    
    for center in centers:
        results[center.id] = {
            "name": center.name,
            "result": setup_webhook_for_center(center, base_url)
        }
    
    return results


# ============================================================================
# Webhook View Handler
# ============================================================================

def _extract_chat_id(update_dict):
    if update_dict.get("message"):
        return update_dict["message"].get("chat", {}).get("id")
    if update_dict.get("callback_query"):
        callback = update_dict["callback_query"]
        return callback.get("message", {}).get("chat", {}).get("id") or callback.get("from", {}).get("id")
    return None


def _queue_webhook_update(request, center):
    from bot.access import center_can_run_bot
    from bot.models import TelegramUpdateReceipt
    from bot.tasks import process_telegram_update

    supplied_secret = request.META.get("HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN", "")
    if not supplied_secret or not secrets.compare_digest(supplied_secret, center.webhook_secret):
        logger.warning("Rejected Telegram webhook with invalid secret for center %s", center.pk)
        return JsonResponse({"ok": False, "error": "Invalid webhook secret"}, status=403)

    if not center_can_run_bot(center):
        logger.info("Ignoring webhook update for inactive center %s", center.pk)
        return JsonResponse({"ok": True, "inactive": True}, status=200)

    try:
        update_dict = json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse({"ok": False, "error": "Invalid JSON"}, status=400)

    update_id = update_dict.get("update_id")
    if not isinstance(update_id, int):
        return JsonResponse({"ok": False, "error": "Missing update_id"}, status=400)

    receipt, created = TelegramUpdateReceipt.objects.get_or_create(
        center=center,
        update_id=update_id,
        defaults={
            "chat_id": _extract_chat_id(update_dict),
            "payload": update_dict,
        },
    )

    if not created and receipt.status in {
        TelegramUpdateReceipt.STATUS_QUEUED,
        TelegramUpdateReceipt.STATUS_PROCESSING,
        TelegramUpdateReceipt.STATUS_COMPLETED,
        TelegramUpdateReceipt.STATUS_DEAD,
    }:
        return JsonResponse({"ok": True, "duplicate": True}, status=200)

    if not created:
        receipt.status = TelegramUpdateReceipt.STATUS_QUEUED
        receipt.chat_id = _extract_chat_id(update_dict)
        receipt.payload = update_dict
        receipt.last_error = ""
        receipt.save(update_fields=["status", "chat_id", "payload", "last_error", "updated_at"])

    try:
        process_telegram_update.delay(receipt.pk)
    except Exception as exc:
        receipt.status = TelegramUpdateReceipt.STATUS_FAILED
        receipt.last_error = f"Queue unavailable: {exc}"
        receipt.save(update_fields=["status", "last_error", "updated_at"])
        logger.exception("Failed to enqueue Telegram update %s", receipt.pk)
        return JsonResponse({"ok": False, "error": "Queue unavailable"}, status=503)

    return JsonResponse({"ok": True, "queued": True}, status=200)


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
            from bot.access import center_can_run_bot
            if not center_can_run_bot(center):
                return HttpResponse(
                    "<h1>Webhook Inactive</h1><p>Center subscription is not active.</p>",
                    status=403,
                )
            return HttpResponse(
                f"<h1>Webhook Active</h1><p>Center: {center.name}</p>",
                status=200
            )
        except TranslationCenter.DoesNotExist:
            return HttpResponse("<h1>Center Not Found</h1>", status=404)
    
    try:
        center = TranslationCenter.objects.get(id=center_id)
    except TranslationCenter.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Center not found"}, status=404)
    return _queue_webhook_update(request, center)


@csrf_exempt
@require_http_methods(["POST"])
def webhook_handler_v2(request, webhook_identifier):
    from organizations.models import TranslationCenter

    try:
        center = TranslationCenter.objects.get(webhook_identifier=webhook_identifier)
    except TranslationCenter.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Webhook not found"}, status=404)
    return _queue_webhook_update(request, center)
