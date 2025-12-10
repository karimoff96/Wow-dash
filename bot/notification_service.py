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
import tempfile
import zipfile
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
        # Check if order has files
        if not order.files.exists():
            logger.warning(f"Order {order.id} has no files to zip")
            return None
        
        # Create temporary directory for ZIP
        temp_dir = tempfile.mkdtemp()
        zip_filename = f"order_{order.id}_{order.bot_user.name.replace(' ', '_')}.zip"
        zip_path = os.path.join(temp_dir, zip_filename)
        
        files_added = 0
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for order_file in order.files.all():
                if order_file.file:
                    try:
                        # Get the full path to the file
                        full_path = order_file.file.path
                        if os.path.exists(full_path):
                            # Get just the filename without path
                            file_name = os.path.basename(order_file.file.name)
                            zipf.write(full_path, file_name)
                            files_added += 1
                            logger.debug(f"Added file to zip: {file_name}")
                        else:
                            logger.warning(f"File does not exist: {full_path}")
                    except Exception as e:
                        logger.error(f"Failed to add file to zip: {e}")
        
        # If no files were added, delete the empty zip and return None
        if files_added == 0:
            logger.warning(f"No files could be added to zip for order {order.id}")
            if os.path.exists(zip_path):
                os.remove(zip_path)
            if os.path.exists(temp_dir):
                os.rmdir(temp_dir)
            return None
        
        logger.info(f"Created zip for order {order.id} with {files_added} files")
        return zip_path
    except Exception as e:
        logger.error(f"Failed to create ZIP for order {order.id}: {e}")
        import traceback
        traceback.print_exc()
        return None


