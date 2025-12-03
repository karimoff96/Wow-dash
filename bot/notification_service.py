"""
Bot Notification Service for Order Routing

This module handles sending order notifications to Telegram channels
based on the multi-tenant bot infrastructure.

Order Routing Rules:
- ALWAYS send to center.company_orders_channel_id (if set)
- If B2C (individual customer) -> send to branch.b2c_orders_channel_id (if set)
- If B2B (agency customer) -> send to branch.b2b_orders_channel_id (if set)
"""

import logging
import telebot
import os
import zipfile
import tempfile
from telebot.apihelper import ApiTelegramException
from functools import lru_cache
from django.conf import settings

logger = logging.getLogger(__name__)

# Cache for bot instances to avoid creating new instances for every request
_bot_instances = {}


def get_bot_instance(bot_token):
    """
    Get or create a bot instance for the given token.
    Uses caching to avoid creating multiple instances for the same token.
    """
    if not bot_token:
        return None
    
    if bot_token not in _bot_instances:
        try:
            bot = telebot.TeleBot(bot_token, parse_mode="HTML", threaded=False)
            _bot_instances[bot_token] = bot
            logger.info(f"Created new bot instance for token ending in ...{bot_token[-8:]}")
        except Exception as e:
            logger.error(f"Failed to create bot instance: {e}")
            return None
    
    return _bot_instances[bot_token]


def clear_bot_cache(bot_token=None):
    """Clear cached bot instances. If token provided, only clear that one."""
    global _bot_instances
    if bot_token and bot_token in _bot_instances:
        del _bot_instances[bot_token]
    elif bot_token is None:
        _bot_instances = {}


def create_order_zip(order):
    """Create a ZIP file containing all order files."""
    try:
        # Create temporary directory for ZIP
        temp_dir = tempfile.mkdtemp()
        zip_filename = f"order_{order.id}_{order.bot_user.name.replace(' ', '_')}.zip"
        zip_path = os.path.join(temp_dir, zip_filename)
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for order_file in order.files.all():
                if order_file.file and os.path.exists(order_file.file.path):
                    # Get just the filename without path
                    file_name = os.path.basename(order_file.file.name)
                    zipf.write(order_file.file.path, file_name)
        
        return zip_path
    except Exception as e:
        logger.error(f"Failed to create ZIP for order {order.id}: {e}")
        return None


def format_order_message(order, include_details=True):
    """Format detailed order message for Telegram notification."""
    from orders.models import Order
    from django.utils import timezone
    
    # Determine customer type
    is_b2b = order.bot_user.is_agency if order.bot_user else False
    customer_type = "🏢 B2B (Агентство)" if is_b2b else "👤 B2C (Физ. лицо)"
    
    # Status emoji mapping
    status_emoji = {
        'pending': '🟡 Ожидает',
        'payment_pending': '💳 Ожидает оплату',
        'payment_received': '💰 Оплата получена',
        'payment_confirmed': '✅ Оплата подтверждена',
        'in_progress': '🔵 В работе',
        'ready': '🟢 Готов',
        'completed': '✅ Завершен',
        'cancelled': '❌ Отменен',
    }
    status_text = status_emoji.get(order.status, f'⚪ {order.get_status_display()}')
    
    # Payment type
    payment_emoji = "💵" if order.payment_type == "cash" else "💳"
    payment_text = "Наличные" if order.payment_type == "cash" else "Карта"
    
    # Get language if available
    lang_name = ""
    if order.language:
        lang_name = f"\n🌍 <b>Язык перевода:</b> {order.language.name}"
    
    # Get category/service name
    category_name = ""
    if order.product and order.product.category:
        category_name = f"\n📁 <b>Услуга:</b> {order.product.category.name}"
    
    # Get agency info if B2B
    agency_info = ""
    if is_b2b and order.bot_user.agency:
        agency_info = f"\n🏢 <b>Агентство:</b> {order.bot_user.agency.name}"
    
    # Calculate file count
    file_count = order.files.count()
    
    # Format created time
    local_time = timezone.localtime(order.created_at)
    created_str = local_time.strftime('%d.%m.%Y %H:%M')
    
    message = f"""
📋 <b>НОВЫЙ ЗАКАЗ #{order.id}</b>
{'━' * 25}

{customer_type}
{status_text}

👤 <b>Клиент:</b> {order.bot_user.display_name if order.bot_user else 'N/A'}
📞 <b>Телефон:</b> {order.bot_user.phone if order.bot_user and order.bot_user.phone else 'N/A'}
💬 <b>Telegram:</b> @{order.bot_user.username if order.bot_user and order.bot_user.username else 'N/A'}{agency_info}

🏢 <b>Филиал:</b> {order.branch.name if order.branch else 'N/A'}
📍 <b>Адрес:</b> {order.branch.address if order.branch and order.branch.address else 'N/A'}
"""
    
    if include_details:
        message += f"""
{'━' * 25}
📄 <b>ДЕТАЛИ ЗАКАЗА</b>
{'━' * 25}
{category_name}
📝 <b>Тип документа:</b> {order.product.name if order.product else 'N/A'}{lang_name}

📎 <b>Файлов:</b> {file_count}
📄 <b>Страниц:</b> {order.total_pages}
📋 <b>Копий:</b> {order.copy_number}

{'━' * 25}
💰 <b>ОПЛАТА</b>
{'━' * 25}
{payment_emoji} <b>Способ:</b> {payment_text}
💵 <b>Сумма:</b> {order.total_price:,.0f} UZS
"""
        if order.description:
            message += f"\n📝 <b>Примечание:</b> {order.description[:300]}"
    
    message += f"""

{'━' * 25}
🕐 <b>Создан:</b> {created_str}
"""
    
    return message


def send_message_to_channel(bot_token, channel_id, message, retry_count=3):
    """
    Send a message to a Telegram channel with retry logic.
    """
    if not bot_token or not channel_id:
        return False, "Missing bot_token or channel_id"
    
    bot = get_bot_instance(bot_token)
    if not bot:
        return False, "Failed to create bot instance"
    
    for attempt in range(retry_count):
        try:
            bot.send_message(channel_id, message)
            logger.info(f"Message sent to channel {channel_id}")
            return True, None
        except ApiTelegramException as e:
            error_msg = f"Telegram API error: {e.description}"
            logger.warning(f"Attempt {attempt + 1}/{retry_count} failed: {error_msg}")
            if attempt == retry_count - 1:
                logger.error(f"Failed to send message after {retry_count} attempts: {error_msg}")
                return False, error_msg
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    return False, "Max retries exceeded"


def send_document_to_channel(bot_token, channel_id, file_path, caption, retry_count=3):
    """
    Send a document to a Telegram channel with caption.
    """
    if not bot_token or not channel_id or not file_path:
        return False, "Missing required parameters"
    
    if not os.path.exists(file_path):
        return False, f"File not found: {file_path}"
    
    bot = get_bot_instance(bot_token)
    if not bot:
        return False, "Failed to create bot instance"
    
    for attempt in range(retry_count):
        try:
            with open(file_path, 'rb') as doc_file:
                bot.send_document(
                    chat_id=channel_id,
                    document=doc_file,
                    caption=caption,
                    parse_mode="HTML",
                    visible_file_name=os.path.basename(file_path)
                )
            logger.info(f"Document sent to channel {channel_id}")
            return True, None
        except ApiTelegramException as e:
            error_msg = f"Telegram API error: {e.description}"
            logger.warning(f"Attempt {attempt + 1}/{retry_count} failed: {error_msg}")
            if attempt == retry_count - 1:
                logger.error(f"Failed to send document after {retry_count} attempts: {error_msg}")
                return False, error_msg
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    return False, "Max retries exceeded"