def format_order_message(order, include_details=True):
    """Format detailed order message for Telegram notification with rich styling."""
    from orders.models import Order
    from django.utils import timezone
    
    # Determine customer type
    is_b2b = order.bot_user.is_agency if order.bot_user else False
    is_manual = not order.bot_user
    
    # Customer type indicator
    if is_manual:
        customer_type = "📝 <b>РУЧНОЙ ЗАКАЗ</b> (Manual Order)"
    elif is_b2b:
        customer_type = "🏢 <b>B2B</b> │ Агентство"
    else:
        customer_type = "👤 <b>B2C</b> │ Физ. лицо"
    
    # Status emoji mapping with more details
    status_emoji = {
        'pending': '🟡',
        'payment_pending': '💳',
        'payment_received': '💰',
        'payment_confirmed': '✅',
        'in_progress': '🔵',
        'ready': '🟢',
        'completed': '✅',
        'cancelled': '❌',
    }
    status_names = {
        'pending': 'Ожидает',
        'payment_pending': 'Ожидает оплату',
        'payment_received': 'Оплата получена',
        'payment_confirmed': 'Оплата подтверждена',
        'in_progress': 'В работе',
        'ready': 'Готов к выдаче',
        'completed': 'Завершен',
        'cancelled': 'Отменен',
    }
    status_icon = status_emoji.get(order.status, '⚪')
    status_name = status_names.get(order.status, order.get_status_display())
    
    # Payment type with icons
    payment_emoji = "💵" if order.payment_type == "cash" else "💳"
    payment_text = "Наличные" if order.payment_type == "cash" else "Банковская карта"
    
    # Calculate file count
    file_count = order.files.count()
    
    # Format timestamps
    local_time = timezone.localtime(order.created_at)
    created_str = local_time.strftime('%d.%m.%Y в %H:%M')
    
    # ═══════════════════════════════════════
    # HEADER SECTION
    # ═══════════════════════════════════════
    message = f"""
╔═══════════════════════════════════╗
║  🎯 <b>НОВЫЙ ЗАКАЗ #{order.id}</b>
╚═══════════════════════════════════╝

{customer_type}
{status_icon} <b>Статус:</b> {status_name}

"""
    
    # ═══════════════════════════════════════
    # CUSTOMER INFO SECTION
    # ═══════════════════════════════════════
    message += "┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
    message += "┃  👤 <b>ИНФОРМАЦИЯ О КЛИЕНТЕ</b>\n"
    message += "┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n"
    
    if is_manual:
        # Manual order customer info
        customer_name = order.get_customer_display_name()
        customer_phone = order.get_customer_phone() or 'N/A'
        message += f"👤 <b>Имя:</b> {customer_name}\n"
        message += f"📞 <b>Телефон:</b> {customer_phone}\n"
        message += f"💬 <b>Telegram:</b> <i>Не указан</i>\n"
    else:
        # Bot user customer info
        message += f"👤 <b>Имя:</b> {order.bot_user.display_name}\n"
        message += f"📞 <b>Телефон:</b> {order.bot_user.phone if order.bot_user.phone else 'N/A'}\n"
        message += f"💬 <b>Telegram:</b> @{order.bot_user.username if order.bot_user.username else 'N/A'}\n"
        message += f"🆔 <b>User ID:</b> <code>{order.bot_user.user_id}</code>\n"
        
        # Agency info for B2B
        if is_b2b and order.bot_user.agency:
            message += f"\n🏢 <b>Агентство:</b> {order.bot_user.agency.name}\n"
            if order.bot_user.agency.phone:
                message += f"📞 <b>Тел. агентства:</b> {order.bot_user.agency.phone}\n"
    
    # ═══════════════════════════════════════
    # BRANCH INFO SECTION
    # ═══════════════════════════════════════
    message += f"\n┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
    message += f"┃  🏢 <b>ФИЛИАЛ</b>\n"
    message += f"┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n"
    message += f"🏢 <b>Название:</b> {order.branch.name if order.branch else 'N/A'}\n"
    if order.branch and order.branch.address:
        message += f"📍 <b>Адрес:</b> {order.branch.address}\n"
    if order.branch and hasattr(order.branch, 'phone') and order.branch.phone:
        message += f"📞 <b>Телефон:</b> {order.branch.phone}\n"
    
    if include_details:
        # ═══════════════════════════════════════
        # ORDER DETAILS SECTION
        # ═══════════════════════════════════════
        message += f"\n┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
        message += f"┃  📄 <b>ДЕТАЛИ ЗАКАЗА</b>\n"
        message += f"┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n"
        
        # Service/Category
        if order.product and order.product.category:
            message += f"📁 <b>Услуга:</b> {order.product.category.name}\n"
        
        # Product/Document type
        if order.product:
            message += f"📝 <b>Тип документа:</b> {order.product.name}\n"
        
        # Language
        if order.language:
            message += f"🌍 <b>Язык перевода:</b> {order.language.name}\n"
        
        # File statistics
        message += f"\n📊 <b>Объем работы:</b>\n"
        message += f"   • 📎 Файлов: <b>{file_count}</b>\n"
        message += f"   • 📄 Страниц: <b>{order.total_pages}</b>\n"
        message += f"   • 📋 Копий: <b>{order.copy_number}</b>\n"
        
        # ═══════════════════════════════════════
        # PAYMENT SECTION
        # ═══════════════════════════════════════
        message += f"\n┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
        message += f"┃  💰 <b>ИНФОРМАЦИЯ ОБ ОПЛАТЕ</b>\n"
        message += f"┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n"
        message += f"{payment_emoji} <b>Способ оплаты:</b> {payment_text}\n"
        
        # Price breakdown
        total_price = float(order.total_price)
        message += f"💵 <b>Сумма заказа:</b> <b>{total_price:,.0f} UZS</b>\n"
        
        # Extra fee if exists
        if order.extra_fee and float(order.extra_fee) > 0:
            extra_fee = float(order.extra_fee)
            message += f"➕ <b>Доп. услуги:</b> {extra_fee:,.0f} UZS\n"
            total_with_fee = total_price + extra_fee
            message += f"💰 <b>Итого к оплате:</b> <b>{total_with_fee:,.0f} UZS</b>\n"
        
        # Payment tracking
        if order.received and float(order.received) > 0:
            received = float(order.received)
            remaining = total_price - received
            message += f"\n💰 <b>Получено:</b> {received:,.0f} UZS\n"
            if remaining > 0:
                message += f"⏳ <b>Остаток:</b> {remaining:,.0f} UZS\n"
            else:
                message += f"✅ <b>Оплачено полностью</b>\n"
        
        # Receipt info
        if order.recipt:
            message += f"🧾 <b>Чек:</b> Прикреплен\n"
        
        # Payment tracking timestamps
        if order.payment_received_at:
            payment_time = timezone.localtime(order.payment_received_at)
            payment_str = payment_time.strftime('%d.%m.%Y в %H:%M')
            message += f"🕐 <b>Оплата получена:</b> {payment_str}\n"
            if order.payment_received_by:
                message += f"👤 <b>Принял:</b> {order.payment_received_by.full_name}\n"
        
        # ═══════════════════════════════════════
        # ASSIGNMENT SECTION
        # ═══════════════════════════════════════
        if order.assigned_to:
            message += f"\n┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
            message += f"┃  👥 <b>НАЗНАЧЕНИЕ</b>\n"
            message += f"┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n"
            message += f"👤 <b>Исполнитель:</b> {order.assigned_to.full_name}\n"
            if order.assigned_by:
                message += f"👤 <b>Назначил:</b> {order.assigned_by.full_name}\n"
            if order.assigned_at:
                assigned_time = timezone.localtime(order.assigned_at)
                assigned_str = assigned_time.strftime('%d.%m.%Y в %H:%M')
                message += f"🕐 <b>Дата назначения:</b> {assigned_str}\n"
        
        # ═══════════════════════════════════════
        # NOTES SECTION
        # ═══════════════════════════════════════
        if order.description:
            message += f"\n┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
            message += f"┃  📝 <b>ПРИМЕЧАНИЯ</b>\n"
            message += f"┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n"
            # Limit description to 400 chars
            desc = order.description[:400]
            if len(order.description) > 400:
                desc += "..."
            message += f"{desc}\n"
    
    # ═══════════════════════════════════════
    # FOOTER SECTION
    # ═══════════════════════════════════════
    message += f"\n╔═══════════════════════════════════╗\n"
    message += f"║  🕐 <b>Создан:</b> {created_str}\n"
    message += f"╚═══════════════════════════════════╝\n"
    
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
    Send order status update notification with rich formatting.
    Includes payment tracking and progress indicators.
    """
    from orders.models import Order
    from django.utils import timezone
    
    try:
        order = Order.objects.select_related(
            'branch__center', 'bot_user', 'product', 'assigned_to'
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
    
    # Status emoji and names
    status_emoji = {
        'pending': '🟡',
        'payment_pending': '💳',
        'payment_received': '💰',
        'payment_confirmed': '✅',
        'in_progress': '🔵',
        'ready': '🟢',
        'completed': '✅',
        'cancelled': '❌',
    }
    status_names = {
        'pending': 'Ожидает',
        'payment_pending': 'Ожидает оплату',
        'payment_received': 'Оплата получена',
        'payment_confirmed': 'Оплата подтверждена',
        'in_progress': 'В работе',
        'ready': 'Готов к выдаче',
        'completed': 'Завершен',
        'cancelled': 'Отменен',
    }
    
    # Progress indicator based on status
    progress_bar = ""
    if order.status == 'pending':
        progress_bar = "▱▱▱▱▱▱▱ 0%"
    elif order.status in ['payment_pending', 'payment_received']:
        progress_bar = "▰▱▱▱▱▱▱ 15%"
    elif order.status == 'payment_confirmed':
        progress_bar = "▰▰▱▱▱▱▱ 30%"
    elif order.status == 'in_progress':
        progress_bar = "▰▰▰▰▱▱▱ 60%"
    elif order.status == 'ready':
        progress_bar = "▰▰▰▰▰▰▱ 85%"
    elif order.status == 'completed':
        progress_bar = "▰▰▰▰▰▰▰ 100%"
    elif order.status == 'cancelled':
        progress_bar = "✖✖✖✖✖✖✖ ОТМЕНЕН"
    
    current_icon = status_emoji.get(order.status, '⚪')
    current_name = status_names.get(order.status, order.get_status_display())
    
    # Build message
    message = f"""
╔═══════════════════════════════════╗
║  🔄 <b>ОБНОВЛЕНИЕ СТАТУСА</b>
╚═══════════════════════════════════╝

🆔 <b>Заказ:</b> #{order.id}
"""
    
    # Show status change
    if old_status:
        old_icon = status_emoji.get(old_status, '⚪')
        old_name = status_names.get(old_status, old_status)
        message += f"\n{old_icon} <s>{old_name}</s>\n"
        message += f"           ⬇️\n"
    
    message += f"{current_icon} <b>{current_name}</b>\n\n"
    message += f"📊 <b>Прогресс:</b> {progress_bar}\n"
    
    # Customer info
    message += f"\n┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
    message += f"┃  👤 <b>КЛИЕНТ</b>\n"
    message += f"┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n"
    
    if order.bot_user:
        message += f"👤 {order.bot_user.display_name}\n"
        message += f"📞 {order.bot_user.phone if order.bot_user.phone else 'N/A'}\n"
    else:
        customer_name = order.get_customer_display_name()
        customer_phone = order.get_customer_phone() or 'N/A'
        message += f"👤 {customer_name}\n"
        message += f"📞 {customer_phone}\n"
    
    message += f"🏢 <b>Филиал:</b> {branch.name}\n"
    
    # Payment info for payment-related statuses
    if order.status in ['payment_pending', 'payment_received', 'payment_confirmed']:
        message += f"\n┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
        message += f"┃  💰 <b>ОПЛАТА</b>\n"
        message += f"┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n"
        
        total_price = float(order.total_price)
        message += f"💵 <b>Сумма:</b> {total_price:,.0f} UZS\n"
        
        if order.received and float(order.received) > 0:
            received = float(order.received)
            remaining = total_price - received
            payment_pct = (received / total_price * 100) if total_price > 0 else 0
            message += f"💰 <b>Получено:</b> {received:,.0f} UZS ({payment_pct:.0f}%)\n"
            if remaining > 0:
                message += f"⏳ <b>Остаток:</b> {remaining:,.0f} UZS\n"
        
        if order.recipt:
            message += f"🧾 <b>Чек:</b> Прикреплен ✅\n"
        
        if order.payment_received_at:
            payment_time = timezone.localtime(order.payment_received_at)
            payment_str = payment_time.strftime('%d.%m.%Y в %H:%M')
            message += f"🕐 {payment_str}\n"
    
    # Assignment info for in-progress orders
    if order.status in ['in_progress', 'ready'] and order.assigned_to:
        message += f"\n┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
        message += f"┃  👥 <b>ИСПОЛНИТЕЛЬ</b>\n"
        message += f"┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\n"
        message += f"👤 {order.assigned_to.full_name}\n"
    
    # Product info
    if order.product:
        message += f"\n📝 <b>Услуга:</b> {order.product.name}\n"
    
    # Timestamp
    update_time = timezone.localtime(timezone.now())
    update_str = update_time.strftime('%d.%m.%Y в %H:%M')
    message += f"\n╔═══════════════════════════════════╗\n"
    message += f"║  🕐 <b>Обновлено:</b> {update_str}\n"
    message += f"╚═══════════════════════════════════╝\n"
    
    # Send only to company channel for status updates
    if center.company_orders_channel_id:
        return send_message_to_channel(
            center.bot_token,
            center.company_orders_channel_id,
            message
        )
    
    return None