def send_order_notification(order_id):
    """
    Send order notification with ZIP file to appropriate channels based on routing rules.
    
    Routing Rules:
    1. ALWAYS send to center.company_orders_channel_id (if configured)
    2. If B2C customer -> send to branch.b2c_orders_channel_id (if configured)
    3. If B2B customer -> send to branch.b2b_orders_channel_id (if configured)
    
    Both channels receive the same ZIP file with detailed order information.
    
    Args:
        order_id: The ID of the order to notify about
    
    Returns:
        dict: Results of notification attempts
    """
    from orders.models import Order
    
    results = {
        'order_id': order_id,
        'success': False,
        'company_channel': {'sent': False, 'error': None},
        'branch_channel': {'sent': False, 'error': None, 'type': None},
    }
    
    try:
        order = Order.objects.select_related(
            'branch__center', 'bot_user', 'product__category'
        ).prefetch_related('files').get(id=order_id)
    except Order.DoesNotExist:
        results['error'] = f"Order {order_id} not found"
        logger.error(results['error'])
        return results
    
    # Get center and branch
    branch = order.branch
    if not branch:
        results['error'] = "Order has no branch assigned"
        logger.error(results['error'])
        return results
    
    center = branch.center
    if not center:
        results['error'] = "Branch has no center"
        logger.error(results['error'])
        return results
    
    # Check if center has bot token
    bot_token = center.bot_token
    if not bot_token:
        results['error'] = "Center has no bot token configured"
        logger.warning(results['error'])
        return results
    
    # Format the message
    message = format_order_message(order)
    
    # Create ZIP file with order files
    zip_path = create_order_zip(order)
    
    try:
        # Determine B2C or B2B
        is_b2b = order.bot_user.is_agency if order.bot_user else False
        results['branch_channel']['type'] = 'B2B' if is_b2b else 'B2C'
        
        # 1. Send to company orders channel (always) - with ZIP file
        if center.company_orders_channel_id:
            if zip_path:
                success, error = send_document_to_channel(
                    bot_token, 
                    center.company_orders_channel_id, 
                    zip_path,
                    message
                )
            else:
                # Fallback to text message if ZIP creation failed
                success, error = send_message_to_channel(
                    bot_token, 
                    center.company_orders_channel_id, 
                    message + "\n\n⚠️ <i>Файлы не прикреплены</i>"
                )
            results['company_channel'] = {'sent': success, 'error': error}
        else:
            results['company_channel']['error'] = "Company channel not configured"
        
        # 2. Send to appropriate branch channel - with ZIP file
        branch_channel_id = branch.b2b_orders_channel_id if is_b2b else branch.b2c_orders_channel_id
        
        if branch_channel_id:
            if zip_path:
                success, error = send_document_to_channel(
                    bot_token,
                    branch_channel_id,
                    zip_path,
                    message
                )
            else:
                success, error = send_message_to_channel(
                    bot_token,
                    branch_channel_id,
                    message + "\n\n⚠️ <i>Файлы не прикреплены</i>"
                )
            results['branch_channel']['sent'] = success
            results['branch_channel']['error'] = error
        else:
            channel_type = "B2B" if is_b2b else "B2C"
            results['branch_channel']['error'] = f"{channel_type} channel not configured for branch"
        
        # Mark success if at least one channel received the notification
        results['success'] = results['company_channel']['sent'] or results['branch_channel']['sent']
        
    finally:
        # Clean up ZIP file
        if zip_path and os.path.exists(zip_path):
            try:
                os.remove(zip_path)
                # Also remove temp directory
                temp_dir = os.path.dirname(zip_path)
                if temp_dir and os.path.exists(temp_dir):
                    os.rmdir(temp_dir)
            except Exception as e:
                logger.warning(f"Failed to cleanup ZIP file: {e}")
    
    # Log summary
    logger.info(
        f"Order {order_id} notification results: "
        f"company={results['company_channel']['sent']}, "
        f"branch_{results['branch_channel']['type']}={results['branch_channel']['sent']}"
    )
    
    return results


def send_order_status_update(order_id, old_status=None):
    """
    Send order status update notification.
    Similar to send_order_notification but with status change context.
    """
    from orders.models import Order
    
    try:
        order = Order.objects.select_related(
            'branch__center', 'bot_user', 'product'
        ).get(id=order_id)
    except Order.DoesNotExist:
        logger.error(f"Order {order_id} not found for status update")
        return None
    
    branch = order.branch
    if not branch or not branch.center:
        return None
    
    center = branch.center
    if not center.bot_token:
        return None
    
    # Format status update message
    status_emoji = {
        'pending': '🟡',
        'in_progress': '🔵',
        'ready': '🟢',
        'completed': '✅',
        'cancelled': '❌',
    }
    
    message = f"""
<b>📝 Order #{order.id} Status Update</b>

{status_emoji.get(order.status, '⚪')} <b>New Status:</b> {order.get_status_display()}
"""
    if old_status:
        message += f"<i>Previous: {old_status}</i>\n"
    
    message += f"""
<b>Customer:</b> {order.bot_user.display_name if order.bot_user else 'N/A'}
<b>Branch:</b> {branch.name}
"""
    
    # Send only to company channel for status updates
    if center.company_orders_channel_id:
        return send_message_to_channel(
            center.bot_token,
            center.company_orders_channel_id,
            message
        )
    
    return None
