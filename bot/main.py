from django.views.decorators.csrf import csrf_exempt
import telebot
from telebot import types
from telebot.apihelper import ApiTelegramException
from django.http import HttpResponse
from dotenv import load_dotenv
import os
import logging
from .translations import get_text, create_or_update_user
from .notification_service import send_order_notification
from django.core.files.base import ContentFile
from django.utils import timezone
import mimetypes
from io import BytesIO
from django.core.files.storage import default_storage
import uuid
from accounts.models import BotUser

# Import persistent state (Redis-backed for multi-worker support)
from .persistent_state import user_data, uploaded_files

logger = logging.getLogger(__name__)

load_dotenv()

# user_data and uploaded_files are now imported from persistent_state.py
# They use Redis/database-backed storage for multi-worker support

# Disable SSL verification (for development only - not recommended for production)
import ssl
from telebot import apihelper
import requests
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager


class NoSSLAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        kwargs["ssl_context"] = ssl._create_unverified_context()
        return super().init_poolmanager(*args, **kwargs)


# Create custom session with SSL verification disabled
session = requests.Session()
session.mount("https://", NoSSLAdapter())
apihelper.SESSION = session

# Initialize bot with a PLACEHOLDER token for handler registration only.
# This template bot is NEVER used for actual polling - it only serves as a 
# container for handler definitions that get copied to center-specific bots.
# Multi-tenant bots are created separately with actual tokens from the database.
_TEMPLATE_TOKEN = "0000000000:XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
bot = telebot.TeleBot(_TEMPLATE_TOKEN, parse_mode="HTML", threaded=False)

# Admin user IDs (add your admin user IDs here)
ADMINS = []  # Example: [123456789, 987654321]


def get_translated_field(obj, field_name, language):
    """
    Get translated field value based on user's language.
    For modeltranslation, fields are stored as field_uz, field_ru, field_en

    Args:
        obj: Model instance (Cateogry or Product)
        field_name: Base field name ('name' or 'description')
        language: User's language ('uz', 'ru', 'en')

    Returns:
        Translated field value or default value
    """
    # Map language codes to field suffixes
    lang_suffix = language if language in ["uz", "ru", "en"] else "uz"
    translated_field = f"{field_name}_{lang_suffix}"

    # Try to get the translated field
    value = getattr(obj, translated_field, None)

    # Fallback to base field if translation is empty
    if not value:
        value = getattr(obj, field_name, "")

    return value


# Channel IDs for order forwarding
B2C_CHANNEL_ID = os.getenv("B2C_CHANNEL_ID")  # For regular users
B2B_CHANNEL_ID = os.getenv("B2B_CHANNEL_ID")  # For agency users

# Allowed file extensions
ALLOWED_EXTENSIONS = {
    ".doc",
    ".docx",
    ".pdf",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".bmp",
    ".tiff",
    ".tif",
    ".webp",
    ".heic",
    ".heif",
}
STEP_LANGUAGE_SELECTED = 1
STEP_BRANCH_SELECTION = 2  # NEW: After language, before registration
STEP_REGISTRATION_STARTED = 3
STEP_NAME_REQUESTED = 4
STEP_PHONE_REQUESTED = 5
STEP_REGISTERED = 6
STEP_EDITING_PROFILE = 7
STEP_EDITING_NAME = 8
STEP_EDITING_PHONE = 9
STEP_SELECTING_SERVICE = 10
STEP_SELECTING_DOCUMENT = 11
STEP_SELECTING_COPY_NUMBER = 12
STEP_UPLOADING_FILES = 13
STEP_PAYMENT_METHOD = 14
STEP_AWAITING_PAYMENT = 15
STEP_UPLOADING_RECEIPT = 16
STEP_AWAITING_RECEIPT = 17  # For additional payment receipts on existing orders


def is_valid_file_format(file_name):
    """Check if file has allowed extension"""
    if not file_name:
        return False
    _, ext = os.path.splitext(file_name.lower())
    return ext in ALLOWED_EXTENSIONS


def create_order_zip(order):
    """
    Create a ZIP file containing all order files and receipt (if exists)
    Returns the path to the created ZIP file
    """
    import zipfile
    from io import BytesIO
    from django.core.files.storage import default_storage
    import tempfile

    try:
        # Create a temporary file for the ZIP
        temp_zip = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")

        with zipfile.ZipFile(temp_zip.name, "w", zipfile.ZIP_DEFLATED) as zipf:
            # Add all order files
            for order_file in order.files.all():
                if order_file.file and default_storage.exists(order_file.file.name):
                    file_path = order_file.file.name
                    file_name = os.path.basename(file_path)

                    # Read file from storage
                    with default_storage.open(file_path, "rb") as f:
                        zipf.writestr(f"files/{file_name}", f.read())

            # Add receipt if exists
            if order.recipt:
                if hasattr(order.recipt, "name") and default_storage.exists(
                    order.recipt.name
                ):
                    receipt_path = order.recipt.name
                    receipt_name = os.path.basename(receipt_path)

                    with default_storage.open(receipt_path, "rb") as f:
                        zipf.writestr(f"receipt/{receipt_name}", f.read())

        return temp_zip.name

    except Exception as e:
        logger.error(f"Failed to create ZIP file: {e}", exc_info=True)
        return None


def send_order_status_notification(order, old_status, new_status):
    """
    Send notification to user when order status changes.
    Handles both status and payment-related notifications.
    """
    from accounts.models import AdditionalInfo

    # Define all notifiable statuses with their notification types
    notifiable_statuses = {
        "payment_pending": "payment",
        "payment_received": "payment",
        "payment_confirmed": "payment",
        "in_progress": "status",
        "ready": "status",
        "completed": "status",
        "cancelled": "status",
    }

    if new_status not in notifiable_statuses:
        return

    try:
        user = order.bot_user
        if not user or not user.user_id:
            logger.warning(f"No user or user_id for order {order.id}")
            return
            
        language = user.language or "uz"

        # Get additional info for address and phone
        additional_info = AdditionalInfo.get_for_user(user)
        phone = additional_info.support_phone if additional_info and additional_info.support_phone else "N/A"
        branch_name = order.branch.name if order.branch else "Translation Center"
        branch_address = order.branch.address if order.branch and order.branch.address else ""
        
        # Build notification based on status
        if new_status == "payment_pending":
            if language == "uz":
                notification_text = (
                    f"💳 <b>To'lov kutilmoqda</b>\n\n"
                    f"📋 Buyurtma raqami: #{order.id}\n"
                    f"💰 To'lov summasi: {order.total_price:,.0f} so'm\n\n"
                    f"📱 To'lov chekini yuborishingizni kutmoqdamiz."
                )
            elif language == "ru":
                notification_text = (
                    f"💳 <b>Ожидание оплаты</b>\n\n"
                    f"📋 Номер заказа: #{order.id}\n"
                    f"💰 Сумма к оплате: {order.total_price:,.0f} сум\n\n"
                    f"📱 Ожидаем квитанцию об оплате."
                )
            else:
                notification_text = (
                    f"💳 <b>Payment Pending</b>\n\n"
                    f"📋 Order #: #{order.id}\n"
                    f"💰 Amount: {order.total_price:,.0f} sum\n\n"
                    f"📱 Waiting for your payment receipt."
                )
        
        elif new_status == "payment_received":
            if language == "uz":
                notification_text = (
                    f"📨 <b>To'lov cheki qabul qilindi</b>\n\n"
                    f"📋 Buyurtma raqami: #{order.id}\n"
                    f"💰 Summa: {order.total_price:,.0f} so'm\n\n"
                    f"⏳ To'lovingiz tekshirilmoqda. Tez orada tasdiqlash habarimiz keladi."
                )
            elif language == "ru":
                notification_text = (
                    f"📨 <b>Квитанция об оплате получена</b>\n\n"
                    f"📋 Номер заказа: #{order.id}\n"
                    f"💰 Сумма: {order.total_price:,.0f} сум\n\n"
                    f"⏳ Ваша оплата проверяется. Скоро вы получите подтверждение."
                )
            else:
                notification_text = (
                    f"📨 <b>Payment Receipt Received</b>\n\n"
                    f"📋 Order #: #{order.id}\n"
                    f"💰 Amount: {order.total_price:,.0f} sum\n\n"
                    f"⏳ Your payment is being verified. You'll receive confirmation shortly."
                )
        
        elif new_status == "payment_confirmed":
            if language == "uz":
                notification_text = (
                    f"✅ <b>To'lov tasdiqlandi!</b>\n\n"
                    f"📋 Buyurtma raqami: #{order.id}\n"
                    f"💰 Summa: {order.total_price:,.0f} so'm\n\n"
                    f"🔄 Buyurtmangiz jarayonga qo'shildi. Operatorlarimiz tez orada bog'lanishadi."
                )
            elif language == "ru":
                notification_text = (
                    f"✅ <b>Оплата подтверждена!</b>\n\n"
                    f"📋 Номер заказа: #{order.id}\n"
                    f"💰 Сумма: {order.total_price:,.0f} сум\n\n"
                    f"🔄 Ваш заказ добавлен в обработку. Наши операторы свяжутся с вами."
                )
            else:
                notification_text = (
                    f"✅ <b>Payment Confirmed!</b>\n\n"
                    f"📋 Order #: #{order.id}\n"
                    f"💰 Amount: {order.total_price:,.0f} sum\n\n"
                    f"🔄 Your order is now being processed. Our operators will contact you soon."
                )
        
        elif new_status == "in_progress":
            estimated_days = order.product.estimated_days if order.product else "N/A"
            if language == "uz":
                notification_text = (
                    f"🔄 <b>Buyurtma jarayonda!</b>\n\n"
                    f"📋 Buyurtma raqami: #{order.id}\n"
                    f"⏱️ Taxminiy muddat: {estimated_days} kun\n\n"
                    f"✅ Sizga tayyor bo'lganda xabar beramiz."
                )
            elif language == "ru":
                notification_text = (
                    f"🔄 <b>Заказ в процессе!</b>\n\n"
                    f"📋 Номер заказа: #{order.id}\n"
                    f"⏱️ Примерный срок: {estimated_days} дней\n\n"
                    f"✅ Мы сообщим вам, когда будет готово."
                )
            else:
                notification_text = (
                    f"🔄 <b>Order In Progress!</b>\n\n"
                    f"📋 Order #: #{order.id}\n"
                    f"⏱️ Estimated time: {estimated_days} days\n\n"
                    f"✅ We'll notify you when it's ready."
                )
        
        elif new_status == "ready":
            if language == "uz":
                notification_text = (
                    f"✅ <b>Buyurtma tayyor!</b>\n\n"
                    f"📋 Buyurtma raqami: #{order.id}\n"
                    f"📦 Buyurtmangizni olib ketishingiz mumkin.\n\n"
                    f"🏢 Filial: {branch_name}\n"
                )
                if branch_address:
                    notification_text += f"📍 Manzil: {branch_address}\n"
                if phone != "N/A":
                    notification_text += f"📞 Telefon: {phone}"
            elif language == "ru":
                notification_text = (
                    f"✅ <b>Заказ готов!</b>\n\n"
                    f"📋 Номер заказа: #{order.id}\n"
                    f"📦 Вы можете забрать свой заказ.\n\n"
                    f"🏢 Филиал: {branch_name}\n"
                )
                if branch_address:
                    notification_text += f"📍 Адрес: {branch_address}\n"
                if phone != "N/A":
                    notification_text += f"📞 Телефон: {phone}"
            else:
                notification_text = (
                    f"✅ <b>Order Ready!</b>\n\n"
                    f"📋 Order #: #{order.id}\n"
                    f"📦 You can pick up your order.\n\n"
                    f"🏢 Branch: {branch_name}\n"
                )
                if branch_address:
                    notification_text += f"📍 Address: {branch_address}\n"
                if phone != "N/A":
                    notification_text += f"📞 Phone: {phone}"
        
        elif new_status == "completed":
            if language == "uz":
                notification_text = (
                    f"🎉 <b>Buyurtma yakunlandi!</b>\n\n"
                    f"📋 Buyurtma raqami: #{order.id}\n\n"
                    f"🙏 Xizmatlarimizdan foydalanganingiz uchun rahmat!\n"
                    f"⭐ Fikr-mulohazangizni kutamiz."
                )
            elif language == "ru":
                notification_text = (
                    f"🎉 <b>Заказ завершен!</b>\n\n"
                    f"📋 Номер заказа: #{order.id}\n\n"
                    f"🙏 Спасибо за использование наших услуг!\n"
                    f"⭐ Ждем ваших отзывов."
                )
            else:
                notification_text = (
                    f"🎉 <b>Order Completed!</b>\n\n"
                    f"📋 Order #: #{order.id}\n\n"
                    f"🙏 Thank you for using our services!\n"
                    f"⭐ We look forward to your feedback."
                )
        
        elif new_status == "cancelled":
            if language == "uz":
                notification_text = (
                    f"❌ <b>Buyurtma bekor qilindi</b>\n\n"
                    f"📋 Buyurtma raqami: #{order.id}\n\n"
                    f"📞 Savollaringiz bo'lsa, operatorlarimiz bilan bog'laning."
                )
                if phone != "N/A":
                    notification_text += f"\n📱 Telefon: {phone}"
            elif language == "ru":
                notification_text = (
                    f"❌ <b>Заказ отменен</b>\n\n"
                    f"📋 Номер заказа: #{order.id}\n\n"
                    f"📞 Если у вас есть вопросы, свяжитесь с нашими операторами."
                )
                if phone != "N/A":
                    notification_text += f"\n📱 Телефон: {phone}"
            else:
                notification_text = (
                    f"❌ <b>Order Cancelled</b>\n\n"
                    f"📋 Order #: #{order.id}\n\n"
                    f"📞 If you have questions, contact our operators."
                )
                if phone != "N/A":
                    notification_text += f"\n📱 Phone: {phone}"
        else:
            # Generic fallback
            notification_text = get_text(f"status_{new_status}", language)
            if not notification_text or "Missing translation" in notification_text:
                logger.warning(f"No notification text found for status: {new_status}")
                return
            notification_text = notification_text.format(
                order_id=order.id,
                price=f"{order.total_price:,.0f}",
                days=order.product.estimated_days if order.product else "N/A",
                phone=phone,
                address=branch_address or branch_name
            )

        # Get the correct bot instance for this order's center
        from bot.webhook_manager import get_bot_for_center
        if order.branch and order.branch.center:
            center_bot = get_bot_for_center(order.branch.center)
            if center_bot:
                center_bot.send_message(
                    chat_id=user.user_id, text=notification_text, parse_mode="HTML"
                )
            else:
                # Fallback to global bot
                bot.send_message(
                    chat_id=user.user_id, text=notification_text, parse_mode="HTML"
                )
        else:
            # No branch center, use global bot
            bot.send_message(
                chat_id=user.user_id, text=notification_text, parse_mode="HTML"
            )

        logger.info(
            f"Sent status notification to user {user.user_id} for order {order.id}: {old_status} → {new_status}"
        )

    except Exception as e:
        logger.error(f"Failed to send status notification: {e}", exc_info=True)


def send_payment_received_notification(order, amount_received, total_received):
    """
    Send notification to user when a payment amount is received (partial payment support).
    """
    try:
        user = order.bot_user
        if not user or not user.user_id:
            logger.warning(f"No user or user_id for order {order.id} during payment notification")
            return
            
        language = user.language or "uz"
        
        # Calculate remaining balance
        remaining = order.remaining
        total_due = order.total_due
        
        # Check if payment is fully completed
        is_fully_paid = remaining <= 0 or order.payment_accepted_fully
        
        if is_fully_paid:
            # Full payment notification
            if language == "uz":
                notification_text = (
                    f"✅ <b>To'lov to'liq qabul qilindi!</b>\n\n"
                    f"📋 Buyurtma raqami: #{order.id}\n"
                    f"💰 Qabul qilingan summa: {amount_received:,.0f} so'm\n"
                    f"💵 Jami to'langan: {total_received:,.0f} / {total_due:,.0f} so'm\n\n"
                    f"🎉 Rahmat! Buyurtmangiz tez orada bajariladi."
                )
            elif language == "ru":
                notification_text = (
                    f"✅ <b>Оплата полностью получена!</b>\n\n"
                    f"📋 Номер заказа: #{order.id}\n"
                    f"💰 Полученная сумма: {amount_received:,.0f} сум\n"
                    f"💵 Всего оплачено: {total_received:,.0f} / {total_due:,.0f} сум\n\n"
                    f"🎉 Спасибо! Ваш заказ скоро будет выполнен."
                )
            else:
                notification_text = (
                    f"✅ <b>Payment Fully Received!</b>\n\n"
                    f"📋 Order #: #{order.id}\n"
                    f"💰 Amount received: {amount_received:,.0f} sum\n"
                    f"💵 Total paid: {total_received:,.0f} / {total_due:,.0f} sum\n\n"
                    f"🎉 Thank you! Your order will be processed soon."
                )
        else:
            # Partial payment notification
            if language == "uz":
                notification_text = (
                    f"💳 <b>Qisman to'lov qabul qilindi</b>\n\n"
                    f"📋 Buyurtma raqami: #{order.id}\n"
                    f"💰 Qabul qilingan summa: {amount_received:,.0f} so'm\n"
                    f"💵 Jami to'langan: {total_received:,.0f} / {total_due:,.0f} so'm\n"
                    f"📊 Qolgan summa: {remaining:,.0f} so'm\n\n"
                    f"ℹ️ To'lov to'liq qabul qilinganida xabar beramiz."
                )
            elif language == "ru":
                notification_text = (
                    f"💳 <b>Частичная оплата получена</b>\n\n"
                    f"📋 Номер заказа: #{order.id}\n"
                    f"💰 Полученная сумма: {amount_received:,.0f} сум\n"
                    f"💵 Всего оплачено: {total_received:,.0f} / {total_due:,.0f} сум\n"
                    f"📊 Остаток: {remaining:,.0f} сум\n\n"
                    f"ℹ️ Мы сообщим, когда оплата будет завершена."
                )
            else:
                notification_text = (
                    f"💳 <b>Partial Payment Received</b>\n\n"
                    f"📋 Order #: #{order.id}\n"
                    f"💰 Amount received: {amount_received:,.0f} sum\n"
                    f"💵 Total paid: {total_received:,.0f} / {total_due:,.0f} sum\n"
                    f"📊 Remaining: {remaining:,.0f} sum\n\n"
                    f"ℹ️ We'll notify you when payment is complete."
                )
        
        # Get the correct bot instance for this order's center
        from bot.webhook_manager import get_bot_for_center
        if order.branch and order.branch.center:
            center_bot = get_bot_for_center(order.branch.center)
            if center_bot:
                center_bot.send_message(
                    chat_id=user.user_id, text=notification_text, parse_mode="HTML"
                )
            else:
                bot.send_message(
                    chat_id=user.user_id, text=notification_text, parse_mode="HTML"
                )
        else:
            bot.send_message(
                chat_id=user.user_id, text=notification_text, parse_mode="HTML"
            )

        logger.info(
            f"Sent payment notification to user {user.user_id} for order {order.id}: received {amount_received}, total {total_received}"
        )

    except Exception as e:
        logger.error(f"Failed to send payment notification: {e}", exc_info=True)


def generate_order_summary_caption(order, language):
    """
    Generate order summary caption for channel forwarding
    """
    from accounts.models import BotUser

    user = order.bot_user

    # Determine charging type
    is_dynamic = order.product.category.charging == "dynamic"

    # Calculate pricing based on user type and pages
    if user.is_agency:
        first_page_price = order.product.agency_first_page_price
        other_page_price = order.product.agency_other_page_price
        user_type = (
            "Agency"
            if language == "en"
            else "Агентство" if language == "ru" else "Agentlik"
        )
    else:
        first_page_price = order.product.ordinary_first_page_price
        other_page_price = order.product.ordinary_other_page_price
        user_type = (
            "Regular User"
            if language == "en"
            else "Обычный пользователь" if language == "ru" else "Oddiy foydalanuvchi"
        )

    # Calculate total price
    if is_dynamic:
        if order.total_pages == 1:
            total_price = first_page_price
        else:
            total_price = first_page_price + (
                other_page_price * (order.total_pages - 1)
            )
    else:
        total_price = first_page_price  # Static price, no multiplication

    # Payment status
    if order.payment_type == "cash":
        payment_status = (
            "Cash (On Place)"
            if language == "en"
            else "Наличные (На месте)" if language == "ru" else "Naqd pul (Joyida)"
        )
    elif order.recipt:
        payment_status = (
            "Card (Under Review)"
            if language == "en"
            else "Карта (На проверке)" if language == "ru" else "Karta (Tekshiruvda)"
        )
    else:
        payment_status = (
            "Pending"
            if language == "en"
            else "В ожидании" if language == "ru" else "Kutilmoqda"
        )

    # Get language name
    lang_name = ""
    if hasattr(order, "language") and order.language:
        try:
            from services.models import Language

            lang = Language.objects.get(id=order.language)
            lang_name = lang.name
        except:
            pass

    # Format user display with username if available
    user_display = user.name
    if user.username:
        user_display += f" (@{user.username})"

    # Create summary
    if language == "uz":
        caption = "📋 <b>YANGI BUYURTMA</b>\n\n"
        caption += f"🆔 Buyurtma raqami: #{order.id}\n"
        caption += f"👤 Mijoz: {user_display}\n"
        caption += f"📞 Telefon: {user.phone}\n"
        caption += f"🏢 Foydalanuvchi turi: {user_type}\n"
        caption += (
            f"📊 Xizmat: {get_translated_field(order.product.category, 'name', 'uz')}\n"
        )
        caption += (
            f"📄 Hujjat turi: {get_translated_field(order.product, 'name', 'uz')}\n"
        )
        if lang_name:
            caption += f"🌍 Tarjima tili: {lang_name}\n"
        caption += f"📑 Jami sahifalar: {order.total_pages}\n"
        if is_dynamic:
            caption += f"💰 1-sahifa narxi: {first_page_price:,.0f} so'm\n"
            if order.total_pages > 1:
                caption += f"💰 Qolgan sahifalar narxi: {other_page_price:,.0f} so'm\n"
        caption += f"💵 Jami summa: {total_price:,.0f} so'm\n"
        caption += f"💳 To'lov: {payment_status}\n"
        caption += f"⏱️ Taxminiy muddat: {order.product.estimated_days} kun\n"
        caption += f"📅 Buyurtma sanasi: {timezone.localtime(order.created_at).strftime('%d.%m.%Y %H:%M')}\n"
    elif language == "ru":
        caption = "📋 <b>НОВЫЙ ЗАКАЗ</b>\n\n"
        caption += f"🆔 Номер заказа: #{order.id}\n"
        caption += f"👤 Клиент: {user_display}\n"
        caption += f"📞 Телефон: {user.phone}\n"
        caption += f"🏢 Тип пользователя: {user_type}\n"
        caption += (
            f"📊 Услуга: {get_translated_field(order.product.category, 'name', 'ru')}\n"
        )
        caption += (
            f"📄 Тип документа: {get_translated_field(order.product, 'name', 'ru')}\n"
        )
        if lang_name:
            caption += f"🌍 Язык перевода: {lang_name}\n"
        caption += f"📑 Всего страниц: {order.total_pages}\n"
        if is_dynamic:
            caption += f"💰 Цена 1-й страницы: {first_page_price:,.0f} сум\n"
            if order.total_pages > 1:
                caption += f"💰 Цена остальных страниц: {other_page_price:,.0f} сум\n"
        caption += f"💵 Общая сумма: {total_price:,.0f} сум\n"
        caption += f"💳 Оплата: {payment_status}\n"
        caption += f"⏱️ Примерный срок: {order.product.estimated_days} дней\n"
        caption += f"📅 Дата заказа: {timezone.localtime(order.created_at).strftime('%d.%m.%Y %H:%M')}\n"
    else:  # English
        caption = "📋 <b>NEW ORDER</b>\n\n"
        caption += f"🆔 Order number: #{order.id}\n"
        caption += f"👤 Client: {user_display}\n"
        caption += f"📞 Phone: {user.phone}\n"
        caption += f"🏢 User type: {user_type}\n"
        caption += f"📊 Service: {get_translated_field(order.product.category, 'name', 'en')}\n"
        caption += (
            f"📄 Document type: {get_translated_field(order.product, 'name', 'en')}\n"
        )
        if lang_name:
            caption += f"🌍 Translation language: {lang_name}\n"
        caption += f"📑 Total pages: {order.total_pages}\n"
        if is_dynamic:
            caption += f"💰 1st page price: {first_page_price:,.0f} sum\n"
            if order.total_pages > 1:
                caption += f"💰 Other pages price: {other_page_price:,.0f} sum\n"
        caption += f"💵 Total amount: {total_price:,.0f} sum\n"
        caption += f"💳 Payment: {payment_status}\n"
        caption += f"⏱️ Estimated time: {order.product.estimated_days} days\n"
        caption += f"📅 Order date: {timezone.localtime(order.created_at).strftime('%d.%m.%Y %H:%M')}\n"

    return caption


def forward_order_to_channel(order, language):
    """
    Forward order with all files to appropriate channel(s).
    Uses multi-tenant notification system that sends to:
    1. Center's company_orders_channel_id (if configured)
    2. Branch's B2C or B2B channel based on customer type
    
    Falls back to env-based channels if branch/center channels not configured.
    """
    try:
        # Try multi-tenant notification first
        try:
            notification_result = send_order_notification(order.id)
            if notification_result.get('success'):
                logger.info(f"Order {order.id} sent via multi-tenant notification")
                return True
        except Exception as e:
            logger.warning(f"Multi-tenant notification failed: {e}, falling back to legacy")
        
        # Fallback to legacy env-based channel forwarding
        channel_id = B2B_CHANNEL_ID if order.bot_user.is_agency else B2C_CHANNEL_ID
        
        if not channel_id:
            logger.warning(f"No channel configured for order {order.id}")
            return False

        logger.debug(f"Forwarding order {order.id} to channel {channel_id}")

        # Create ZIP file with all order files
        zip_path = create_order_zip(order)

        if not zip_path:
            logger.error(f"Failed to create ZIP file for order {order.id}")
            return False

        # Generate caption
        caption = generate_order_summary_caption(order, language)

        # Send ZIP file to channel
        try:
            with open(zip_path, "rb") as zip_file:
                zip_filename = (
                    f"order_{order.id}_{order.bot_user.name.replace(' ', '_')}.zip"
                )
                bot.send_document(
                    chat_id=channel_id,
                    document=zip_file,
                    caption=caption,
                    parse_mode="HTML",
                    visible_file_name=zip_filename,
                )

            logger.debug(
                f"Successfully forwarded order {order.id} to channel {channel_id}"
            )

            # Clean up temporary ZIP file
            try:
                os.remove(zip_path)
            except:
                pass

            return True

        except Exception as e:
            logger.error(f"Failed to send ZIP to channel: {e}", exc_info=True)

            # Clean up temporary ZIP file
            try:
                os.remove(zip_path)
            except:
                pass

            return False

    except Exception as e:
        logger.error(f"Failed to forward order to channel: {e}", exc_info=True)
        return False


def truncate_filename(filename, max_length=50):
    """Truncate filename to prevent database field overflow while preserving extension"""
    if not filename or len(filename) <= max_length:
        return filename
    
    name, ext = os.path.splitext(filename)
    # Reserve space for extension and some characters from name
    max_name_length = max_length - len(ext) - 3  # -3 for "..."
    
    if max_name_length <= 0:
        # Extension too long, just use hash
        import hashlib
        return hashlib.md5(filename.encode()).hexdigest()[:max_length]
    
    return f"{name[:max_name_length]}...{ext}"


def get_file_pages_from_content(file_content, file_name):
    """Get accurate page count using the most precise methods available"""
    _, ext = os.path.splitext(file_name.lower())

    if ext in [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp"]:
        return 1  # Images count as 1 page
    elif ext in [".doc", ".docx"]:
        # Simple estimation for Word documents: ~500 words per page
        try:
            text = file_content.decode("utf-8", errors="ignore")
            word_count = len(text.split())
            return max(1, word_count // 500)
        except:
            return 1
    elif ext == ".pdf":
        # Use PDF library to get actual page count
        try:
            from io import BytesIO
            import PyPDF2

            # Create PDF reader from file content
            pdf_file = BytesIO(file_content)
            pdf_reader = PyPDF2.PdfReader(pdf_file)

            # Get actual number of pages
            page_count = len(pdf_reader.pages)
            return max(1, page_count)
        except Exception as e:
            logger.warning(f"Failed to read PDF pages: {e}")
            # Fallback to word count estimation if PDF parsing fails
            try:
                text = file_content.decode("utf-8", errors="ignore")
                word_count = len(text.split())
                return max(1, word_count // 500)
            except:
                return 1
    else:
        # Unknown file type, default to 1 page
        return 1


def generate_totals_message(language, total_files, total_pages):
    """Generate totals message in appropriate language"""
    return f"{get_text('file_summary_uploaded', language)}: {total_files}\n{get_text('file_summary_pages', language)}: {total_pages}"


def update_totals_message(user_id, language):
    """Update the totals message for a user"""
    if user_id in uploaded_files and uploaded_files[user_id].get("files"):
        files = uploaded_files[user_id]["files"]
        total_files = len(files)
        total_pages = sum(f["pages"] for f in files.values())

        totals_text = generate_totals_message(language, total_files, total_pages)

        # Delete previous totals message if it exists
        if "totals_message_id" in uploaded_files[user_id]:
            try:
                bot.delete_message(
                    chat_id=user_id,
                    message_id=uploaded_files[user_id]["totals_message_id"],
                )
            except:
                pass  # Message might already be deleted

        # Send new totals message using our helper function
        totals_message = send_message(user_id, totals_text)
        uploaded_files[user_id]["totals_message_id"] = totals_message.message_id
    else:
        # No files, clear the totals message ID
        if user_id in uploaded_files and "totals_message_id" in uploaded_files[user_id]:
            try:
                bot.delete_message(
                    chat_id=user_id,
                    message_id=uploaded_files[user_id]["totals_message_id"],
                )
            except:
                pass
            del uploaded_files[user_id]["totals_message_id"]


def clear_user_files(user_id):
    """Clear uploaded files for a user"""
    if user_id in uploaded_files:
        # Clean up totals message before clearing
        if "totals_message_id" in uploaded_files[user_id]:
            try:
                bot.delete_message(
                    chat_id=user_id,
                    message_id=uploaded_files[user_id]["totals_message_id"],
                )
            except:
                pass  # Message might already be deleted
        del uploaded_files[user_id]


def get_user_files(user_id):
    """Get uploaded files for a user"""
    user_data = uploaded_files.get(user_id)
    if user_data and isinstance(user_data, dict) and "files" in user_data:
        return user_data["files"]
    return {}


def get_user_language(user_id):
    """Get user's preferred language"""
    try:
        user = get_bot_user(user_id)
        if user:
            return user.language
        return "uz"
    except Exception as e:
        logger.debug(f"Error getting user language for {user_id}: {e}")
        return "uz"


def update_user_username(message):
    """Update user's Telegram username if it has changed.
    Call this function when processing messages to keep username in sync."""
    try:
        if not message or not message.from_user:
            return
        
        user_id = message.from_user.id
        telegram_username = message.from_user.username or ""
        
        user = get_bot_user(user_id)
        if user and user.username != telegram_username:
            user.username = telegram_username
            user.save(update_fields=['username'])
            logger.debug(f"Updated username for user {user_id}: {telegram_username}")
    except Exception as e:
        logger.debug(f"Error updating username for user: {e}")


def send_message(chat_id, text, reply_markup=None, parse_mode="HTML"):
    """Helper function to send messages with proper language handling"""
    try:
        # Get user's preferred language
        language = get_user_language(chat_id)

        # If text is a translation key, get the translation
        if hasattr(text, "startswith") and text.startswith("translation:"):
            text = get_text(text.replace("translation:", ""), language)

        return bot.send_message(
            chat_id=chat_id, text=text, reply_markup=reply_markup, parse_mode=parse_mode
        )
    except Exception as e:
        logger.error(f"Failed to send message to {chat_id}: {e}")
        # Fallback to direct message sending if our custom function fails
        return bot.send_message(
            chat_id=chat_id, text=text, reply_markup=reply_markup, parse_mode=parse_mode
        )


def send_branch_location(chat_id, branch, language):
    """
    Send branch location to user with pickup information.
    Extracts coordinates from location_url if possible, otherwise sends URL link.
    """
    try:
        if not branch:
            return False
        
        # Prepare location message based on language
        if language == "uz":
            location_text = "📍 <b>Buyurtmangizni olish manzili:</b>\n\n"
            location_text += f"🏢 <b>{branch.name}</b>\n"
            if branch.address:
                location_text += f"📍 Manzil: {branch.address}\n"
            if branch.phone:
                location_text += f"📞 Telefon: {branch.phone}\n"
            location_text += "\n✅ Buyurtmangiz tayyor bo'lganda sizga xabar beramiz.\n"
            location_text += "📦 Shu manzildan olib ketishingiz mumkin bo'ladi."
        elif language == "ru":
            location_text = "📍 <b>Адрес для получения заказа:</b>\n\n"
            location_text += f"🏢 <b>{branch.name}</b>\n"
            if branch.address:
                location_text += f"📍 Адрес: {branch.address}\n"
            if branch.phone:
                location_text += f"📞 Телефон: {branch.phone}\n"
            location_text += "\n✅ Когда ваш заказ будет готов, мы вас уведомим.\n"
            location_text += "📦 Вы сможете забрать его по этому адресу."
        else:  # English
            location_text = "📍 <b>Pickup location:</b>\n\n"
            location_text += f"🏢 <b>{branch.name}</b>\n"
            if branch.address:
                location_text += f"📍 Address: {branch.address}\n"
            if branch.phone:
                location_text += f"📞 Phone: {branch.phone}\n"
            location_text += "\n✅ We will notify you when your order is ready.\n"
            location_text += "📦 You can pick it up from this location."
        
        # Send location message
        bot.send_message(chat_id=chat_id, text=location_text, parse_mode="HTML")
        
        # Try to extract coordinates from location_url and send map location
        if branch.location_url:
            coords = extract_coordinates_from_url(branch.location_url)
            if coords:
                try:
                    bot.send_location(
                        chat_id=chat_id,
                        latitude=coords['lat'],
                        longitude=coords['lng']
                    )
                except Exception as e:
                    logger.warning(f"Failed to send location coordinates: {e}")
                    # Send URL as fallback
                    bot.send_message(chat_id=chat_id, text=f"🗺️ {branch.location_url}")
            else:
                # No coordinates extracted, send URL
                bot.send_message(chat_id=chat_id, text=f"🗺️ {branch.location_url}")
        
        return True
    except Exception as e:
        logger.error(f"Failed to send branch location: {e}")
        return False


def extract_coordinates_from_url(url):
    """
    Extract latitude and longitude from Google Maps or Yandex Maps URL.
    Returns dict with 'lat' and 'lng' keys, or None if extraction fails.
    
    Supports:
    - Google Maps: https://maps.google.com/?q=41.311081,69.240562
    - Google Maps: https://www.google.com/maps/@41.311081,69.240562,15z
    - Google Maps: https://goo.gl/maps/... (short URLs - returns None, just use URL)
    - Yandex Maps: https://yandex.com/maps/?ll=69.240562,41.311081
    - Yandex Maps: https://yandex.uz/maps/-/...
    """
    import re
    
    if not url:
        return None
    
    try:
        # Google Maps patterns
        # Pattern 1: ?q=lat,lng or @lat,lng
        google_pattern1 = r'[?&@]q?=?(-?\d+\.?\d*),(-?\d+\.?\d*)'
        match = re.search(google_pattern1, url)
        if match:
            lat, lng = float(match.group(1)), float(match.group(2))
            if -90 <= lat <= 90 and -180 <= lng <= 180:
                return {'lat': lat, 'lng': lng}
        
        # Pattern 2: @lat,lng,zoom
        google_pattern2 = r'@(-?\d+\.?\d*),(-?\d+\.?\d*),\d+z'
        match = re.search(google_pattern2, url)
        if match:
            lat, lng = float(match.group(1)), float(match.group(2))
            if -90 <= lat <= 90 and -180 <= lng <= 180:
                return {'lat': lat, 'lng': lng}
        
        # Pattern 3: /place/.../@lat,lng
        google_pattern3 = r'/place/[^/]+/@(-?\d+\.?\d*),(-?\d+\.?\d*)'
        match = re.search(google_pattern3, url)
        if match:
            lat, lng = float(match.group(1)), float(match.group(2))
            if -90 <= lat <= 90 and -180 <= lng <= 180:
                return {'lat': lat, 'lng': lng}
        
        # Yandex Maps patterns
        # Pattern: ll=lng,lat (note: Yandex uses lng,lat order)
        yandex_pattern = r'll=(-?\d+\.?\d*),(-?\d+\.?\d*)'
        match = re.search(yandex_pattern, url)
        if match:
            lng, lat = float(match.group(1)), float(match.group(2))
            if -90 <= lat <= 90 and -180 <= lng <= 180:
                return {'lat': lat, 'lng': lng}
        
        # Pattern: pt=lng,lat
        yandex_pattern2 = r'pt=(-?\d+\.?\d*),(-?\d+\.?\d*)'
        match = re.search(yandex_pattern2, url)
        if match:
            lng, lat = float(match.group(1)), float(match.group(2))
            if -90 <= lat <= 90 and -180 <= lng <= 180:
                return {'lat': lat, 'lng': lng}
        
        return None
    except Exception as e:
        logger.warning(f"Failed to extract coordinates from URL: {e}")
        return None


def get_current_center():
    """
    Get the TranslationCenter associated with the current bot token.
    This is essential for multi-tenant support.
    """
    try:
        from organizations.models import TranslationCenter
        center = TranslationCenter.objects.filter(bot_token=bot.token).first()
        return center
    except Exception as e:
        logger.error(f"Failed to get current center: {e}")
        return None


def get_bot_user(user_id, center=None):
    """
    Get BotUser for the given user_id and center.
    Each Telegram user has a separate account per translation center.
    
    Args:
        user_id: Telegram user ID
        center: TranslationCenter instance. If None, uses current bot's center.
    
    Returns:
        BotUser instance or None if not found
    """
    if center is None:
        center = get_current_center()
    
    try:
        return BotUser.objects.filter(user_id=user_id, center=center).first()
    except Exception as e:
        logger.error(f"Failed to get bot user: {e}")
        return None


def get_or_create_bot_user(user_id, center=None, defaults=None):
    """
    Get or create BotUser for the given user_id and center.
    
    Args:
        user_id: Telegram user ID
        center: TranslationCenter instance. If None, uses current bot's center.
        defaults: Dict of default values for creation
    
    Returns:
        Tuple of (BotUser instance, created boolean)
    """
    if center is None:
        center = get_current_center()
    
    if defaults is None:
        defaults = {}
    
    defaults['center'] = center
    
    try:
        return BotUser.objects.get_or_create(
            user_id=user_id,
            center=center,
            defaults=defaults
        )
    except Exception as e:
        logger.error(f"Failed to get or create bot user: {e}")
        return None, False


def get_center_branches(center=None):
    """
    Get all active branches for a center.
    If no center provided, uses the current bot's center.
    """
    if center is None:
        center = get_current_center()
    
    if center is None:
        return []
    
    try:
        from organizations.models import Branch
        return list(Branch.objects.filter(center=center, is_active=True))
    except Exception as e:
        logger.error(f"Failed to get branches: {e}")
        return []


def show_branch_selection(message, language):
    """
    Show branch selection after phone number is received.
    User must select a branch before registration completes.
    """
    user_id = message.from_user.id
    update_user_step(user_id, STEP_BRANCH_SELECTION)
    
    center = get_current_center()
    if not center:
        send_message(message.chat.id, get_text("error_config", language))
        return
    
    branches = get_center_branches(center)
    
    if not branches:
        send_message(message.chat.id, get_text("error_no_branches", language))
        return
    
    # If only one branch, auto-select it and complete registration
    if len(branches) == 1:
        branch = branches[0]
        # Save branch to user and complete registration
        user = get_bot_user(user_id, center)
        if user:
            user.branch = branch
            user.is_active = True
            user.step = STEP_REGISTERED
            user.save()
        else:
            user = create_or_update_user(user_id=user_id, branch=branch, center=center)
            if user:
                user.is_active = True
                user.step = STEP_REGISTERED
                user.save()
        
        # Show registration complete and main menu
        complete_text = get_text("registration_complete", language)
        send_message(message.chat.id, complete_text)
        show_main_menu(message, language)
        return
    
    # Multiple branches - show selection
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    # Build branch selection message
    header = get_text("select_branch_header", language)
    
    for branch in branches:
        # Format branch button text with name and address
        branch_name = branch.name
        branch_address = branch.address or ""
        
        if branch_address:
            button_text = f"📍 {branch_name}"
        else:
            button_text = f"📍 {branch_name}"
        
        markup.add(types.InlineKeyboardButton(
            text=button_text,
            callback_data=f"select_branch_{branch.id}"
        ))
    
    # Add back button
    back_text = get_text("back_to_menu", language)
    markup.add(types.InlineKeyboardButton(text=f"🔙 {back_text}", callback_data="back_to_language"))
    
    # Build detailed branch info message
    branch_info = header + "\n\n"
    for branch in branches:
        branch_info += f"🏢 <b>{branch.name}</b>\n"
        if branch.address:
            branch_info += f"   📍 {branch.address}\n"
        if branch.phone:
            branch_info += f"   📞 {branch.phone}\n"
        branch_info += "\n"
    
    send_message(message.chat.id, branch_info, reply_markup=markup)


def ensure_additional_info_exists():
    """Check if AdditionalInfo record exists in database - only create if missing"""
    try:
        from accounts.models import AdditionalInfo

        if not AdditionalInfo.objects.exists():
            # Only create a global default if no record exists
            AdditionalInfo.objects.create(
                branch=None,  # Global/default settings
                bank_card=None,
                holder_name="",
                help_text_uz="📞 Savollaringiz bo'lsa, admin bilan bog'laning\n🌐 Til o'zgartirish: /start\n📋 Buyurtma berish: Hizmatdan foydalanish",
                help_text_ru="📞 Если у вас есть вопросы, свяжитесь с администратором\n🌐 Сменить язык: /start\n📋 Сделать заказ: Воспользоваться услугой",
                help_text_en="📞 If you have questions, contact administrator\n🌐 Change language: /start\n📋 Place order: Use Service",
                description_uz="📞 Savollaringiz bo'lsa, admin bilan bog'laning\n🌐 Kompaniyamiz haqida ko'proq ma'lumot tez kunda qo'shiladi!",
                description_ru="📞 Если у вас есть вопросы, свяжитесь с администратором\n🌐 Информация о нашей компании будет добавлена в ближайшее время!",
                description_en="📞 If you have questions, contact administrator\n🌐 Information about our company will be added soon!",
                about_us_uz="📞 Savollaringiz bo'lsa, admin bilan bog'laning\n🌐 Kompaniyamiz haqida ko'proq ma'lumot tez kunda qo'shiladi!",
                about_us_ru="📞 Если у вас есть вопросы, свяжитесь с администратором\n🌐 Информация о нашей компании будет добавлена в ближайшее время!",
                about_us_en="📞 If you have questions, contact administrator\n🌐 Information about our company will be added soon!",
            )
            logger.info("Created default AdditionalInfo record")
        else:
            logger.info("AdditionalInfo record already exists - using existing record")
    except Exception as e:
        logger.error(f"Failed to check AdditionalInfo: {e}")


def update_user_step(user_id, step):
    """Update user's current step"""
    try:
        user = get_bot_user(user_id)
        if user:
            user.step = step
            user.save()
    except:
        pass


def get_user_step(user_id):
    """Get user's current step"""
    try:
        user = get_bot_user(user_id)
        if user:
            return user.step
        return 0
    except:
        return 0


def calculate_order_pricing(order, user):
    """
    Calculate order pricing with copy charges
    Returns: (base_price, copy_charge, total_price, copy_percentage)
    """
    # Determine charging type
    is_dynamic = order.product.category.charging == "dynamic"

    # Get base prices based on user type
    if user.is_agency:
        first_page_price = order.product.agency_first_page_price
        other_page_price = order.product.agency_other_page_price
        copy_percentage = order.product.agency_copy_price_percentage
    else:
        first_page_price = order.product.ordinary_first_page_price
        other_page_price = order.product.ordinary_other_page_price
        copy_percentage = order.product.user_copy_price_percentage

    # Calculate base price
    if is_dynamic:
        if order.total_pages == 1:
            base_price = first_page_price
        else:
            base_price = first_page_price + (other_page_price * (order.total_pages - 1))
    else:
        base_price = first_page_price

    # Calculate copy charge
    copy_charge = 0
    if order.copy_number > 0:
        copy_charge = (base_price * copy_percentage * order.copy_number) / 100

    total_price = base_price + copy_charge

    return base_price, copy_charge, total_price, copy_percentage


@bot.message_handler(commands=["start"])
def start(message):
    import uuid as uuid_module
    from accounts.models import BotUser

    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name or ""
    
    # Update username in case it changed
    update_user_username(message)

    # Default language (will be updated if user exists)
    language = "uz"

    # Check if this is an agency invitation link
    is_agency_invite = False
    agency_token = None
    agency = None

    # Check for deep link parameter (e.g., /start agency_1234-5678-...)
    if len(message.text.split()) > 1:
        param = message.text.split()[1]
        logger.debug(f"Start parameter received: {param}")

        if param.startswith("agency_"):
            try:
                agency_token = param[7:]  # Remove "agency_" prefix
                logger.debug(f"Extracted token: {agency_token}")

                # Validate it's a valid UUID
                uuid_obj = uuid_module.UUID(agency_token)
                logger.debug(f"Token is valid UUID: {uuid_obj}")

                # Try to get the agency by token
                agency = BotUser.get_agency_by_token(agency_token)
                if agency:
                    is_agency_invite = True
                    logger.info(
                        f"Valid agency token found for agency: {agency.name} (ID: {agency.id})"
                    )
                else:
                    logger.warning(
                        f"Invalid or already used agency token: {agency_token}"
                    )
            except (ValueError, IndexError) as e:
                logger.error(f"Invalid agency token format: {e}")
            except Exception as e:
                logger.error(f"Unexpected error processing agency token: {e}")

    # Check if user already exists for this center
    center = get_current_center()
    existing_user = get_bot_user(user_id, center)

    if existing_user:
        # User already exists
        language = existing_user.language

        if is_agency_invite and agency:
            # User trying to use agency invite but already has a Telegram account
            if existing_user.is_agency:
                # This user is already an agency profile
                error_msg = get_text("already_agency", language)
                send_message(message.chat.id, error_msg)
            elif existing_user.agency:
                # Already linked to another agency
                already_linked_msg = get_text(
                    "already_linked_to_agency", language
                ).format(existing_user.agency.name)
                send_message(message.chat.id, already_linked_msg)
            else:
                # Link existing user to agency
                existing_user.agency = agency
                existing_user.save()
                success_msg = get_text("agency_linked_success", language).format(
                    agency.name
                )
                send_message(message.chat.id, success_msg)
                logger.info(f" Linked existing user {user_id} to agency {agency.name}")
        elif is_agency_invite and not agency:
            # Invalid token
            error_msg = get_text("invalid_agency_invite", language)
            send_message(message.chat.id, error_msg)

        # Show appropriate menu
        if existing_user.is_active:
            show_main_menu(message, language)
        else:
            # User exists but not fully registered, restart registration
            show_language_selection(message)
        return

    # New user with agency invitation
    if is_agency_invite and agency:
        # IMPORTANT: Fill the agency profile with Telegram user data
        # Instead of creating a new user, update the agency profile
        user = agency  # Use the existing agency profile
        user.user_id = user_id  # Set the Telegram user ID
        user.username = username or ""  # Set username
        # Keep the name and phone from agency profile (set by admin)
        # User will be able to update these during registration if needed
        user.language = language  # Set user's preferred language
        user.is_active = False  # Not active until registration completes
        user.step = 0  # Start registration process
        user.save()

        # Send welcome message with agency info
        welcome_msg = get_text("agency_welcome", language).format(agency.name)
        send_message(message.chat.id, welcome_msg)
        print(
            f"[INFO] ✅ Agency profile '{agency.name}' (ID: {agency.id}) claimed by Telegram user {user_id}"
        )
    elif is_agency_invite and not agency:
        # Invalid token for new user
        error_msg = get_text("invalid_agency_invite", language)
        send_message(message.chat.id, error_msg)

        # Continue with normal registration
        center = get_current_center()
        user = create_or_update_user(
            user_id=user_id,
            username=username,
            language=language,
            center=center,
        )
    else:
        # Normal user registration
        center = get_current_center()
        user = create_or_update_user(
            user_id=user_id,
            username=username,
            language=language,
            center=center,
        )

    if user is None:
        error_msg = get_text("error_creating_account", language)
        send_message(message.chat.id, error_msg)
        return

    if user.is_active:
        show_main_menu(message, language)
        return

    current_step = get_user_step(user_id)

    if current_step == STEP_PHONE_REQUESTED:
        ask_contact(message, language)
    elif current_step == STEP_NAME_REQUESTED:
        ask_name(message, language)
    elif current_step in [STEP_LANGUAGE_SELECTED, STEP_REGISTRATION_STARTED]:
        start_registration(message, language)
    else:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)
        btn1 = types.KeyboardButton("🇺🇿 O'zbek")
        btn2 = types.KeyboardButton("🇷🇺 Русский")
        btn3 = types.KeyboardButton("🇬🇧 English")
        markup.add(btn1, btn2, btn3)

        welcome_text = get_text("welcome", language)
        if is_agency_invite and not user.agency:
            welcome_text += "\n\n⚠️ Note: The agency invitation could not be processed. Please complete your registration first."

        send_message(message.chat.id, welcome_text, reply_markup=markup)
        update_user_step(user_id, 0)


@bot.message_handler(
    func=lambda message: message.text in ["🇺🇿 O'zbek", "🇷🇺 Русский", "🇬🇧 English"]
)
def handle_language_selection(message):
    user_id = message.from_user.id
    if "O'zbek" in message.text:
        language = "uz"
        language_name = "O'zbek"
    elif "Русский" in message.text:
        language = "ru"
        language_name = "Русский"
    else:
        language = "en"
        language_name = "English"

    center = get_current_center()
    create_or_update_user(user_id=user_id, language=language, center=center)
    update_user_step(user_id, STEP_LANGUAGE_SELECTED)

    language_selected_text = get_text("language_selected", language).format(
        language=language_name
    )
    send_message(message.chat.id, language_selected_text)

    # Go directly to registration (ask name first)
    start_registration(message, language)


# Handler for branch selection callback
@bot.callback_query_handler(func=lambda call: call.data.startswith("select_branch_"))
def handle_branch_selection(call):
    user_id = call.from_user.id
    language = get_user_language(user_id)
    
    try:
        branch_id = int(call.data.split("_")[2])
        from organizations.models import Branch
        from accounts.models import BotUser
        
        branch = Branch.objects.get(id=branch_id)
        center = get_current_center()
        
        # Update user with selected branch and complete registration
        user = get_bot_user(user_id, center)
        if user:
            user.branch = branch
            user.is_active = True
            user.step = STEP_REGISTERED
            user.save()
        else:
            user = create_or_update_user(user_id=user_id, branch=branch, center=center)
            if user:
                user.is_active = True
                user.step = STEP_REGISTERED
                user.save()
        
        # Delete the branch selection message
        try:
            bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.message_id)
        except:
            pass
        
        # Confirm branch selection
        confirm_text = get_text("branch_selected", language).format(branch=branch.name)
        
        send_message(call.message.chat.id, confirm_text)
        
        # Show registration complete message
        complete_text = get_text("registration_complete", language)
        send_message(call.message.chat.id, complete_text)
        
        # Create a message-like object with correct from_user and show main menu
        class MessageWrapper:
            def __init__(self, chat, from_user):
                self.chat = chat
                self.from_user = from_user
        
        wrapped_message = MessageWrapper(call.message.chat, call.from_user)
        show_main_menu(wrapped_message, language)
        
    except Branch.DoesNotExist:
        bot.answer_callback_query(call.id, get_text("error_branch_not_found", language))
    except Exception as e:
        logger.error(f" Branch selection error: {e}")
        bot.answer_callback_query(call.id, get_text("error_general", language))


# Handler for back to language from branch selection
@bot.callback_query_handler(func=lambda call: call.data == "back_to_language")
def handle_back_to_language(call):
    try:
        bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.message_id)
    except:
        pass
    
    # Create a message-like object with correct from_user
    class MessageWrapper:
        def __init__(self, chat, from_user):
            self.chat = chat
            self.from_user = from_user
    
    wrapped_message = MessageWrapper(call.message.chat, call.from_user)
    show_language_selection(wrapped_message)


def ask_name(message, language):
    user_id = message.from_user.id
    update_user_step(user_id, STEP_NAME_REQUESTED)

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    back_btn = types.KeyboardButton(get_text("back_to_menu", language))
    markup.add(back_btn)

    ask_name_text = get_text("ask_name", language)
    send_message(message.chat.id, ask_name_text, reply_markup=markup)


def start_registration(message, language):
    user_id = message.from_user.id
    update_user_step(user_id, STEP_REGISTRATION_STARTED)
    ask_name(message, language)


def ask_contact(message, language):
    user_id = message.from_user.id
    update_user_step(user_id, STEP_PHONE_REQUESTED)

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    contact_btn = types.KeyboardButton(
        get_text("phone_button", language), request_contact=True
    )
    back_btn = types.KeyboardButton(get_text("back_to_menu", language))
    markup.add(contact_btn, back_btn)

    ask_contact_text = get_text("ask_contact", language)
    send_message(message.chat.id, ask_contact_text, reply_markup=markup)


def show_language_selection(message):
    user_id = message.from_user.id
    language = get_user_language(user_id)
    update_user_step(user_id, 0)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)
    btn1 = types.KeyboardButton("🇺🇿 O'zbek")
    btn2 = types.KeyboardButton("🇷🇺 Русский")
    btn3 = types.KeyboardButton("🇬🇧 English")
    markup.add(btn1, btn2, btn3)
    welcome_text = get_text("welcome", language)
    bot.send_message(message.chat.id, welcome_text, reply_markup=markup)


def handle_back_button(message, language):
    user_id = message.from_user.id
    current_step = get_user_step(user_id)

    if current_step == STEP_PHONE_REQUESTED:
        # Back from phone request -> ask name again
        update_user_step(user_id, STEP_NAME_REQUESTED)
        ask_name(message, language)
    elif current_step == STEP_NAME_REQUESTED:
        # Back from name request -> language selection
        show_language_selection(message)
    elif current_step == STEP_REGISTRATION_STARTED:
        show_language_selection(message)
    elif current_step == STEP_LANGUAGE_SELECTED:
        show_language_selection(message)
    elif current_step == STEP_BRANCH_SELECTION:
        # Back from branch selection -> language selection
        show_language_selection(message)
    elif current_step == STEP_SELECTING_SERVICE:
        # Back from service selection -> main menu
        show_main_menu(message, language)
    elif current_step == STEP_SELECTING_DOCUMENT:
        # Back from document selection -> services
        show_categorys(message, language)
    elif current_step == STEP_SELECTING_COPY_NUMBER:
        # Back from copy number -> document types
        user_data = uploaded_files.get(user_id, {})
        if user_data and "service_id" in user_data:
            service_id = user_data["service_id"]
            show_products(message, language, service_id)
        else:
            show_categorys(message, language)
    elif current_step == STEP_UPLOADING_FILES:
        # Back from file upload -> document types (since copy number leads to upload)
        user_data = uploaded_files.get(user_id, {})
        if user_data and "service_id" in user_data:
            service_id = user_data["service_id"]
            show_products(message, language, service_id)
        else:
            show_categorys(message, language)
    elif current_step == STEP_PAYMENT_METHOD:
        # Back from payment method -> file upload
        handle_back_to_upload_docs_message(message, language)
    elif current_step in (STEP_AWAITING_PAYMENT, STEP_UPLOADING_RECEIPT, STEP_AWAITING_RECEIPT):
        # Back from payment/receipt screens -> try to restore payment options
        user_data = uploaded_files.get(user_id, {})
        if user_data and "order_id" in user_data:
            try:
                from orders.models import Order
                order = Order.objects.get(id=user_data["order_id"])
                show_payment_options(message, language, order)
            except:
                show_main_menu(message, language)
        else:
            show_main_menu(message, language)
    elif current_step == STEP_EDITING_PROFILE:
        # Back from profile editing -> main menu
        show_main_menu(message, language)
    elif current_step == STEP_EDITING_NAME:
        # Back from name editing -> profile
        update_user_step(user_id, STEP_EDITING_PROFILE)
        show_profile(message, language)
    elif current_step == STEP_EDITING_PHONE:
        # Back from phone editing -> profile
        update_user_step(user_id, STEP_EDITING_PROFILE)
        show_profile(message, language)
    else:
        # Default: go to main menu
        show_main_menu(message, language)


@bot.message_handler(content_types=["contact"])
def handle_contact(message):
    user_id = message.from_user.id
    language = get_user_language(user_id)

    # Check if user is in phone editing step
    current_step = get_user_step(user_id)
    if current_step == STEP_EDITING_PHONE and message.contact:
        phone = message.contact.phone_number
        center = get_current_center()
        create_or_update_user(user_id=user_id, phone=phone, center=center)
        update_user_step(user_id, STEP_EDITING_PROFILE)

        # Remove keyboard
        markup = types.ReplyKeyboardRemove()
        send_message(
            message.chat.id, get_text("phone_updated", language), reply_markup=markup
        )

        # Show updated profile
        show_profile(message, language)

    # Handle regular registration contact (existing functionality)
    elif current_step == STEP_PHONE_REQUESTED and message.contact:
        phone = message.contact.phone_number
        center = get_current_center()
        user = create_or_update_user(user_id=user_id, phone=phone, center=center)

        if user:
            current_step = get_user_step(user_id)
            if current_step == STEP_PHONE_REQUESTED:
                contact_text = get_text("phone_received", language).format(phone=phone)
                send_message(message.chat.id, contact_text)

                # Check if user already has a branch selected
                bot_user = get_bot_user(user_id, center)
                if bot_user and bot_user.branch:
                    # User already has a branch, complete registration
                    bot_user.is_active = True
                    bot_user.step = STEP_REGISTERED
                    bot_user.save()
                    
                    complete_text = get_text("registration_complete", language)
                    send_message(message.chat.id, complete_text)
                    show_main_menu(message, language)
                else:
                    # No branch yet, show branch selection
                    show_branch_selection(message, language)
            elif current_step == STEP_EDITING_PHONE:
                send_message(
                    message.chat.id,
                    get_text("phone_updated", language),
                    reply_markup=types.ReplyKeyboardRemove(),
                )
                show_profile(message, language)
        else:
            send_message(
                message.chat.id,
                "translation:error_processing_contact",
            )


def show_main_menu(message, language):
    # Handle both direct messages and callback messages
    if hasattr(message, 'from_user') and message.from_user:
        user_id = message.from_user.id
    else:
        user_id = message.chat.id
    
    update_user_step(user_id, STEP_REGISTERED)
    
    # Check if branch has pricelist enabled
    user = get_bot_user(user_id)
    should_show_pricelist = False
    if user and user.branch and user.branch.show_pricelist:
        should_show_pricelist = True
    
    markup = types.ReplyKeyboardMarkup(
        resize_keyboard=True, row_width=2, one_time_keyboard=True
    )
    if language == "uz":
        btn1 = types.KeyboardButton("🛍️ Hizmatdan foydalanish")
        btn2 = types.KeyboardButton("📋 Arizalarim")
        btn3 = types.KeyboardButton("👤 Profil")
        btn4 = types.KeyboardButton("ℹ️ Biz haqimizda")
        btn5 = types.KeyboardButton("❓ Yordam")
        btn_pricelist = types.KeyboardButton("💰 Narxlar ro'yxati")
    elif language == "ru":
        btn1 = types.KeyboardButton("🛍️ Воспользоваться услугой")
        btn2 = types.KeyboardButton("📋 Мои заявки")
        btn3 = types.KeyboardButton("👤 Профиль")
        btn4 = types.KeyboardButton("ℹ️ О нас")
        btn5 = types.KeyboardButton("❓ Помощь")
        btn_pricelist = types.KeyboardButton("💰 Прайс-лист")
    else:  # English
        btn1 = types.KeyboardButton("🛍️ Use Service")
        btn2 = types.KeyboardButton("📋 My Orders")
        btn3 = types.KeyboardButton("👤 Profile")
        btn4 = types.KeyboardButton("ℹ️ About Us")
        btn5 = types.KeyboardButton("❓ Help")
        btn_pricelist = types.KeyboardButton("💰 Price List")
    markup.add(btn1, btn2)
    markup.add(btn3, btn4)
    if should_show_pricelist:
        markup.add(btn5, btn_pricelist)
    else:
        markup.add(btn5)
    welcome_text = get_text("main_menu_welcome", language)
    bot.send_message(message.chat.id, welcome_text, reply_markup=markup)


@bot.message_handler(
    func=lambda message: message.text
    in [
        "🛍️ Hizmatdan foydalanish",
        "🛍️ Воспользоваться услугой",
        "🛍️ Use Service",
        "📋 Arizalarim",
        "📋 Мои заявки",
        "📋 My Orders",
        "👤 Profil",
        "👤 Profile",
        "👤 Профиль",
        "ℹ️ Biz haqimizda",
        "ℹ️ О нас",
        "ℹ️ About Us",
        "❓ Yordam",
        "❓ Помощь",
        "❓ Help",
        "💰 Narxlar ro'yxati",
        "💰 Прайс-лист",
        "💰 Price List",
    ]
)
def handle_main_menu(message):
    from accounts.models import AdditionalInfo, BotUser

    user_id = message.from_user.id
    language = get_user_language(user_id)

    # Get AdditionalInfo for user's branch (with fallback)
    user = get_bot_user(user_id)
    if user:
        additional_info = AdditionalInfo.get_for_user(user)
    else:
        additional_info = AdditionalInfo.get_for_branch(None)

    if (
        "Hizmatdan foydalanish" in message.text
        or "Воспользоваться услугой" in message.text
        or "Use Service" in message.text
    ):
        show_categorys(message, language)
    elif (
        "Arizalarim" in message.text
        or "Мои заявки" in message.text
        or "My Orders" in message.text
    ):
        show_user_orders(message, language)
    elif (
        "Profil" in message.text
        or "Profile" in message.text
        or "Профиль" in message.text
    ):
        try:
            bot.delete_message(message.chat.id, message.message_id)
        except Exception as e:
            logger.debug(f" Could not delete profile button message: {e}")
        show_profile(message, language)
    elif (
        "Biz haqimizda" in message.text
        or "О нас" in message.text
        or "About Us" in message.text
    ):
        # Get about us text based on language using translated field
        about_content = additional_info.get_translated_field('about_us', language) if additional_info else ""
        
        if language == "uz":
            about_text = "ℹ️ <b>Biz haqimizda</b>\n\n"
            if about_content:
                about_text += about_content
            else:
                about_text += "📞 Savollaringiz bo'lsa, admin bilan bog'laning\n🌐 Kompaniyamiz haqida ko'proq ma'lumot tez kunda qo'shiladi!"
        elif language == "ru":
            about_text = "ℹ️ <b>О нас</b>\n\n"
            if about_content:
                about_text += about_content
            else:
                about_text += "📞 Если у вас есть вопросы, свяжитесь с администратором\n🌐 Информация о нашей компании будет добавлена в ближайшее время!"
        else:  # English
            about_text = "ℹ️ <b>About Us</b>\n\n"
            if about_content:
                about_text += about_content
            else:
                about_text += "📞 If you have questions, contact administrator\n🌐 Information about our company will be added soon!"

        send_message(message.chat.id, about_text, parse_mode="HTML")
        show_main_menu(message, language)

    elif "Yordam" in message.text or "Помощь" in message.text or "Help" in message.text:
        # Get help text based on language using translated field
        help_content = additional_info.get_translated_field('help_text', language) if additional_info else ""
        
        if language == "uz":
            help_text = "❓ <b>Yordam</b>\n\n"
            if help_content:
                help_text += help_content
            else:
                help_text += "📞 Savollaringiz bo'lsa, admin bilan bog'laning\n🌐 Til o'zgartirish: /start\n📋 Buyurtma berish: Hizmatdan foydalanish"
        elif language == "ru":
            help_text = "❓ <b>Помощь</b>\n\n"
            if help_content:
                help_text += help_content
            else:
                help_text += "📞 Если у вас есть вопросы, свяжитесь с администратором\n🌐 Сменить язык: /start\n📋 Сделать заказ: Воспользоваться услугой"
        else:  # English
            help_text = "❓ <b>Help</b>\n\n"
            if help_content:
                help_text += help_content
            else:
                help_text += "📞 If you have questions, contact administrator\n🌐 Change language: /start\n📋 Place order: Use Service"

        send_message(message.chat.id, help_text, parse_mode="HTML")
        show_main_menu(message, language)

    elif (
        "Narxlar ro'yxati" in message.text
        or "Прайс-лист" in message.text
        or "Price List" in message.text
    ):
        show_pricelist(message, language)


def show_pricelist(message, language):
    """Show price list for the user's branch"""
    from services.models import Category, Product
    
    user_id = message.from_user.id
    user = get_bot_user(user_id)
    
    if not user or not user.branch:
        send_message(message.chat.id, get_text("pricelist_empty", language), parse_mode="HTML")
        show_main_menu(message, language)
        return
    
    # Check if branch has price list enabled
    if not user.branch.show_pricelist:
        send_message(message.chat.id, get_text("pricelist_empty", language), parse_mode="HTML")
        show_main_menu(message, language)
        return
    
    # Determine if user is agency (B2B) or regular (B2C)
    is_agency = user.is_agency if hasattr(user, 'is_agency') else False
    
    # Get categories for this branch
    categories = Category.objects.filter(
        branch=user.branch,
        is_active=True
    ).prefetch_related('product_set').order_by('name')
    
    # Build price list text with creative formatting
    if language == 'uz':
        pricelist_text = "╔══════════════════════╗\n"
        pricelist_text += "   💰 <b>NARXLAR RO'YXATI</b> 💰\n"
        pricelist_text += "╚══════════════════════╝\n\n"
        pricelist_text += f"🏢 <b>{user.branch.name}</b>\n"
        pricelist_text += "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n\n"
    elif language == 'ru':
        pricelist_text = "╔══════════════════════╗\n"
        pricelist_text += "     💰 <b>ПРАЙС-ЛИСТ</b> 💰\n"
        pricelist_text += "╚══════════════════════╝\n\n"
        pricelist_text += f"🏢 <b>{user.branch.name}</b>\n"
        pricelist_text += "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n\n"
    else:
        pricelist_text = "╔══════════════════════╗\n"
        pricelist_text += "     💰 <b>PRICE LIST</b> 💰\n"
        pricelist_text += "╚══════════════════════╝\n\n"
        pricelist_text += f"🏢 <b>{user.branch.name}</b>\n"
        pricelist_text += "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n\n"
    
    # Add B2B/B2C note with icons
    if is_agency:
        if language == 'uz':
            pricelist_text += "💼 <i>Agentlik narxlari</i> 🔥\n\n"
        elif language == 'ru':
            pricelist_text += "💼 <i>Цены для агентств</i> 🔥\n\n"
        else:
            pricelist_text += "💼 <i>Agency prices</i> 🔥\n\n"
    else:
        if language == 'uz':
            pricelist_text += "👤 <i>Mijozlar uchun narxlar</i> ✨\n\n"
        elif language == 'ru':
            pricelist_text += "👤 <i>Цены для клиентов</i> ✨\n\n"
        else:
            pricelist_text += "👤 <i>Customer prices</i> ✨\n\n"
    
    has_products = False
    category_icons = ['📁', '📂', '🗂', '📋', '📑', '🗃']
    
    for idx, category in enumerate(categories):
        products = category.product_set.filter(is_active=True).order_by('name')
        
        if products.exists():
            has_products = True
            # Get category name based on language
            category_name = get_translated_field(category, 'name', language)
            
            # Determine charging type for this category
            is_dynamic = category.charging == 'dynamic'
            
            # Use rotating icons for categories
            cat_icon = category_icons[idx % len(category_icons)]
            
            pricelist_text += f"┌{'─' * 20}┐\n"
            pricelist_text += f"│ {cat_icon} <b>{category_name.upper()}</b>\n"
            pricelist_text += f"└{'─' * 20}┘\n"
            
            for product in products:
                # Get product name based on language
                product_name = get_translated_field(product, 'name', language)
                
                # Get prices based on user type (agency vs regular)
                if is_agency:
                    first_price = product.agency_first_page_price
                    other_price = product.agency_other_page_price
                else:
                    first_price = product.ordinary_first_page_price
                    other_price = product.ordinary_other_page_price
                
                # Format prices
                first_formatted = "{:,.0f}".format(first_price).replace(",", " ")
                other_formatted = "{:,.0f}".format(other_price).replace(",", " ")
                
                if is_dynamic:
                    # Dynamic pricing - show first page and other pages prices
                    if language == 'uz':
                        pricelist_text += f"\n  📄 <b>{product_name}</b>\n"
                        pricelist_text += f"     ├ 1️⃣ sahifa: <code>{first_formatted}</code> so'm\n"
                        pricelist_text += f"     ├ ➕ keyingi: <code>{other_formatted}</code> so'm\n"
                        if product.estimated_days:
                            pricelist_text += f"     └ ⏰ ~{product.estimated_days} kun\n"
                    elif language == 'ru':
                        pricelist_text += f"\n  📄 <b>{product_name}</b>\n"
                        pricelist_text += f"     ├ 1️⃣ стр.: <code>{first_formatted}</code> сум\n"
                        pricelist_text += f"     ├ ➕ далее: <code>{other_formatted}</code> сум\n"
                        if product.estimated_days:
                            pricelist_text += f"     └ ⏰ ~{product.estimated_days} дн.\n"
                    else:
                        pricelist_text += f"\n  📄 <b>{product_name}</b>\n"
                        pricelist_text += f"     ├ 1️⃣ page: <code>{first_formatted}</code> sum\n"
                        pricelist_text += f"     ├ ➕ next: <code>{other_formatted}</code> sum\n"
                        if product.estimated_days:
                            pricelist_text += f"     └ ⏰ ~{product.estimated_days} days\n"
                else:
                    # Static pricing - single price per document
                    if language == 'uz':
                        pricelist_text += f"\n  📄 {product_name}\n"
                        pricelist_text += f"     ├ 💵 <code>{first_formatted}</code> so'm"
                        if product.estimated_days:
                            pricelist_text += f"\n     └ ⏰ ~{product.estimated_days} kun\n"
                        else:
                            pricelist_text += "\n"
                    elif language == 'ru':
                        pricelist_text += f"\n  📄 {product_name}\n"
                        pricelist_text += f"     ├ 💵 <code>{first_formatted}</code> сум"
                        if product.estimated_days:
                            pricelist_text += f"\n     └ ⏰ ~{product.estimated_days} дн.\n"
                        else:
                            pricelist_text += "\n"
                    else:
                        pricelist_text += f"\n  📄 {product_name}\n"
                        pricelist_text += f"     ├ 💵 <code>{first_formatted}</code> sum"
                        if product.estimated_days:
                            pricelist_text += f"\n     └ ⏰ ~{product.estimated_days} days\n"
                        else:
                            pricelist_text += "\n"
            
            pricelist_text += "\n"
    
    if not has_products:
        pricelist_text = get_text("pricelist_empty", language)
    else:
        # Add creative footer
        pricelist_text += "═══════════════════════\n"
        if language == 'uz':
            pricelist_text += "📞 <b>Savollar bormi?</b>\n"
            pricelist_text += "💬 Biz bilan bog'laning!\n"
            pricelist_text += "═══════════════════════\n"
            pricelist_text += "🚀 <i>Tez • Sifatli • Ishonchli</i>"
        elif language == 'ru':
            pricelist_text += "📞 <b>Есть вопросы?</b>\n"
            pricelist_text += "💬 Свяжитесь с нами!\n"
            pricelist_text += "═══════════════════════\n"
            pricelist_text += "🚀 <i>Быстро • Качественно • Надежно</i>"
        else:
            pricelist_text += "📞 <b>Have questions?</b>\n"
            pricelist_text += "💬 Contact us!\n"
            pricelist_text += "═══════════════════════\n"
            pricelist_text += "🚀 <i>Fast • Quality • Reliable</i>"
    
    send_message(message.chat.id, pricelist_text, parse_mode="HTML")
    show_main_menu(message, language)


def show_user_orders(message, language):
    """Show all orders for the current user"""
    user_id = message.from_user.id

    try:
        from accounts.models import AdditionalInfo
        from orders.models import Order

        user = get_bot_user(user_id)
        if not user:
            send_message(message.chat.id, get_text("error_general", language))
            return

        # Get all orders for this user
        orders = Order.objects.filter(bot_user=user).order_by("-id")

        if not orders:
            # No orders found
            if language == "uz":
                no_orders_text = "📋 Hozircha arizalaringiz yo'q\n\n"
                no_orders_text += (
                    '📝 Buyurtma berish uchun "🛍️ Hizmatdan foydalanish" ni bosing'
                )
            elif language == "ru":
                no_orders_text = "📋 У вас пока нет заявок\n\n"
                no_orders_text += (
                    '📝 Чтобы сделать заказ, нажмите "🛍️ Воспользоваться услугой"'
                )
            else:  # English
                no_orders_text = "📋 You have no orders yet\n\n"
                no_orders_text += '📝 To place an order, press "🛍️ Use Service"'

            send_message(message.chat.id, no_orders_text)
            show_main_menu(message, language)
            return

        # Show orders individually without inline buttons
        for order in orders:
            # Determine charging type
            is_dynamic = order.product.category.charging == "dynamic"

            # Calculate pricing based on user type
            if user.is_agency:
                first_page_price = order.product.agency_first_page_price
                other_page_price = order.product.agency_other_page_price
            else:
                first_page_price = order.product.ordinary_first_page_price
                other_page_price = order.product.ordinary_other_page_price

            # Calculate total price
            if is_dynamic:
                if order.total_pages == 1:
                    total_price = first_page_price
                else:
                    total_price = first_page_price + (
                        other_page_price * (order.total_pages - 1)
                    )
            else:
                total_price = first_page_price

            # Order status - check if order is completed first
            if order.is_active:
                # Order is completed
                if order.payment_type == "cash":
                    status_text = (
                        "🟡 Joyida (naqd pul)"
                        if language == "uz"
                        else (
                            "🟡 На месте (наличными)"
                            if language == "ru"
                            else "🟡 On place (cash)"
                        )
                    )
                    status_emoji = "🟡"
                elif order.payment_type == "card":
                    if order.recipt:
                        status_text = (
                            "✅ Chek yuklandi"
                            if language == "uz"
                            else (
                                "✅ Чек загружен"
                                if language == "ru"
                                else "✅ Receipt uploaded"
                            )
                        )
                        status_emoji = "✅"
                    else:
                        status_text = (
                            "💳 Kartaga o'tkazish"
                            if language == "uz"
                            else (
                                "💳 Перевод на карту"
                                if language == "ru"
                                else "💳 Card Transfer"
                            )
                        )
                        status_emoji = "💳"
                else:
                    status_text = (
                        "✅ Yakunlandi"
                        if language == "uz"
                        else "✅ Выполнен" if language == "ru" else "✅ Completed"
                    )
                    status_emoji = "✅"
            else:
                # Order is still pending
                status_text = (
                    "⏳ Kutilmoqda"
                    if language == "uz"
                    else "⏳ В ожидании" if language == "ru" else "⏳ Pending"
                )
                status_emoji = "⏳"

            # Create order text
            if language == "uz":
                order_text = f"📄 <b>Buyurtma #{order.id}</b>\n\n"
                order_text += f"📊 Xizmat: {get_translated_field(order.product.category, 'name', 'uz')}\n"
                order_text += (
                    f"📄 Hujjat: {get_translated_field(order.product, 'name', 'uz')}\n"
                )
                order_text += f"📑 Sahifalar: {order.total_pages}\n"
                if is_dynamic:
                    order_text += f"💰 1-sahifa narxi: {first_page_price:,.0f} so'm\n"
                    if order.total_pages > 1:
                        order_text += (
                            f"💰 Qolgan sahifalar: {other_page_price:,.0f} so'm\n"
                        )
                order_text += f"💵 Jami: {total_price:,.0f} so'm\n"
                order_text += f"{status_emoji} Holat: {status_text}\n"
                order_text += f"📅 Sana: {timezone.localtime(order.created_at).strftime('%d.%m.%Y %H:%M')}\n"
            elif language == "ru":
                order_text = f"📄 <b>Заказ #{order.id}</b>\n\n"
                order_text += f"📊 Услуга: {get_translated_field(order.product.category, 'name', 'ru')}\n"
                order_text += f"📄 Документ: {get_translated_field(order.product, 'name', 'ru')}\n"
                order_text += f"📑 Страниц: {order.total_pages}\n"
                if is_dynamic:
                    order_text += f"💰 Цена 1-й страницы: {first_page_price:,.0f} сум\n"
                    if order.total_pages > 1:
                        order_text += (
                            f"💰 Остальные страницы: {other_page_price:,.0f} сум\n"
                        )
                order_text += f"💵 Всего: {total_price:,.0f} сум\n"
                order_text += f"{status_emoji} Статус: {status_text}\n"
                order_text += f"📅 Дата: {timezone.localtime(order.created_at).strftime('%d.%m.%Y %H:%M')}\n"
            else:  # English
                order_text = f"📄 <b>Order #{order.id}</b>\n\n"
                order_text += f"📊 Service: {get_translated_field(order.product.category, 'name', 'en')}\n"
                order_text += f"📄 Document: {get_translated_field(order.product, 'name', 'en')}\n"
                order_text += f"📑 Pages: {order.total_pages}\n"
                if is_dynamic:
                    order_text += f"💰 1st page price: {first_page_price:,.0f} sum\n"
                    if order.total_pages > 1:
                        order_text += f"💰 Other pages: {other_page_price:,.0f} sum\n"
                order_text += f"💵 Total: {total_price:,.0f} sum\n"
                order_text += f"{status_emoji} Status: {status_text}\n"
                order_text += f"📅 Date: {timezone.localtime(order.created_at).strftime('%d.%m.%Y %H:%M')}\n"

            # Add payment info if partially paid
            if order.received > 0 or order.remaining > 0:
                if language == "uz":
                    order_text += f"\n💰 To'langan: {order.received:,.0f} so'm\n"
                    order_text += f"💳 Qoldiq: {order.remaining:,.0f} so'm\n"
                elif language == "ru":
                    order_text += f"\n💰 Оплачено: {order.received:,.0f} сум\n"
                    order_text += f"💳 Остаток: {order.remaining:,.0f} сум\n"
                else:
                    order_text += f"\n💰 Paid: {order.received:,.0f} sum\n"
                    order_text += f"💳 Remaining: {order.remaining:,.0f} sum\n"

            # Check if order has unpaid balance
            has_remaining = order.remaining > 0 and not order.is_fully_paid
            
            # Create inline keyboard for Pay button if unpaid
            if has_remaining:
                markup = types.InlineKeyboardMarkup()
                pay_text = get_text("btn_pay", language)
                markup.add(types.InlineKeyboardButton(
                    text=pay_text,
                    callback_data=f"pay_order_{order.id}"
                ))
                send_message(
                    chat_id=message.chat.id,
                    text=order_text,
                    parse_mode="HTML",
                    reply_markup=markup
                )
            else:
                send_message(
                    chat_id=message.chat.id,
                    text=order_text,
                    parse_mode="HTML",
                )

        # After showing all orders, display main menu
        show_main_menu(message, language)

    except Exception as e:
        logger.error(f" Failed to show user orders: {e}")
        import traceback

        traceback.print_exc()
        send_message(message.chat.id, get_text("error_general", language))
        show_main_menu(message, language)


# Payment callback handler
@bot.callback_query_handler(func=lambda call: call.data.startswith("pay_order_"))
def handle_pay_order(call):
    """Handle pay order button click"""
    from orders.models import Order
    
    user_id = call.from_user.id
    language = get_user_language(user_id)
    order_id = call.data.replace("pay_order_", "")
    
    try:
        order = Order.objects.get(id=order_id)
        user = get_bot_user(user_id)
        
        # Verify this order belongs to this user
        if order.bot_user_id != user.id:
            bot.answer_callback_query(call.id, get_text("error_general", language))
            return
        
        # Store order in user session for receipt upload
        if user_id not in uploaded_files:
            uploaded_files[user_id] = {}
        uploaded_files[user_id]["pending_payment_order_id"] = order_id
        update_user_step(user_id, STEP_AWAITING_RECEIPT)
        
        # Get bank card info from AdditionalInfo
        from accounts.models import AdditionalInfo
        additional_info = AdditionalInfo.get_for_user(user)
        
        # Build payment instructions
        total_due = order.total_due
        received = order.received or 0
        remaining = order.remaining
        
        # Build text using translation keys
        text = get_text("payment_title", language) + "\n\n"
        text += f"{get_text('payment_order', language)}: #{order.id}\n"
        text += f"{get_text('payment_total_price', language)}: {total_due:,.0f} so'm\n"
        text += f"{get_text('payment_paid', language)}: {received:,.0f} so'm\n"
        text += f"{get_text('payment_remaining', language)}: <b>{remaining:,.0f} so'm</b>\n\n"
        
        if additional_info and additional_info.bank_card:
            text += f"{get_text('payment_card_number', language)}:\n<code>{additional_info.bank_card}</code>\n"
            if additional_info.holder_name:
                text += f"{get_text('payment_card_holder', language)}: {additional_info.holder_name}\n"
            text += "\n"
        else:
            text += get_text("payment_card_not_found", language) + "\n\n"
        
        text += get_text("payment_send_receipt", language) + "\n"
        text += get_text("payment_receipt_format", language)
        
        # Create cancel button
        markup = types.InlineKeyboardMarkup()
        cancel_text = get_text("btn_back_to_orders", language)
        markup.add(types.InlineKeyboardButton(
            text=cancel_text,
            callback_data="cancel_payment"
        ))
        
        bot.answer_callback_query(call.id)
        send_message(
            chat_id=call.message.chat.id,
            text=text,
            parse_mode="HTML",
            reply_markup=markup
        )
        
    except Order.DoesNotExist:
        bot.answer_callback_query(call.id, get_text("error_order_not_found", language))
    except Exception as e:
        logger.error(f" handle_pay_order: {e}")
        bot.answer_callback_query(call.id, get_text("error_general", language))


@bot.callback_query_handler(func=lambda call: call.data == "cancel_payment")
def handle_cancel_payment(call):
    """Cancel payment and return to orders"""
    user_id = call.from_user.id
    language = get_user_language(user_id)
    
    # Clear payment state
    if user_id in uploaded_files:
        uploaded_files[user_id].pop("pending_payment_order_id", None)
    update_user_step(user_id, STEP_REGISTERED)
    
    bot.answer_callback_query(call.id)
    
    # Delete the payment message
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except:
        pass
    
    show_main_menu(call.message, language)


def show_profile(message, language):
    """Show user profile with edit options

    Args:
        message: Can be a Message, CallbackQuery, or other object with user info
        language: User's language preference
    """
    # Initialize variables
    chat_id = None
    user_id = None
    from_user = None

    # Handle different types of message objects
    if hasattr(message, "message") and hasattr(
        message.message, "chat"
    ):  # CallbackQuery
        chat_id = message.message.chat.id
        from_user = getattr(message, "from_user", None) or getattr(
            message, "from", None
        )
    elif hasattr(message, "chat") and hasattr(message.chat, "id"):  # Message
        chat_id = message.chat.id
        from_user = getattr(message, "from_user", None) or getattr(
            message, "from", None
        )

    # If we couldn't get chat_id from the message, try to get it from user_data
    if chat_id is None and hasattr(message, "chat_id"):
        chat_id = message.chat_id

    # If we still don't have a chat_id, we can't proceed
    if chat_id is None:
        logger.error("Could not determine chat_id in show_profile")
        return

    # Get user info with fallbacks
    if from_user is None:
        # Try to get user info from message if available
        from_user = getattr(message, "from_user", None) or getattr(
            message, "from", None
        )

    # If we have from_user, get the user_id
    if from_user is not None:
        user_id = getattr(from_user, "id", None) or getattr(from_user, "user_id", None)

    # If we still don't have a user_id, use the chat_id as user_id
    if user_id is None:
        user_id = chat_id
        logger.warning(f" Using chat_id as user_id: {user_id}")

    # Get username and name with fallbacks
    username = ""
    name = f"User {user_id}"

    if from_user is not None:
        username = getattr(from_user, "username", "") or ""
        name = (
            getattr(from_user, "first_name", "")
            or getattr(from_user, "name", "")
            or name
        )

    try:
        from accounts.models import BotUser

        # Get current center for multi-tenant support
        center = get_current_center()

        # Try to get user, create if doesn't exist
        user, created = BotUser.objects.get_or_create(
            user_id=user_id,
            center=center,
            defaults={
                "username": username,
                "name": name,
                "language": language,
                "phone": "",
                "is_active": False,
                "step": STEP_REGISTERED,
            },
        )

        if created:
            logger.debug(f" Created new user: {user_id}")

        # Create profile text using translation keys
        branch_name = user.branch.name if user.branch else "—"
        lang_name = get_text(f"language_name_{user.language}", language)
        status_text = get_text("status_active", language) if user.is_active else get_text("status_inactive", language)
        
        profile_text = get_text("profile_title", language) + "\n"
        
        # Add agency badge if user is an agency
        if user.is_agency:
            profile_text += get_text("profile_agency_badge", language) + "\n"
        
        profile_text += "\n"
        profile_text += f"{get_text('profile_name', language)}: {user.name}\n"
        profile_text += f"{get_text('profile_phone', language)}: {user.phone}\n"
        profile_text += f"{get_text('profile_branch', language)}: {branch_name}\n"
        profile_text += f"{get_text('profile_language', language)}: {lang_name}\n"
        profile_text += f"{get_text('profile_status', language)}: {status_text}\n"
        profile_text += f"{get_text('profile_joined', language)}: {timezone.localtime(user.created_at).strftime('%d.%m.%Y')}\n\n"
        profile_text += get_text("profile_edit_hint", language)

        # Create inline keyboard with edit options
        markup = types.InlineKeyboardMarkup(row_width=2)
        edit_name_button = types.InlineKeyboardButton(
            text=get_text("edit_name", language), callback_data="edit_name"
        )
        edit_phone_button = types.InlineKeyboardButton(
            text=get_text("edit_phone", language), callback_data="edit_phone"
        )
        edit_branch_button = types.InlineKeyboardButton(
            text=get_text("change_branch", language), 
            callback_data="edit_branch"
        )
        edit_language_button = types.InlineKeyboardButton(
            text=get_text("edit_language", language), callback_data="edit_language"
        )
        back_button = types.InlineKeyboardButton(
            text=get_text("back_to_menu", language), callback_data="main_menu"
        )

        markup.add(edit_name_button, edit_phone_button)
        markup.add(edit_branch_button, edit_language_button)
        markup.add(back_button)

        send_message(
            chat_id=chat_id,
            text=profile_text,
            reply_markup=markup,
            parse_mode="HTML",
        )

    except Exception as e:
        logger.error(f" Failed to show profile: {e}")
        import traceback

        traceback.print_exc()
        
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
        back_button = types.KeyboardButton(text=get_text("back_to_menu", language))
        markup.add(back_button)

        send_message(chat_id, get_text("error_general", language), reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == "edit_profile")
def handle_profile_actions(call):
    show_edit_profile_menu(call.message)


def show_edit_profile_menu(message):
    user_id = message.chat.id
    language = get_user_language(user_id)
    update_user_step(user_id, STEP_EDITING_PROFILE)

    markup = types.InlineKeyboardMarkup(row_width=2)
    edit_name_button = types.InlineKeyboardButton(
        text=get_text("edit_name", language), callback_data="edit_name"
    )
    edit_phone_button = types.InlineKeyboardButton(
        text=get_text("edit_phone", language), callback_data="edit_phone"
    )
    edit_language_button = types.InlineKeyboardButton(
        text=get_text("edit_language", language), callback_data="edit_language"
    )
    back_button = types.InlineKeyboardButton(
        text=get_text("back_to_menu", language), callback_data="main_menu"
    )

    markup.add(edit_name_button, edit_phone_button)
    markup.add(edit_language_button)
    markup.add(back_button)

    edit_text = get_text("edit_profile_menu", language)
    send_message(message.chat.id, edit_text, reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == "edit_name")
def handle_edit_name_request(call):
    user_id = call.message.chat.id
    language = get_user_language(user_id)
    update_user_step(user_id, STEP_EDITING_NAME)
    bot.send_message(call.message.chat.id, get_text("enter_new_name", language))


@bot.callback_query_handler(func=lambda call: call.data == "edit_phone")
def handle_edit_phone_request(call):
    user_id = call.message.chat.id
    language = get_user_language(user_id)
    update_user_step(user_id, STEP_EDITING_PHONE)

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    contact_btn = types.KeyboardButton(
        get_text("phone_button", language), request_contact=True
    )
    markup.add(contact_btn)

    bot.send_message(
        call.message.chat.id, get_text("enter_new_phone", language), reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data == "edit_branch")
def handle_edit_branch_request(call):
    """Show branch selection for changing preferred branch"""
    user_id = call.from_user.id
    language = get_user_language(user_id)
    
    center = get_current_center()
    if not center:
        bot.answer_callback_query(call.id, "Configuration error")
        return
    
    branches = get_center_branches(center)
    
    if not branches:
        bot.answer_callback_query(call.id, "No branches available")
        return
    
    # Build branch selection message
    if language == "uz":
        header = "🏢 <b>Filialni tanlang</b>\n\nQuyidagi filiallardan birini tanlang:"
    elif language == "ru":
        header = "🏢 <b>Выберите филиал</b>\n\nВыберите один из филиалов ниже:"
    else:
        header = "🏢 <b>Select Branch</b>\n\nPlease select one of the branches below:"
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    # Get current user's branch
    current_branch_id = None
    user = get_bot_user(user_id)
    if user and user.branch:
        current_branch_id = user.branch.id
    
    for branch in branches:
        # Mark current branch with checkmark
        if branch.id == current_branch_id:
            button_text = f"✅ {branch.name}"
        else:
            button_text = f"📍 {branch.name}"
        
        markup.add(types.InlineKeyboardButton(
            text=button_text,
            callback_data=f"change_branch_{branch.id}"
        ))
    
    # Add back button
    back_text = "🔙 " + ("Orqaga" if language == "uz" else "Назад" if language == "ru" else "Back")
    markup.add(types.InlineKeyboardButton(text=back_text, callback_data="back_to_profile"))
    
    # Build detailed branch info
    branch_info = header + "\n\n"
    for branch in branches:
        if branch.id == current_branch_id:
            branch_info += f"✅ <b>{branch.name}</b> (joriy)\n" if language == "uz" else f"✅ <b>{branch.name}</b> (текущий)\n" if language == "ru" else f"✅ <b>{branch.name}</b> (current)\n"
        else:
            branch_info += f"🏢 <b>{branch.name}</b>\n"
        if branch.address:
            branch_info += f"   📍 {branch.address}\n"
        branch_info += "\n"
    
    try:
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=branch_info,
            reply_markup=markup,
            parse_mode="HTML"
        )
    except:
        send_message(call.message.chat.id, branch_info, reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith("change_branch_"))
def handle_change_branch(call):
    """Handle branch change from profile"""
    user_id = call.from_user.id
    language = get_user_language(user_id)
    
    try:
        branch_id = int(call.data.split("_")[2])
        from organizations.models import Branch
        
        branch = Branch.objects.get(id=branch_id)
        
        # Update user's branch
        user = get_bot_user(user_id)
        if not user:
            bot.answer_callback_query(call.id, "User not found")
            return
        user.branch = branch
        user.save()
        
        # Confirm change
        if language == "uz":
            confirm_text = f"✅ Filial <b>{branch.name}</b> ga o'zgartirildi."
        elif language == "ru":
            confirm_text = f"✅ Филиал изменен на <b>{branch.name}</b>."
        else:
            confirm_text = f"✅ Branch changed to <b>{branch.name}</b>."
        
        bot.answer_callback_query(call.id, confirm_text.replace("<b>", "").replace("</b>", ""))
        
        # Show updated profile
        class MessageWrapper:
            def __init__(self, chat, from_user):
                self.chat = chat
                self.from_user = from_user
        
        wrapped_message = MessageWrapper(call.message.chat, call.from_user)
        
        # Delete old message
        try:
            bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.message_id)
        except:
            pass
        
        show_profile(wrapped_message, language)
        
    except Branch.DoesNotExist:
        bot.answer_callback_query(call.id, "Branch not found")
    except BotUser.DoesNotExist:
        bot.answer_callback_query(call.id, "User not found")
    except Exception as e:
        logger.error(f" Change branch error: {e}")
        bot.answer_callback_query(call.id, "Error occurred")


@bot.callback_query_handler(func=lambda call: call.data == "edit_language")
def handle_edit_language_request(call):
    try:
        user_id = call.message.chat.id
        language = get_user_language(user_id)
        update_user_step(user_id, STEP_LANGUAGE_SELECTED)

        # Create language selection keyboard with distinct callback pattern
        markup = types.InlineKeyboardMarkup(row_width=3)
        btn1 = types.InlineKeyboardButton(
            get_text("language_uz", language), callback_data="profile_lang_uz"
        )
        btn2 = types.InlineKeyboardButton(
            get_text("language_ru", language), callback_data="profile_lang_ru"
        )
        btn3 = types.InlineKeyboardButton(
            get_text("language_en", language), callback_data="profile_lang_en"
        )
        back_btn = types.InlineKeyboardButton(
            f"🔙 {get_text('back_to_profile', language)}",
            callback_data="back_to_profile",
        )
        markup.add(btn1, btn2, btn3)
        markup.add(back_btn)

        # Use send_message helper for consistent language handling
        try:
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=get_text("choose_language", language),
                reply_markup=markup,
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error(f" Error editing message: {e}")
            # If editing fails, send a new message
            send_message(
                chat_id=user_id,
                text=get_text("choose_language", language),
                reply_markup=markup,
            )
    except Exception as e:
        logger.error(f" Error in handle_edit_language_request: {e}")
        try:
            send_message(
                call.message.chat.id,
                get_text(
                    "error_occurred", get_user_language(call.from_user.id) or "uz"
                ),
            )
        except:
            pass


@bot.callback_query_handler(func=lambda call: call.data == "back_to_profile")
def handle_back_to_profile(call):
    """Handle back to profile button from inline keyboards"""
    user_id = call.from_user.id
    language = get_user_language(user_id)
    
    try:
        bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.message_id)
    except:
        pass
    
    update_user_step(user_id, STEP_EDITING_PROFILE)
    show_profile(call.message, language)


@bot.callback_query_handler(
    func=lambda call: call.data.startswith("lang_") and call.data.count("_") >= 2
)
def handle_service_language_selection(call):
    """
    Handle language selection for services (not profile language)
    Callback data format: lang_<language_id>_<service_id>[_<doc_type_id>]
    """
    try:
        # Get the message object from the callback
        message = call.message
        user_id = message.chat.id
        language = get_user_language(user_id)

        # Extract language ID and service ID from callback data
        parts = call.data.split("_")
        if len(parts) < 3:
            logger.error(f" Invalid service language selection format: {call.data}")
            send_message(user_id, get_text("error_occurred", language))
            show_categorys(call.message, language)
            return

        try:
            lang_id = int(parts[1])
            service_id = int(parts[2])
            doc_type_id = int(parts[3]) if len(parts) > 3 else None
        except (ValueError, IndexError) as e:
            logger.error(f" Error parsing callback data {call.data}: {e}")
            send_message(user_id, get_text("error_occurred", language))
            show_categorys(call.message, language)
            return

        # Store selected service language in uploaded_files
        if user_id not in uploaded_files:
            uploaded_files[user_id] = {}
        uploaded_files[user_id]["service_id"] = service_id
        uploaded_files[user_id]["lang_id"] = lang_id

        # Store language name for summaries
        try:
            from services.models import Language

            lang_obj = Language.objects.filter(id=lang_id).first()
            if lang_obj:
                uploaded_files[user_id]["lang_name"] = lang_obj.name
        except Exception as ex:
            logger.warning(f" Could not get language name: {ex}")

        # Delete the language selection message
        try:
            bot.delete_message(chat_id=user_id, message_id=message.message_id)
        except Exception as e:
            logger.error(f" Error deleting message: {e}")

        # Show document types for the selected language and service
        show_products(
            message=message,
            language=language,
            service_id=service_id,
            lang_id=lang_id,
            doc_type_id=doc_type_id,
        )

    except Exception as e:
        logger.error(f" Error in handle_service_language_selection: {e}")
        # Get user language again in case of error
        user_id = call.message.chat.id
        language = get_user_language(user_id)

        try:
            send_message(user_id, get_text("error_occurred", language))
            show_categorys(call.message, language)
        except Exception as inner_e:
            logger.error(f" Failed to handle error: {inner_e}")
            # If we can't handle the error, just log it
            pass
        print(f"Unexpected error in handle_service_language_selection: {e}")


# Add a new handler for profile language updates
@bot.callback_query_handler(func=lambda call: call.data.startswith("profile_lang_"))
def handle_profile_language_update(call):
    """Handle profile language updates"""
    try:
        user_id = call.from_user.id

        # Extract language code from callback data
        try:
            language = call.data.split("_")[2]  # Format: profile_lang_<lang_code>
            if language not in ["uz", "ru", "en"]:
                raise ValueError(f"Invalid language code: {language}")
        except (IndexError, ValueError) as e:
            logger.error(f" Invalid language selection: {e}")
            language = "uz"  # Default to Uzbek if language is invalid

        # Update the user's profile language
        try:
            from accounts.models import BotUser
            
            # Get current center for multi-tenant support
            center = get_current_center()

            user, created = BotUser.objects.get_or_create(
                user_id=user_id,
                center=center,
                defaults={
                    "username": call.from_user.username,
                    "language": language,
                    "name": call.from_user.first_name or "User",
                    "phone": "",
                },
            )

            if not created:
                user.language = language
                user.save()

            logger.debug(f" Updated profile language for user {user_id} to {language}")

        except Exception as e:
            logger.error(f" Error updating user {user_id} language: {e}")
            try:
                # Try to create the user if update failed
                center = get_current_center()
                create_or_update_user(
                    user_id=user_id, username=call.from_user.username, language=language, center=center
                )
            except Exception as inner_e:
                logger.critical(f" Failed to create user {user_id}: {inner_e}")
                language = "uz"  # Default to Uzbek as fallback

        # Delete the old message
        try:
            bot.delete_message(
                chat_id=call.message.chat.id, message_id=call.message.message_id
            )
        except Exception as e:
            logger.warning(f" Error deleting message: {e}")

        # Show profile with updated language
        try:
            show_profile(call.message, language)
        except Exception as e:
            logger.error(f" Failed to show profile after language update: {e}")
            # If showing profile fails, at least send a confirmation message
            confirmation_msg = get_text("language_updated", language)
            send_message(user_id, confirmation_msg)
            show_main_menu(call.message, language)

    except Exception as e:
        logger.critical(f" Unhandled error in handle_profile_language_update: {e}")
        # Try to recover by showing main menu in default language
        try:
            send_message(call.from_user.id, get_text("error_occurred", "uz"))
            show_main_menu(call.message, "uz")
        except:
            pass  # If even this fails, there's nothing more we can do


def show_categorys(message, language):
    # Handle both direct messages and callback messages
    if hasattr(message, 'from_user') and message.from_user:
        user_id = message.from_user.id
    else:
        user_id = message.chat.id
    
    update_user_step(user_id, STEP_SELECTING_SERVICE)
    from services.models import Category

    try:
        # Get user's branch and filter categories by that branch
        user = get_bot_user(user_id)
        if not user:
            send_message(message.chat.id, get_text("error_user_not_found", language))
            return
        
        if not user.branch:
            # No branch selected - show message to select branch first
            if language == "uz":
                no_branch_text = "⚠️ Iltimos, avval filialni tanlang.\n\nProfilga o'ting va filialni tanlang."
            elif language == "ru":
                no_branch_text = "⚠️ Пожалуйста, сначала выберите филиал.\n\nПерейдите в профиль и выберите филиал."
            else:
                no_branch_text = "⚠️ Please select a branch first.\n\nGo to Profile and select a branch."
            send_message(message.chat.id, no_branch_text)
            show_main_menu(message, language)
            return
        
        services = Category.objects.filter(branch=user.branch, is_active=True)
        
        if services.exists():
            markup = types.InlineKeyboardMarkup(row_width=2)
            for service in services:
                button = types.InlineKeyboardButton(
                    text=get_translated_field(service, "name", language),
                    callback_data=f"category_{service.id}",
                )
                markup.add(button)
            back_button = types.InlineKeyboardButton(
                text=get_text("back_to_menu", language), callback_data="main_menu"
            )
            markup.add(back_button)
            send_message(
                message.chat.id,
                get_text("select_service", language),
                reply_markup=markup,
            )
        else:
            # No services available for this branch
            if language == "uz":
                no_services_text = "📋 Hozircha bu filialda xizmatlar mavjud emas."
            elif language == "ru":
                no_services_text = "📋 В данном филиале пока нет доступных услуг."
            else:
                no_services_text = "📋 No services available for this branch yet."
            send_message(message.chat.id, no_services_text)
            show_main_menu(message, language)
    except Category.DoesNotExist:
        logger.error(f" Category query failed for user {user_id}")
        send_message(message.chat.id, get_text("error_general", language))
        show_main_menu(message, language)
    except AttributeError as e:
        logger.error(f" AttributeError in show_categorys: {e}")
        send_message(message.chat.id, get_text("error_general", language))
        show_main_menu(message, language)
    except Exception as e:
        logger.error(f" Unexpected error in show_categorys: {e}", exc_info=True)
        send_message(message.chat.id, get_text("error_general", language))
        show_main_menu(message, language)


@bot.callback_query_handler(func=lambda call: call.data == ("main_menu"))
def handle_main_menu_callback(call):
    user_id = call.from_user.id
    language = get_user_language(user_id)
    
    try:
        bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.message_id)
    except:
        pass
    
    # Create wrapper with proper from_user
    class MessageWrapper:
        def __init__(self, chat, from_user):
            self.chat = chat
            self.from_user = from_user
    
    wrapped_message = MessageWrapper(call.message.chat, call.from_user)
    show_main_menu(wrapped_message, language)


@bot.callback_query_handler(func=lambda call: call.data.startswith("category_"))
def handle_service_selection(call):
    user_id = call.from_user.id
    language = get_user_language(user_id)
    
    # Create wrapper with proper from_user for functions that need it
    class MessageWrapper:
        def __init__(self, chat, from_user, message_id=None):
            self.chat = chat
            self.from_user = from_user
            self.message_id = message_id
    
    wrapped_message = MessageWrapper(call.message.chat, call.from_user, call.message.message_id)
    
    try:
        service_id = int(call.data.split("_")[1])
        from services.models import Category

        # Delete the service selection message
        try:
            bot.delete_message(
                chat_id=call.message.chat.id, message_id=call.message.message_id
            )
        except:
            pass

        category = Category.objects.get(id=service_id)

        # Check if service has multiple languages
        if category.languages.count() > 1:
            show_available_langs(wrapped_message, language, service_id)
        else:
            # If only one language is available, use it and go directly to document types
            lang = category.languages.first()
            show_products(
                message=wrapped_message,
                language=language,
                service_id=service_id,
                lang_id=lang.id if lang else None,
            )

    except Category.DoesNotExist:
        error_msg = get_text("service_not_found", language)
        bot.send_message(call.message.chat.id, error_msg)
        show_categorys(wrapped_message, language)
    except Exception as e:
        error_msg = get_text("error_occurred", language)
        bot.send_message(call.message.chat.id, error_msg)
        print(f"Error in handle_service_selection: {e}")
        show_main_menu(wrapped_message, language)


def show_available_langs(
    message,
    language,
    service_id,
    edit_message=False,
    message_id=None,
    chat_id=None,
    back_from_upload=False,
    doc_type_id=None,
    service_id_for_back=None,
):
    """Show available languages for the selected service"""
    try:
        if chat_id is None:
            chat_id = message.chat.id
            if message_id is None and hasattr(message, "message_id"):
                message_id = message.message_id

        from services.models import Category, Language

        service = Category.objects.get(id=service_id)

        # Get available languages for this service
        available_languages = service.languages.all()

        if not available_languages.exists():
            error_msg = get_text("no_languages_available", language)
            if edit_message and message_id:
                bot.edit_message_text(
                    chat_id=chat_id, message_id=message_id, text=error_msg
                )
            else:
                bot.send_message(chat_id, error_msg)
            show_categorys(message, language)
            return

        # Create inline keyboard with language buttons
        markup = types.InlineKeyboardMarkup(row_width=2)

        for lang in available_languages:
            # Create callback data with language ID and service ID
            callback_data = f"lang_{lang.id}_{service_id}"

            # Add language button
            button = types.InlineKeyboardButton(
                text=lang.name, callback_data=callback_data
            )
            markup.add(button)

        # Add back button to return to services
        back_button = types.InlineKeyboardButton(
            text=get_text("back_to_services", language),
            callback_data=(
                f"category_{service_id}" if back_from_upload else "back_to_services"
            ),
        )
        markup.add(back_button)

        # Prepare message text
        message_text = get_text("select_document_lang", language).format(
            service_name=get_translated_field(service, "name", language)
        )

        # Send or edit message
        if edit_message and message_id:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=message_text,
                reply_markup=markup,
                parse_mode="HTML",
            )
        else:
            # Delete previous message if it exists
            if hasattr(message, "message_id"):
                try:
                    bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                except:
                    pass

            sent_message = bot.send_message(
                chat_id=chat_id,
                text=message_text,
                reply_markup=markup,
                parse_mode="HTML",
            )

            # Store message ID for later updates if needed
            user_id = message.chat.id
            if user_id not in user_data:
                user_data[user_id] = {}
            if "message_ids" not in user_data[user_id]:
                user_data[user_id]["message_ids"] = []
            user_data[user_id]["message_ids"].append(sent_message.message_id)

    except Category.DoesNotExist:
        error_msg = get_text("service_not_found", language)
        if edit_message and message_id:
            bot.edit_message_text(
                chat_id=chat_id, message_id=message_id, text=error_msg
            )
        else:
            bot.send_message(chat_id, error_msg)
        show_categorys(message, language)
    except Exception as e:
        error_msg = get_text("error_occurred", language)
        if edit_message and message_id:
            bot.edit_message_text(
                chat_id=chat_id, message_id=message_id, text=error_msg
            )
        else:
            bot.send_message(chat_id, error_msg)
        print(f"Error in show_available_langs: {e}")
        show_main_menu(message, language)


def show_products(
    message,
    language,
    service_id,
    edit_message=False,
    message_id=None,
    chat_id=None,
    back_from_upload=False,
    doc_type_id=None,
    service_id_for_back=None,
    lang_id=None,
):
    """Show document types for the selected service and language"""
    from services.models import Category, Product, Language

    # Get chat_id and message_id if not provided
    if chat_id is None:
        chat_id = message.chat.id
        if message_id is None and hasattr(message, "message_id"):
            message_id = message.message_id

    # Store selected service language in uploaded_files
    if chat_id not in uploaded_files:
        uploaded_files[chat_id] = {}
    uploaded_files[chat_id]["service_id"] = service_id
    if lang_id:
        uploaded_files[chat_id]["lang_id"] = lang_id
        try:
            from services.models import Language

            lang_obj = Language.objects.filter(id=lang_id).first()
            if lang_obj:
                uploaded_files[chat_id]["lang_name"] = lang_obj.name
        except Exception:
            pass

    # Get the service and language objects
    try:
        service = Category.objects.get(id=service_id)
        lang = Language.objects.get(id=lang_id) if lang_id else None

        # Get available document types for this service
        doc_types = Product.objects.filter(category=service, is_active=True)

        # Update user step
        update_user_step(chat_id, STEP_SELECTING_DOCUMENT)

        if not doc_types.exists():
            error_msg = get_text("no_products", language)
            if edit_message and message_id:
                bot.edit_message_text(
                    chat_id=chat_id, message_id=message_id, text=error_msg
                )
            else:
                bot.send_message(chat_id, error_msg)
            return

        # Create inline keyboard with document types
        markup = types.InlineKeyboardMarkup(row_width=1)
        for doc_type in doc_types:
            # Use the translated document type name
            button_text = get_translated_field(doc_type, "name", language)

            # Add description if available
            doc_description = get_translated_field(doc_type, "description", language)
            if doc_description:
                button_text += f" - {doc_description}"

            # Include language ID in the callback data
            callback_data = f"doc_type_{doc_type.id}_{service_id}"
            if lang_id:
                callback_data += f"_{lang_id}"

            button = types.InlineKeyboardButton(
                text=button_text, callback_data=callback_data
            )
            markup.add(button)

        # Add back button
        if service.languages.count() > 1:
            back_button = types.InlineKeyboardButton(
                text=get_text("back_to_languages", language),
                callback_data=f"category_{service_id}",
            )
        else:
            back_button = types.InlineKeyboardButton(
                text=get_text("back_to_services", language),
                callback_data="back_to_services",
            )
        markup.add(back_button)

        # Prepare message text
        message_text = get_text("select_product", language)
        if lang:
            message_text += (
                f"\n\n🌍 {get_text('selected_language', language)}: {lang.name}"
            )

        # Send or edit message
        if edit_message and message_id:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=message_text,
                reply_markup=markup,
                parse_mode="HTML",
            )
        else:
            # Delete previous message if it exists
            if hasattr(message, "message_id"):
                try:
                    bot.delete_message(chat_id=chat_id, message_id=message.message_id)
                except:
                    pass

            sent_message = bot.send_message(
                chat_id=chat_id,
                text=message_text,
                reply_markup=markup,
                parse_mode="HTML",
            )

            # Store message ID for later updates if needed
            user_id = message.chat.id
            if user_id not in user_data:
                user_data[user_id] = {}
            if "message_ids" not in user_data[user_id]:
                user_data[user_id]["message_ids"] = []
            user_data[user_id]["message_ids"].append(sent_message.message_id)

    except Category.DoesNotExist:
        error_msg = get_text("service_not_found", language)
        if edit_message and message_id:
            bot.edit_message_text(
                chat_id=chat_id, message_id=message_id, text=error_msg
            )
        else:
            bot.send_message(chat_id, error_msg)
        show_categorys(message, language)
    except Exception as e:
        error_msg = get_text("error_occurred", language)
        if edit_message and message_id:
            bot.edit_message_text(
                chat_id=chat_id, message_id=message_id, text=error_msg
            )
        else:
            bot.send_message(chat_id, error_msg)
        print(f"Error in show_products: {e}")
        show_main_menu(message, language)


@bot.callback_query_handler(func=lambda call: call.data == "back_to_services")
def handle_back_to_services(call):
    user_id = call.from_user.id
    language = get_user_language(user_id)
    
    # Create a wrapper message with proper from_user
    class MessageWrapper:
        def __init__(self, chat, from_user):
            self.chat = chat
            self.from_user = from_user
            self.message_id = call.message.message_id
    
    wrapped_message = MessageWrapper(call.message.chat, call.from_user)
    
    # Delete the current message
    try:
        bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.message_id)
    except:
        pass
    
    show_categorys(wrapped_message, language)


def show_copy_number_selection(message, language, doc_type, lang_name):
    """Show copy number selection step"""
    user_id = message.chat.id

    # Update user step
    update_user_step(user_id, STEP_SELECTING_COPY_NUMBER)

    # Delete previous message
    try:
        bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
    except:
        pass

    # Create message text
    message_text = get_text("select_copy_number", language)

    # Create inline keyboard with preset numbers and custom input
    markup = types.InlineKeyboardMarkup(row_width=3)

    # Quick select buttons for common copy numbers
    btn_0 = types.InlineKeyboardButton(text="0️⃣", callback_data="copy_num_0")
    btn_1 = types.InlineKeyboardButton(text="1️⃣", callback_data="copy_num_1")
    btn_2 = types.InlineKeyboardButton(text="2️⃣", callback_data="copy_num_2")
    btn_3 = types.InlineKeyboardButton(text="3️⃣", callback_data="copy_num_3")
    btn_4 = types.InlineKeyboardButton(text="4️⃣", callback_data="copy_num_4")
    btn_5 = types.InlineKeyboardButton(text="5️⃣", callback_data="copy_num_5")

    markup.add(btn_0, btn_1, btn_2)
    markup.add(btn_3, btn_4, btn_5)

    # Back button
    back_button = types.InlineKeyboardButton(
        text=get_text("back_to_documents", language),
        callback_data="back_to_documents_from_copy",
    )
    markup.add(back_button)

    # Send message
    bot.send_message(
        chat_id=user_id, text=message_text, reply_markup=markup, parse_mode="HTML"
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("copy_num_"))
def handle_copy_number_selection(call):
    """Handle copy number selection from inline buttons"""
    user_id = call.message.chat.id
    language = get_user_language(user_id)

    try:
        # Extract copy number from callback data
        copy_number = int(call.data.split("_")[2])

        # Validate copy number
        if copy_number < 0 or copy_number > 99:
            bot.answer_callback_query(
                call.id, get_text("invalid_copy_number", language)
            )
            return

        # Store copy number in uploaded_files
        if user_id not in uploaded_files:
            uploaded_files[user_id] = {}
        uploaded_files[user_id]["copy_number"] = copy_number

        logger.debug(f" User {user_id} selected {copy_number} copies")

        # Delete the copy number message
        try:
            bot.delete_message(chat_id=user_id, message_id=call.message.message_id)
        except:
            pass

        # Get document type info from uploaded_files
        user_data = uploaded_files.get(user_id, {})
        doc_type_id = user_data.get("doc_type_id")
        lang_id = user_data.get("lang_id")

        if not doc_type_id:
            bot.send_message(user_id, get_text("error_occurred", language))
            show_categorys(call.message, language)
            return

        # Get document type and language
        from services.models import Product, Language

        doc_type = Product.objects.get(id=doc_type_id)
        lang_name = Language.objects.get(id=lang_id).name if lang_id else ""

        # Show upload files interface
        show_upload_files_interface(
            call.message, language, doc_type, lang_name, copy_number
        )

    except Exception as e:
        logger.error(f" Failed to handle copy number selection: {e}")
        import traceback

        traceback.print_exc()
        bot.answer_callback_query(call.id, get_text("error_occurred", language))


@bot.callback_query_handler(
    func=lambda call: call.data == "back_to_documents_from_copy"
)
def handle_back_to_documents_from_copy(call):
    """Handle back button from copy number selection"""
    user_id = call.from_user.id
    language = get_user_language(user_id)

    # Get service info from uploaded_files
    user_data = uploaded_files.get(user_id, {})
    service_id = user_data.get("service_id")
    lang_id = user_data.get("lang_id")

    if service_id:
        # Delete the copy number message
        try:
            bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.message_id)
        except:
            pass

        # Show document types again
        show_products(
            message=call.message,
            language=language,
            service_id=service_id,
            lang_id=lang_id,
        )
    else:
        # Fallback to main services - create wrapper with proper from_user
        class MessageWrapper:
            def __init__(self, chat, from_user):
                self.chat = chat
                self.from_user = from_user
        
        wrapped_message = MessageWrapper(call.message.chat, call.from_user)
        show_categorys(wrapped_message, language)


def show_upload_files_interface(message, language, doc_type, lang_name, copy_number):
    """Show file upload interface after copy number is selected"""
    user_id = message.chat.id

    # Create the combined message
    message_text = f"📄 {get_translated_field(doc_type, 'name', language)}\n"
    if lang_name:
        message_text += f"🌍 {get_text('selected_language', language)}: {lang_name}\n"
    message_text += f"📋 {get_text('copy_number', language)}: {copy_number}\n\n"

    message_text += get_text("upload_files", language)
    message_text += "\n\n📎 <b>" + get_text("allowed_formats", language) + "</b>\n"
    message_text += "📄 DOC, DOCX, PDF\n"
    message_text += "🖼️ JPG, PNG, GIF, BMP, TIFF, WEBP, HEIC, HEIF"

    # Create reply keyboard
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    finish_button = types.KeyboardButton(text=get_text("finish_upload", language))
    back_button = types.KeyboardButton(text=get_text("back_to_copy_number", language))
    markup.add(finish_button, back_button)

    # Send new message
    sent_message = bot.send_message(
        chat_id=user_id,
        text=message_text,
        reply_markup=markup,
        parse_mode="HTML",
    )

    # Store the message ID for later updates
    if user_id not in user_data:
        user_data[user_id] = {}
    if "message_ids" not in user_data[user_id]:
        user_data[user_id]["message_ids"] = []
    user_data[user_id]["message_ids"].append(sent_message.message_id)

    # Update user step
    update_user_step(user_id, STEP_UPLOADING_FILES)

    logger.debug(f" User {user_id} moved to file upload with {copy_number} copies")


@bot.callback_query_handler(func=lambda call: call.data.startswith("doc_type_"))
def handle_document_selection(call):
    language = get_user_language(call.message.chat.id)
    try:
        # Extract document type ID, service ID, and language ID from callback data
        parts = call.data.split("_")
        doc_type_id = int(parts[2])
        service_id = int(parts[3])
        lang_id = int(parts[4]) if len(parts) > 4 else None

        # Get document type and language details
        from services.models import Category, Product, Language

        doc_type = Product.objects.get(id=doc_type_id)
        category = Category.objects.get(id=service_id)
        lang = Language.objects.get(id=lang_id) if lang_id else None

        # Store the selected document type and language in user data
        user_id = call.message.chat.id
        if user_id not in user_data:
            user_data[user_id] = {}

        user_data[user_id]["doc_type"] = doc_type
        user_data[user_id]["category"] = category
        if lang:
            user_data[user_id]["language"] = lang

        # Clear any previously uploaded files
        if user_id in uploaded_files:
            del uploaded_files[user_id]

        # Initialize uploaded_files for this user
        uploaded_files[user_id] = {
            "doc_type_id": doc_type_id,
            "service_id": service_id,
            "lang_id": lang_id,
            "files": {},
        }

        # Get document type and language names for the message
        from services.models import Product, Language

        doc_type = Product.objects.get(id=doc_type_id)
        lang_name = Language.objects.get(id=lang_id).name if lang_id else ""

        # Store copy number as 0 by default
        uploaded_files[user_id]["copy_number"] = 0

        # Show copy number selection instead of going directly to upload
        show_copy_number_selection(call.message, language, doc_type, lang_name)

    except (ValueError, IndexError) as e:
        error_msg = get_text("error_occurred", language)
        bot.send_message(call.message.chat.id, error_msg)
        print(f"Error in handle_document_selection: {e}")
        show_categorys(call.message, language)
    except Exception as e:
        error_msg = get_text("error_occurred", language)
        bot.send_message(call.message.chat.id, error_msg)
        print(f"Unexpected error in handle_document_selection: {e}")
        show_main_menu(call.message, language)

    logger.debug(f" Updated uploaded_files: {uploaded_files.get(user_id, {})}")

    update_user_step(user_id, STEP_UPLOADING_FILES)

    # Answer the callback query
    bot.answer_callback_query(call.id)

    # Message is already sent above, just log the action
    logger.debug(f" File upload message sent to user {user_id}")


def show_payment_options(message, language, order):
    """Show payment options for the order"""
    user_id = message.chat.id

    # Update user step to payment method
    update_user_step(user_id, STEP_PAYMENT_METHOD)

    # Get user and calculate pricing
    from accounts.models import BotUser

    user = order.bot_user  # Get user from order

    # Calculate pricing with copy charges
    base_price, copy_charge, total_price, copy_percentage = calculate_order_pricing(
        order, user
    )

    # Determine charging type and user type labels
    is_dynamic = order.product.category.charging == "dynamic"

    if user.is_agency:
        first_page_price = order.product.agency_first_page_price
        other_page_price = order.product.agency_other_page_price
        user_type = (
            "Agency"
            if language == "en"
            else "Агентство" if language == "ru" else "Agentlik"
        )
    else:
        first_page_price = order.product.ordinary_first_page_price
        other_page_price = order.product.ordinary_other_page_price
        user_type = (
            "Regular User"
            if language == "en"
            else "Обычный пользователь" if language == "ru" else "Oddiy foydalanuvchi"
        )

    # Get service language name if available
    service_lang_line = ""
    try:
        if order.language:
            lang_name = order.language.name
            if language == "uz":
                service_lang_line = f"🌍 Xizmat tili: {lang_name}\n"
            elif language == "ru":
                service_lang_line = f"🌍 Язык услуги: {lang_name}\n"
            else:
                service_lang_line = f"🌍 Service language: {lang_name}\n"
    except Exception:
        pass

    # Create summary text with copy information
    if language == "uz":
        summary_text = "📋 <b>Buyurtma xulosasi</b>\n\n"
        summary_text += f"📄 Buyurtma raqami: #{order.id}\n"
        summary_text += f"📎 Jami fayllar: {order.files.count()}\n"
        summary_text += f"📄 Jami sahifalar: {order.total_pages}\n"
        summary_text += service_lang_line
        summary_text += f"🏢 Foydalanuvchi turi: {user_type}\n"
        if is_dynamic:
            summary_text += f"💰 1-sahifa narxi: {first_page_price:,.0f} so'm\n"
            if order.total_pages > 1:
                summary_text += f"💰 Qolgan sahifalar: {other_page_price:,.0f} so'm\n"
        summary_text += f"💵 Asosiy narx: {base_price:,.0f} so'm\n"

        # Add copy information
        if order.copy_number > 0:
            summary_text += f"📋 Nusxalar soni: {order.copy_number}\n"
            summary_text += f"💳 Nusxalar uchun to'lov ({copy_percentage}%): {copy_charge:,.0f} so'm\n"

        summary_text += f"💵 <b>Jami summa: {total_price:,.0f} so'm</b>\n"
        summary_text += f"⏱️ Taxminiy muddat: {order.product.estimated_days} kun\n\n"
        if user.is_agency:
            summary_text += "💳 <b>To'lov usulini tanlang:</b>"
        else:
            summary_text += "💳 <b>To'lov usulini tanlang:</b>\n📌 Eslatma: Naqd to‘lov faqat ofisimizda qabul qilinadi 💵. \nOfisdan tashqarida hujjat yuborsangiz, karta orqali to‘lovni amalga oshiring 💳. \nAgar to‘liq to‘lov qilolmasangiz, “Qisman” (50 000 so‘m) to‘lovni tanlang — shunda ishlaringiz muvaffaqiyatli tasdiqlanadi ✅."
    elif language == "ru":
        summary_text = "📋 <b>Сводка заказа</b>\n\n"
        summary_text += f"📄 Номер заказа: #{order.id}\n"
        summary_text += f"📎 Всего файлов: {order.files.count()}\n"
        summary_text += f"📄 Всего страниц: {order.total_pages}\n"
        summary_text += service_lang_line
        summary_text += f"🏢 Тип пользователя: {user_type}\n"
        if is_dynamic:
            summary_text += f"💰 Цена 1-й страницы: {first_page_price:,.0f} сум\n"
            if order.total_pages > 1:
                summary_text += f"💰 Остальные страницы: {other_page_price:,.0f} сум\n"
        summary_text += f"💵 Базовая цена: {base_price:,.0f} сум\n"

        # Add copy information
        if order.copy_number > 0:
            summary_text += f"📋 Количество копий: {order.copy_number}\n"
            summary_text += (
                f"💳 Оплата за копии ({copy_percentage}%): {copy_charge:,.0f} сум\n"
            )

        summary_text += f"💵 <b>Общая сумма: {total_price:,.0f} сум</b>\n"
        summary_text += f"⏱️ Примерный срок: {order.product.estimated_days} дней\n\n"
        if user.is_agency:
            summary_text += "💳 <b>Выберите способ оплаты:</b>"
        else:
            summary_text += "💳 <b>Выберите способ оплаты:</b>\n📌 Напоминание: Наличный расчет возможен только в нашем офисе 💵. \nЕсли вы отправляете документы вне офиса, необходимо выбрать оплату картой 💳. \nЕсли вы не можете оплатить полную сумму, выберите «Частичную» оплату (50 000 сум) — тогда ваша работа будет успешно подтверждена ✅."
    else:  # English
        summary_text = "📋 <b>Order Summary</b>\n\n"
        summary_text += f"📄 Order number: #{order.id}\n"
        summary_text += f"📎 Total files: {order.files.count()}\n"
        summary_text += f"📄 Total pages: {order.total_pages}\n"
        summary_text += service_lang_line
        summary_text += f"🏢 User type: {user_type}\n"
        if is_dynamic:
            summary_text += f"💰 1st page price: {first_page_price:,.0f} sum\n"
            if order.total_pages > 1:
                summary_text += f"💰 Other pages: {other_page_price:,.0f} sum\n"
        summary_text += f"💵 Base price: {base_price:,.0f} sum\n"

        # Add copy information
        if order.copy_number > 0:
            summary_text += f"📋 Number of copies: {order.copy_number}\n"
            summary_text += (
                f"💳 Copy charges ({copy_percentage}%): {copy_charge:,.0f} sum\n"
            )

        summary_text += f"💵 <b>Total amount: {total_price:,.0f} sum</b>\n"
        summary_text += f"⏱️ Estimated time: {order.product.estimated_days} days\n\n"
        summary_text += "💳 <b>Choose payment method:</b>\n📌 Note: Cash payment is only available at our office 💵. \nIf you are sending documents outside the office, you must choose card payment 💳. \nEven if you cannot pay the full amount by card, make a “Partial” payment to ensure your work is successfully confirmed ✅."

    # Create reply keyboard markup with payment options
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    card_button = types.KeyboardButton(text=get_text("send_to_card", language))
    cash_button = types.KeyboardButton(text=get_text("deliver_manually", language))
    back_to_upload_docs = types.KeyboardButton(
        text=get_text("back_to_upload_docs", language)
    )
    markup.add(card_button, cash_button)
    markup.add(back_to_upload_docs)

    # Send new message with payment options
    bot.send_message(
        chat_id=message.chat.id,
        text=summary_text,
        reply_markup=markup,
        parse_mode="HTML",
    )


@bot.message_handler(content_types=["document", "photo"])
def handle_file_upload(message):
    user_id = message.from_user.id
    language = get_user_language(user_id)
    current_step = get_user_step(user_id)
    
    # Update username in case it changed on Telegram
    update_user_username(message)

    logger.debug(f" ====== FILE UPLOAD START ======")
    logger.debug(f" File upload from user {user_id}, step: {current_step}")
    logger.debug(f" STEP_UPLOADING_RECEIPT = {STEP_UPLOADING_RECEIPT}")
    logger.debug(f" STEP_UPLOADING_FILES = {STEP_UPLOADING_FILES}")
    logger.debug(f" Has document: {message.document is not None}")
    logger.debug(f" Has photo: {message.photo is not None}")

    # Handle payment receipt uploads
    if current_step == STEP_UPLOADING_RECEIPT:
        logger.debug(f" Entering STEP_UPLOADING_RECEIPT handler")
        if message.document or message.photo:
            try:
                logger.debug(f" Getting user_data from uploaded_files...")
                user_data = uploaded_files.get(user_id, {})
                logger.debug(f" user_data = {user_data}")
                
                if "order_id" not in user_data:
                    logger.error(f" order_id not found in user_data!")
                    bot.send_message(
                        message.chat.id,
                        get_text("order_not_found_restart", language),
                    )
                    return

                order_id = user_data["order_id"]
                logger.debug(f" order_id = {order_id}")
                
                from orders.models import Order
                order = Order.objects.get(id=order_id)
                logger.debug(f" Order found: {order}")

                # Save receipt file
                from django.core.files.base import ContentFile
                from django.core.files.storage import default_storage
                from orders.models import Receipt
                import time

                logger.debug(f" Downloading file from Telegram...")
                if message.document:
                    file_info = bot.get_file(message.document.file_id)
                    downloaded_file = bot.download_file(file_info.file_path)
                    # Truncate original filename to prevent path length issues
                    original_name = truncate_filename(message.document.file_name or "doc.pdf", max_length=30)
                    file_name = f"rcpt_{order_id}_{int(time.time())}_{original_name}"
                    telegram_file_id = message.document.file_id
                else:  # message.photo
                    file_info = bot.get_file(message.photo[-1].file_id)
                    downloaded_file = bot.download_file(file_info.file_path)
                    file_name = f"rcpt_{order_id}_{int(time.time())}.jpg"
                    telegram_file_id = message.photo[-1].file_id
                
                logger.debug(f" File downloaded, size: {len(downloaded_file)} bytes")
                logger.debug(f" File name: {file_name}")

                # Save receipt to storage
                logger.debug(f" Saving file to storage...")
                file_content = ContentFile(downloaded_file, name=file_name)
                receipt_path = default_storage.save(
                    f"receipts/{file_name}", file_content
                )
                logger.debug(f" File saved to: {receipt_path}")

                # Get user for Receipt record
                user = get_bot_user(user_id)
                logger.debug(f" Bot user: {user}")

                # Create Receipt record with proper file handling
                logger.debug(f" Creating Receipt record...")
                try:
                    from django.core.files import File
                    
                    receipt = Receipt.objects.create(
                        order=order,
                        telegram_file_id=telegram_file_id,
                        amount=order.total_due,
                        source='bot',
                        status='pending',
                        uploaded_by_user=user,
                    )
                    # Open the file and assign it properly
                    with default_storage.open(receipt_path, 'rb') as f:
                        receipt.file.save(os.path.basename(receipt_path), File(f), save=True)
                    
                    logger.debug(f" Receipt created: {receipt.id}")
                except Exception as receipt_error:
                    logger.error(f" Failed to create Receipt record: {receipt_error}")
                    import traceback
                    traceback.print_exc()

                # Keep legacy field for backward compatibility
                logger.debug(f" Updating order...")
                order.recipt = receipt_path
                order.payment_type = "card"
                order.status = "payment_received"
                order.is_active = True
                order.save()
                logger.debug(f" Order updated successfully")

                # Forward order to channel
                logger.debug(f" Forwarding order to channel...")
                forward_success = forward_order_to_channel(order, language)

                if not forward_success:
                    logger.warning(f" Failed to forward order {order.id} to channel")

                # Clear uploaded files data
                logger.debug(f" Clearing user files...")
                clear_user_files(user_id)
                update_user_step(user_id, STEP_REGISTERED)

                # Send completion confirmation
                user = get_bot_user(user_id)
                if not user:
                    logger.error(f" User not found for order completion: {user_id}")
                    return

                # Calculate pricing with copy charges
                base_price, copy_charge, total_price, copy_percentage = (
                    calculate_order_pricing(order, user)
                )

                # Determine charging type
                is_dynamic = order.product.category.charging == "dynamic"

                # Calculate pricing based on user type
                if user.is_agency:
                    first_page_price = order.product.agency_first_page_price
                    other_page_price = order.product.agency_other_page_price
                else:
                    first_page_price = order.product.ordinary_first_page_price
                    other_page_price = order.product.ordinary_other_page_price

                # Get service language name
                lang_name = ""
                try:
                    if order.language:
                        lang_name = order.language.name
                except Exception:
                    pass

                # Format user display with username if available
                user_display = user.name
                if user.username:
                    user_display += f" (@{user.username})"

                # Create completion message
                if language == "uz":
                    completion_text = "✅ <b>Yuborildi!</b>\n\n"
                    completion_text += "💳 <b>To'lov holati:</b> Tekshiruvda\n\n"
                    completion_text += "📋 <b>Buyurtma ma'lumotlari:</b>\n"
                    completion_text += f"👤 Mijoz: {user_display}\n"
                    completion_text += f"📞 Telefon: {user.phone}\n"
                    completion_text += f"📄 Buyurtma raqami: {order.id}\n"
                    completion_text += f"📊 Jami sahifalar: {order.total_pages}\n"
                    if lang_name:
                        completion_text += f"🌍 Xizmat tili: {lang_name}\n"
                    if is_dynamic:
                        completion_text += (
                            f"💰 1-sahifa narxi: {first_page_price:,.0f} so'm\n"
                        )
                        if order.total_pages > 1:
                            completion_text += (
                                f"💰 Qolgan sahifalar: {other_page_price:,.0f} so'm\n"
                            )
                    completion_text += f"💵 Asosiy narx: {base_price:,.0f} so'm\n"

                    # Add copy information
                    if order.copy_number > 0:
                        completion_text += f"📋 Nusxalar soni: {order.copy_number}\n"
                        completion_text += f"💳 Nusxalar uchun to'lov ({copy_percentage}%): {copy_charge:,.0f} so'm\n"

                    completion_text += (
                        f"💵 <b>Jami summa: {total_price:,.0f} so'm</b>\n"
                    )
                    completion_text += (
                        f"📅 Taxminiy muddat: {order.product.estimated_days} kun\n\n"
                    )
                    completion_text += "✅ Buyurtmangiz muvaffaqiyatli yuborildi!\n"
                    completion_text += "📞 To'lovni tasdiqlangandan keyin operatorlarimiz siz bilan bog'lanishadi."
                elif language == "ru":
                    completion_text = "✅ <b>Отправлено!</b>\n\n"
                    completion_text += "💳 <b>Статус оплаты:</b> На проверке\n\n"
                    completion_text += "📋 <b>Информация о заказе:</b>\n"
                    completion_text += f"👤 Клиент: {user_display}\n"
                    completion_text += f"📞 Телефон: {user.phone}\n"
                    completion_text += f"📄 Номер заказа: {order.id}\n"
                    completion_text += f"📊 Всего страниц: {order.total_pages}\n"
                    if lang_name:
                        completion_text += f"🌍 Язык услуги: {lang_name}\n"
                    if is_dynamic:
                        completion_text += (
                            f"💰 Цена 1-й страницы: {first_page_price:,.0f} сум\n"
                        )
                        if order.total_pages > 1:
                            completion_text += (
                                f"💰 Остальные страницы: {other_page_price:,.0f} сум\n"
                            )
                    completion_text += f"💵 Базовая цена: {base_price:,.0f} сум\n"

                    # Add copy information
                    if order.copy_number > 0:
                        completion_text += f"📋 Количество копий: {order.copy_number}\n"
                        completion_text += f"💳 Оплата за копии ({copy_percentage}%): {copy_charge:,.0f} сум\n"

                    completion_text += (
                        f"💵 <b>Общая сумма: {total_price:,.0f} сум</b>\n"
                    )
                    completion_text += (
                        f"📅 Примерный срок: {order.product.estimated_days} дней\n\n"
                    )
                    completion_text += "✅ Ваш заказ успешно отправлен!\n"
                    completion_text += (
                        "📞 После подтверждения оплаты наши операторы свяжутся с вами."
                    )
                else:  # English
                    completion_text = "✅ <b>Sent!</b>\n\n"
                    completion_text += "💳 <b>Payment status:</b> Under Review\n\n"
                    completion_text += "📋 <b>Order information:</b>\n"
                    completion_text += f"👤 Client: {user_display}\n"
                    completion_text += f"📞 Phone: {user.phone}\n"
                    completion_text += f"📄 Order number: {order.id}\n"
                    completion_text += f"📊 Total pages: {order.total_pages}\n"
                    if lang_name:
                        completion_text += f"🌐 Service language: {lang_name}\n"
                    if is_dynamic:
                        completion_text += (
                            f"💰 1st page price: {first_page_price:,.0f} sum\n"
                        )
                        if order.total_pages > 1:
                            completion_text += (
                                f"💰 Other pages: {other_page_price:,.0f} sum\n"
                            )
                    completion_text += f"💵 Base price: {base_price:,.0f} sum\n"

                    # Add copy information
                    if order.copy_number > 0:
                        completion_text += f"📋 Number of copies: {order.copy_number}\n"
                        completion_text += f"💳 Copy charges ({copy_percentage}%): {copy_charge:,.0f} sum\n"

                    completion_text += (
                        f"💵 <b>Total amount: {total_price:,.0f} sum</b>\n"
                    )
                    completion_text += (
                        f"📅 Estimated time: {order.product.estimated_days} days\n\n"
                    )
                    completion_text += "✅ Your order has been successfully sent!\n"
                    completion_text += (
                        "📞 Our operators will contact you after payment confirmation."
                    )

                # Send completion message
                logger.debug(f" Sending completion message...")
                bot.send_message(
                    chat_id=message.chat.id,
                    text=completion_text,
                    parse_mode="HTML",
                )

                # Send branch location for pickup
                if order.branch:
                    send_branch_location(message.chat.id, order.branch, language)

                # Return user to main menu
                logger.debug(f" ====== FILE UPLOAD SUCCESS ======")
                show_main_menu(message, language)
                return

            except Exception as e:
                logger.error(f" ====== FILE UPLOAD FAILED ======")
                logger.error(f" Exception type: {type(e).__name__}")
                logger.error(f" Exception message: {e}")
                import traceback
                traceback.print_exc()
                
                # Send detailed error to user (in development)
                error_detail = f"Debug: {type(e).__name__}: {str(e)[:100]}"
                bot.send_message(
                    message.chat.id,
                    f"{get_text('receipt_upload_failed', language)}\n\n<code>{error_detail}</code>",
                    parse_mode="HTML",
                )
                return
        else:
            logger.debug(f" No document or photo in message for STEP_UPLOADING_RECEIPT")

    # Handle additional receipt uploads for existing orders
    if current_step == STEP_AWAITING_RECEIPT:
        if message.document or message.photo:
            try:
                user_data = uploaded_files.get(user_id, {})
                order_id = user_data.get("pending_payment_order_id")
                
                if not order_id:
                    bot.send_message(
                        message.chat.id,
                        get_text("order_not_found_restart", language),
                    )
                    return

                from orders.models import Order, Receipt

                order = Order.objects.get(id=order_id)
                user = get_bot_user(user_id)

                # Save receipt file
                from django.core.files.base import ContentFile
                from django.core.files.storage import default_storage
                import time

                if message.document:
                    file_info = bot.get_file(message.document.file_id)
                    downloaded_file = bot.download_file(file_info.file_path)
                    file_name = f"receipt_{order_id}_{int(time.time())}_{message.document.file_name}"
                else:  # message.photo
                    file_info = bot.get_file(message.photo[-1].file_id)
                    downloaded_file = bot.download_file(file_info.file_path)
                    file_name = f"receipt_{order_id}_{int(time.time())}_{message.photo[-1].file_id}.jpg"

                # Save receipt to storage
                file_content = ContentFile(downloaded_file, name=file_name)
                receipt_path = default_storage.save(
                    f"receipts/{file_name}", file_content
                )

                # Get telegram file id for quick access
                telegram_file_id = None
                if message.document:
                    telegram_file_id = message.document.file_id
                elif message.photo:
                    telegram_file_id = message.photo[-1].file_id

                # Create Receipt record - avoid passing path directly to FileField
                try:
                    receipt = Receipt.objects.create(
                        order=order,
                        telegram_file_id=telegram_file_id,
                        amount=order.remaining,  # Default to remaining amount
                        source='bot',
                        status='pending',
                        uploaded_by_user=user,
                    )
                    # Set file path directly
                    receipt.file.name = receipt_path
                    receipt.save()
                except Exception as receipt_error:
                    logger.error(f" Failed to create Receipt record: {receipt_error}")
                    # Continue without Receipt record

                # Clear user state
                if user_id in uploaded_files:
                    uploaded_files[user_id].pop("pending_payment_order_id", None)
                update_user_step(user_id, STEP_REGISTERED)

                # Send success message
                if language == "uz":
                    success_text = f"✅ <b>Chek yuklandi!</b>\n\n"
                    success_text += f"📋 Buyurtma #{order.id}\n"
                    success_text += f"💰 Qoldiq: {order.remaining:,.0f} so'm\n\n"
                    success_text += "⏳ To'lov tekshiruvga yuborildi.\n"
                    success_text += "📞 Tasdiqlanganidan keyin sizga xabar beramiz."
                elif language == "ru":
                    success_text = f"✅ <b>Чек загружен!</b>\n\n"
                    success_text += f"📋 Заказ #{order.id}\n"
                    success_text += f"💰 Остаток: {order.remaining:,.0f} сум\n\n"
                    success_text += "⏳ Оплата отправлена на проверку.\n"
                    success_text += "📞 Мы уведомим вас после подтверждения."
                else:
                    success_text = f"✅ <b>Receipt uploaded!</b>\n\n"
                    success_text += f"📋 Order #{order.id}\n"
                    success_text += f"💰 Remaining: {order.remaining:,.0f} sum\n\n"
                    success_text += "⏳ Payment sent for verification.\n"
                    success_text += "📞 We will notify you after confirmation."

                bot.send_message(
                    chat_id=message.chat.id,
                    text=success_text,
                    parse_mode="HTML",
                )

                # Return to main menu
                show_main_menu(message, language)
                return

            except Order.DoesNotExist:
                bot.send_message(
                    message.chat.id,
                    get_text("error_order_not_found", language),
                )
                return
            except Exception as e:
                logger.error(f" Failed to handle additional receipt upload: {e}")
                import traceback

                traceback.print_exc()
                bot.send_message(
                    message.chat.id,
                    get_text("receipt_upload_failed", language),
                )
                return

    # Handle payment receipt uploads when user is awaiting payment (after card selection)
    if current_step == STEP_AWAITING_PAYMENT:
        if message.document or message.photo:
            try:
                logger.debug(f" Processing payment receipt for STEP_AWAITING_PAYMENT")
                user_data = uploaded_files.get(user_id, {})
                order_id = user_data.get("order_id")
                
                if not order_id:
                    bot.send_message(
                        message.chat.id,
                        get_text("order_not_found_restart", language),
                    )
                    return

                from orders.models import Order, Receipt
                from django.core.files.base import ContentFile
                from django.core.files.storage import default_storage
                import time

                order = Order.objects.get(id=order_id)
                user = get_bot_user(user_id)

                # Download and save receipt file - accept ANY file format
                if message.document:
                    file_info = bot.get_file(message.document.file_id)
                    downloaded_file = bot.download_file(file_info.file_path)
                    original_name = message.document.file_name or "receipt"
                    # Truncate if too long
                    if len(original_name) > 30:
                        name_parts = original_name.rsplit('.', 1)
                        ext = f".{name_parts[1]}" if len(name_parts) > 1 else ""
                        original_name = name_parts[0][:25] + ext
                    file_name = f"rcpt_{order_id}_{int(time.time())}_{original_name}"
                    telegram_file_id = message.document.file_id
                else:  # message.photo
                    file_info = bot.get_file(message.photo[-1].file_id)
                    downloaded_file = bot.download_file(file_info.file_path)
                    file_name = f"rcpt_{order_id}_{int(time.time())}.jpg"
                    telegram_file_id = message.photo[-1].file_id

                logger.debug(f" Receipt file: {file_name}, size: {len(downloaded_file)} bytes")

                # Save receipt to storage
                file_content = ContentFile(downloaded_file, name=file_name)
                receipt_path = default_storage.save(f"receipts/{file_name}", file_content)

                # Create Receipt record
                try:
                    receipt = Receipt.objects.create(
                        order=order,
                        telegram_file_id=telegram_file_id,
                        amount=order.total_due,
                        source='bot',
                        status='pending',
                        uploaded_by_user=user,
                    )
                    receipt.file.name = receipt_path
                    receipt.save()
                    logger.debug(f" Receipt created: {receipt.id}")
                except Exception as receipt_error:
                    logger.error(f" Failed to create Receipt record: {receipt_error}")

                # Update order
                order.recipt = receipt_path
                order.payment_type = "card"
                order.status = "payment_received"
                order.is_active = True
                order.save()

                # Forward order to channel
                forward_success = forward_order_to_channel(order, language)
                if not forward_success:
                    logger.warning(f" Failed to forward order {order.id} to channel")

                # Clear user data and update step
                clear_user_files(user_id)
                update_user_step(user_id, STEP_REGISTERED)

                # Send confirmation message
                if language == "uz":
                    confirm_text = "✅ <b>To'lov cheki qabul qilindi!</b>\n\n"
                    confirm_text += f"📋 Buyurtma #{order.id}\n"
                    confirm_text += f"💰 Summa: {order.total_price:,} so'm\n\n"
                    confirm_text += "⏳ To'lov tekshiruvga yuborildi.\n"
                    confirm_text += "📞 Tasdiqlanganidan keyin sizga xabar beramiz."
                elif language == "ru":
                    confirm_text = "✅ <b>Чек об оплате получен!</b>\n\n"
                    confirm_text += f"📋 Заказ #{order.id}\n"
                    confirm_text += f"💰 Сумма: {order.total_price:,} сум\n\n"
                    confirm_text += "⏳ Оплата отправлена на проверку.\n"
                    confirm_text += "📞 Мы уведомим вас после подтверждения."
                else:
                    confirm_text = "✅ <b>Payment receipt received!</b>\n\n"
                    confirm_text += f"📋 Order #{order.id}\n"
                    confirm_text += f"💰 Amount: {order.total_price:,} sum\n\n"
                    confirm_text += "⏳ Payment sent for verification.\n"
                    confirm_text += "📞 We will notify you after confirmation."

                bot.send_message(
                    chat_id=message.chat.id,
                    text=confirm_text,
                    parse_mode="HTML",
                )

                # Send branch location for pickup
                if order.branch:
                    send_branch_location(message.chat.id, order.branch, language)

                # Return to main menu
                show_main_menu(message, language)
                return

            except Order.DoesNotExist:
                bot.send_message(
                    message.chat.id,
                    get_text("error_order_not_found", language),
                )
                return
            except Exception as e:
                logger.error(f" Failed to handle payment receipt upload: {e}")
                import traceback
                traceback.print_exc()
                bot.send_message(
                    message.chat.id,
                    get_text("receipt_upload_failed", language),
                )
                return

    # Handle regular file uploads for orders
    if current_step == STEP_UPLOADING_FILES:
        logger.debug(f" Processing file upload for user {user_id}")

        try:
            # Get file information
            if message.document:
                file_id = message.document.file_id
                file_name = message.document.file_name
                file_size = message.document.file_size
            elif message.photo:
                file_id = message.photo[-1].file_id
                file_info_obj = bot.get_file(file_id)
                file_name = f"photo_{file_id}.jpg"
                file_size = file_info_obj.file_size
            else:
                return

            logger.debug(f" File info: {file_name}, size: {file_size}")

            # Validate file format
            if not is_valid_file_format(file_name):
                bot.send_message(message.chat.id, get_text("invalid_file_format_full", language))
                return

            # Download file
            file_info = bot.get_file(file_id)
            downloaded_file = bot.download_file(file_info.file_path)

            logger.debug(f" File downloaded, size: {len(downloaded_file)} bytes")

            # Get page count
            pages = get_file_pages_from_content(downloaded_file, file_name)
            logger.debug(f" Detected pages: {pages}")

            # Save file to storage
            from django.core.files.base import ContentFile
            from django.core.files.storage import default_storage

            file_content = ContentFile(downloaded_file, name=file_name)
            file_path = default_storage.save(
                f"order_files/{user_id}_{file_name}", file_content
            )

            logger.debug(f" File saved to: {file_path}")

            # Store file information with unique ID
            import time

            # Get current user data or initialize
            current_data = uploaded_files.get(user_id) or {}
            if not isinstance(current_data, dict):
                current_data = dict(current_data) if current_data else {}
            
            # Ensure 'files' key exists
            if "files" not in current_data:
                current_data["files"] = {}

            # Generate unique file ID using timestamp and file_id
            file_uid = f"{int(time.time() * 1000)}_{file_id[:8]}"

            # Add new file to files dict
            current_data["files"][file_uid] = {
                "file_path": file_path,
                "file_name": file_name,
                "pages": pages,
                "file_size": file_size,
            }
            
            # Reassign to trigger save to persistent storage
            uploaded_files[user_id] = current_data

            print(
                f"[DEBUG] Total files for user: {len(uploaded_files[user_id]['files'])}"
            )

            # Send file confirmation with brief info
            file_size_kb = file_size / 1024
            file_size_mb = file_size_kb / 1024

            if file_size_mb >= 1:
                size_display = f"{file_size_mb:.2f} MB"
            else:
                size_display = f"{file_size_kb:.2f} KB"

            if language == "uz":
                confirm_text = f"✅ <b>Fayl qabul qilindi!</b>\n\n"
                confirm_text += f"📄 Fayl nomi: {file_name}\n"
                confirm_text += f"📊 Sahifalar: {pages}\n"
                confirm_text += f"💾 Hajmi: {size_display}\n"
            elif language == "ru":
                confirm_text = f"✅ <b>Файл принят!</b>\n\n"
                confirm_text += f"📄 Имя файла: {file_name}\n"
                confirm_text += f"📊 Страниц: {pages}\n"
                confirm_text += f"💾 Размер: {size_display}\n"
            else:  # English
                confirm_text = f"✅ <b>File received!</b>\n\n"
                confirm_text += f"📄 File name: {file_name}\n"
                confirm_text += f"📊 Pages: {pages}\n"
                confirm_text += f"💾 Size: {size_display}\n"

            # Add delete button with file_uid for precise deletion
            markup = types.InlineKeyboardMarkup()
            delete_button = types.InlineKeyboardButton(
                text=(
                    "🗑️ O'chirish"
                    if language == "uz"
                    else "🗑️ Delete" if language == "en" else "🗑️ Удалить"
                ),
                callback_data=f"delete_file_{file_uid}",
            )
            markup.add(delete_button)

            print(
                f"[DEBUG] Created delete button with file_uid {file_uid} for user {user_id}"
            )

            bot.send_message(
                chat_id=message.chat.id,
                text=confirm_text,
                reply_markup=markup,
                parse_mode="HTML",
            )

            # Update totals message
            update_totals_message(user_id, language)

        except Exception as e:
            logger.error(f" Failed to process file upload: {e}")
            import traceback

            traceback.print_exc()

            bot.send_message(message.chat.id, get_text("file_upload_failed", language))
        return

    # If not in uploading steps, ignore
    logger.debug(f" User not in uploading step, ignoring file")


@bot.callback_query_handler(func=lambda call: call.data.startswith("payment_card_"))
def handle_payment_card_selection(call):
    """Handle card payment selection"""
    language = get_user_language(call.message.chat.id)
    order_id = int(call.data.split("_")[2])

    try:
        from orders.models import Order

        order = Order.objects.get(id=order_id)

        # Update user step to awaiting payment
        update_user_step(call.message.chat.id, STEP_AWAITING_PAYMENT)

        # Show card information and ask for receipt
        card_info = get_text("payment_card_info", language)
        card_info += "\n\n💳 <b>Karta ma'lumotlari:</b>\n"
        card_info += "🏦 Bank: Kapital Bank\n"
        card_info += "💳 Karta raqami: 1234 5678 9012 3456\n"
        card_info += "👤 Karta egasi: Translation Center\n\n"
        card_info += get_text("upload_payment_receipt", language)

        markup = types.InlineKeyboardMarkup()
        done_button = types.InlineKeyboardButton(
            text=get_text("payment_done", language),
            callback_data=f"payment_receipt_{order_id}",
        )
        back_button = types.InlineKeyboardButton(
            text=get_text("back_to_menu", language), callback_data="main_menu"
        )
        markup.add(done_button, back_button)

        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=card_info,
            reply_markup=markup,
        )

    except Order.DoesNotExist:
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=get_text("error_order_not_found", language),
        )


@bot.callback_query_handler(func=lambda call: call.data.startswith("payment_cash_"))
def handle_payment_cash_selection(call):
    """Handle cash payment selection"""
    language = get_user_language(call.message.chat.id)
    order_id = int(call.data.split("_")[2])

    try:
        from orders.models import Order

        order = Order.objects.get(id=order_id)

        # Update order with cash payment
        order.payment_type = "cash"
        order.is_active = True  # Mark as active for manual payment
        order.save()

        # Show final summary
        total_files = order.files.count()
        summary_text = f"📋 <b>{get_text('order_summary', language)}</b>\n\n"
        summary_text += f"📄 {get_text('order_number', language)}: #{order.id}\n"
        summary_text += f"📎 {get_text('total_files', language)}: {total_files}\n"
        summary_text += f"📄 {get_text('total_pages', language)}: {order.total_pages}\n"
        summary_text += (
            f"💰 {get_text('total_amount', language)}: {order.total_price:,} so'm\n"
        )
        summary_text += f"💳 {get_text('status', language)}: {get_text('manual_payment', language)}\n\n"
        summary_text += "📞 Admin siz bilan bog'lanadi va to'lovni qabul qiladi."

        markup = types.InlineKeyboardMarkup()
        main_menu_button = types.InlineKeyboardButton(
            text=get_text("back_to_main_menu", language), callback_data="main_menu"
        )
        markup.add(main_menu_button)

        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=summary_text,
            reply_markup=markup,
        )

        # Update user step back to registered
        update_user_step(call.message.chat.id, STEP_REGISTERED)

    except Order.DoesNotExist:
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=get_text("error_order_not_found", language),
        )


@bot.callback_query_handler(func=lambda call: call.data.startswith("payment_receipt_"))
def handle_payment_receipt_upload(call):
    """Handle payment receipt upload confirmation"""
    language = get_user_language(call.message.chat.id)
    order_id = int(call.data.split("_")[2])

    try:
        from orders.models import Order

        order = Order.objects.get(id=order_id)

        # Update order with card payment and receipt
        order.payment_type = "card"
        order.is_active = True  # Mark as active with receipt uploaded
        order.save()

        # Show final summary for card payment
        total_files = order.files.count()
        summary_text = f"📋 <b>{get_text('order_summary', language)}</b>\n\n"
        summary_text += f"📄 {get_text('order_number', language)}: #{order.id}\n"
        summary_text += f"📎 {get_text('total_files', language)}: {total_files}\n"
        summary_text += f"📄 {get_text('total_pages', language)}: {order.total_pages}\n"
        summary_text += (
            f"💰 {get_text('total_amount', language)}: {order.total_price:,} so'm\n"
        )
        summary_text += (
            f"💳 {get_text('status', language)}: {get_text('pending', language)}\n\n"
        )
        summary_text += get_text("payment_receipt_received", language)

        markup = types.InlineKeyboardMarkup()
        main_menu_button = types.InlineKeyboardButton(
            text=get_text("back_to_main_menu", language), callback_data="main_menu"
        )
        markup.add(main_menu_button)

        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=summary_text,
            reply_markup=markup,
        )

        # Update user step back to registered
        update_user_step(call.message.chat.id, STEP_REGISTERED)

    except Order.DoesNotExist:
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=get_text("error_order_not_found", language),
        )


@bot.message_handler(content_types=["photo"])
def handle_payment_receipt_photo(message):
    """
    Legacy handler for photo uploads - now handled by main file handler.
    This handler is kept for backward compatibility but the main document/photo
    handler now processes all receipt uploads including photos.
    """
    # All photo handling for receipts is now done in handle_file_upload
    # This handler is no longer needed for STEP_AWAITING_PAYMENT
    pass


@bot.message_handler(func=lambda message: True, content_types=["text"])
def handle_text_messages(message):
    user_id = message.from_user.id
    language = get_user_language(user_id)

    if message.text.startswith("/"):
        return

    user = get_bot_user(user_id)
    if not user:
        start(message)
        return
    
    current_step = user.step

    # Handle copy number input
    if current_step == STEP_SELECTING_COPY_NUMBER:
        try:
            # Try to parse the input as a number
            copy_number = int(message.text)

            if copy_number < 0 or copy_number > 99:
                error_text = get_text("invalid_copy_number", language)
                bot.send_message(message.chat.id, error_text)
                return

            # Store copy number
            if user_id not in uploaded_files:
                uploaded_files[user_id] = {}
            uploaded_files[user_id]["copy_number"] = copy_number

            # Get document type info
            user_data = uploaded_files.get(user_id, {})
            doc_type_id = user_data.get("doc_type_id")
            lang_id = user_data.get("lang_id")

            if not doc_type_id:
                bot.send_message(user_id, get_text("error_occurred", language))
                show_categorys(message, language)
                return

            # Get document type and language
            from services.models import Product, Language

            doc_type = Product.objects.get(id=doc_type_id)
            lang_name = Language.objects.get(id=lang_id).name if lang_id else ""

            # Show upload files interface
            show_upload_files_interface(
                message, language, doc_type, lang_name, copy_number
            )
            return

        except ValueError:
            # Not a valid number
            error_text = get_text("invalid_copy_number", language)
            bot.send_message(message.chat.id, error_text)
            return

    # Handle "Send Receipt" button when user is in receipt upload step
    if current_step == STEP_UPLOADING_RECEIPT:
        if message.text in [
            "📤 Chekni yuborish",
            "📤 Send Receipt",
            "📤 Отправить чек",
        ]:
            # User pressed send receipt button - check if receipt was uploaded
            user_data = uploaded_files.get(user_id, {})
            if "order_id" not in user_data:
                bot.send_message(
                    message.chat.id,
                    get_text("order_not_found_restart", language),
                )
                return

            order_id = user_data["order_id"]

            try:
                from orders.models import Order

                order = Order.objects.get(id=order_id)

                # Check if receipt was uploaded
                if not order.recipt:
                    bot.send_message(message.chat.id, get_text("upload_receipt_first", language))
                    return

                # Receipt is uploaded - finalize the order
                order.status = "payment_received"
                order.is_active = True  # Mark as completed but pending approval
                order.save()

                # Forward order to channel
                forward_success = forward_order_to_channel(order, language)

                if not forward_success:
                    logger.warning(f" Failed to forward order {order.id} to channel")

                # Clear uploaded files data
                clear_user_files(user_id)
                update_user_step(user_id, STEP_REGISTERED)

                # Get user for display
                user = get_bot_user(user_id)
                if not user:
                    logger.error(f" User not found for completion: {user_id}")
                    return

                # Format user display with username if available
                user_display = user.name
                if user.username:
                    user_display += f" (@{user.username})"

                # Send final confirmation to user
                if language == "uz":
                    completion_text = "✅ <b>Yuborildi!</b>\n\n"
                    completion_text += (
                        "💳 <b>To'lov holati:</b> Tasdiqlash kutilmoqda ⏳\n\n"
                    )
                    completion_text += "📋 <b>Buyurtma ma'lumotlari:</b>\n"
                    completion_text += f"👤 Mijoz: {user_display}\n"
                    completion_text += f"📄 Buyurtma raqami: #{order.id}\n"
                    completion_text += f"📊 Jami sahifalar: {order.total_pages}\n"
                    completion_text += f"💰 Jami summa: {order.total_price:,.0f} so'm\n"
                    completion_text += (
                        f"📅 Taxminiy muddat: {order.product.estimated_days} kun\n\n"
                    )
                    completion_text += "✅ Buyurtmangiz muvaffaqiyatli yuborildi!\n"
                    completion_text += "📞 To'lovni tasdiqlangandan keyin operatorlarimiz siz bilan bog'lanishadi."
                elif language == "ru":
                    completion_text = "✅ <b>Отправлено!</b>\n\n"
                    completion_text += (
                        "💳 <b>Статус оплаты:</b> Ожидает подтверждения ⏳\n\n"
                    )
                    completion_text += "📋 <b>Информация о заказе:</b>\n"
                    completion_text += f"👤 Клиент: {user_display}\n"
                    completion_text += f"📄 Номер заказа: #{order.id}\n"
                    completion_text += f"📊 Всего страниц: {order.total_pages}\n"
                    completion_text += f"💰 Общая сумма: {order.total_price:,.0f} сум\n"
                    completion_text += (
                        f"📅 Примерный срок: {order.product.estimated_days} дней\n\n"
                    )
                    completion_text += "✅ Ваш заказ успешно отправлен!\n"
                    completion_text += (
                        "📞 После подтверждения оплаты наши операторы свяжутся с вами."
                    )
                else:  # English
                    completion_text = "✅ <b>Sent!</b>\n\n"
                    completion_text += (
                        "💳 <b>Payment status:</b> Awaiting Approval ⏳\n\n"
                    )
                    completion_text += "📋 <b>Order information:</b>\n"
                    completion_text += f"👤 Client: {user_display}\n"
                    completion_text += f"📄 Order number: #{order.id}\n"
                    completion_text += f"📊 Total pages: {order.total_pages}\n"
                    completion_text += (
                        f"💰 Total amount: {order.total_price:,.0f} sum\n"
                    )
                    completion_text += (
                        f"📅 Estimated time: {order.product.estimated_days} days\n\n"
                    )
                    completion_text += "✅ Your order has been successfully sent!\n"
                    completion_text += (
                        "📞 Our operators will contact you after payment confirmation."
                    )

                # Show main menu
                show_main_menu(message, language)

                # Send completion message after showing menu
                bot.send_message(
                    chat_id=message.chat.id,
                    text=completion_text,
                    parse_mode="HTML",
                )
                
                # Send branch location for pickup
                if order.branch:
                    send_branch_location(message.chat.id, order.branch, language)
                return

            except Order.DoesNotExist:
                bot.send_message(
                    message.chat.id,
                    get_text("order_not_found_restart", language),
                )
                clear_user_files(user_id)
                update_user_step(user_id, STEP_REGISTERED)
                show_categorys(message, language)
                return
            except Exception as e:
                logger.error(f" Failed to finalize order: {e}")
                import traceback

                traceback.print_exc()
                bot.send_message(
                    message.chat.id,
                    get_text("error_general", language),
                )
                return

        # Handle back button during receipt upload
        elif message.text == get_text("back_to_upload_docs", language):
            handle_back_to_upload_docs_message(message, language)
            return

        # If user sends text while in receipt upload step, remind them to upload
        else:
            reminder_text = (
                '📤 Iltimos, to\'lov chekini yuboring yoki "📤 Chekni yuborish" tugmasini bosing'
                if language == "uz"
                else (
                    '📤 Please upload payment receipt or press "📤 Send Receipt" button'
                    if language == "en"
                    else '📤 Пожалуйста, загрузите чек об оплате или нажмите кнопку "📤 Отправить чек"'
                )
            )
            bot.send_message(message.chat.id, reminder_text)
            return

    # Handle back to menu button (universal)
    if message.text == get_text("back_to_menu", language):
        handle_back_button(message, language)
        return

    # Handle keyboard buttons for file upload operations
    if current_step == STEP_UPLOADING_FILES:
        if message.text == get_text("finish_upload", language):
            handle_finish_upload_message(message, language)
            return
        elif message.text == get_text("back_to_copy_number", language):
            handle_back_to_copy_number_message(message, language)
            return
        elif message.text == get_text("back_to_documents", language):
            handle_back_to_documents_message(message, language)
            return

    # Handle name input during registration
    if current_step == STEP_NAME_REQUESTED:
        center = get_current_center()
        create_or_update_user(user_id=user_id, name=message.text, center=center)
        ask_contact(message, language)
        return

    # Handle name editing
    elif current_step == STEP_EDITING_NAME:
        center = get_current_center()
        create_or_update_user(user_id=user_id, name=message.text, center=center)
        update_user_step(user_id, STEP_EDITING_PROFILE)
        bot.send_message(message.chat.id, get_text("name_updated", language))
        show_profile(message, language)
        return

    # Handle phone editing
    elif current_step == STEP_EDITING_PHONE:
        phone_number = (
            message.text
            if message.text
            else (message.contact.phone_number if message.contact else None)
        )
        if phone_number:
            center = get_current_center()
            create_or_update_user(user_id=user_id, phone=phone_number, center=center)
            update_user_step(user_id, STEP_EDITING_PROFILE)
            bot.send_message(message.chat.id, get_text("phone_updated", language))
            show_profile(message, language)
        else:
            bot.send_message(message.chat.id, get_text("send_phone_or_contact", language))
        return

    # Handle payment options buttons
    if message.text == get_text("back_to_upload_docs", language):
        handle_back_to_upload_docs_message(message, language)
        return
    elif message.text == get_text("deliver_manually", language):
        handle_cash_payment_message(message, language)
        return
    elif message.text == get_text("send_to_card", language):
        handle_card_payment_message(message, language)
        return

    # Default: show main menu for registered users
    elif current_step >= STEP_REGISTERED:
        show_main_menu(message, language)


def handle_card_payment_message(message, language):
    """Handle card payment button press from keyboard"""
    user_id = message.from_user.id

    logger.debug(f" Card payment request from user {user_id}")

    # Get order_id from uploaded_files
    user_data = uploaded_files.get(user_id, {})
    if "order_id" not in user_data:
        bot.send_message(
            message.chat.id, get_text("order_not_found_restart", language)
        )
        return

    order_id = user_data["order_id"]

    try:
        from accounts.models import AdditionalInfo
        from orders.models import Order

        order = Order.objects.get(id=order_id)
        user = get_bot_user(user_id)
        if not user:
            bot.send_message(message.chat.id, get_text("user_not_found", language))
            return

        # Update order payment type to card (but don't mark as active yet)
        order.payment_type = "card"
        order.status = "payment_pending"
        order.is_active = False  # Keep inactive until receipt is uploaded
        order.save()

        # Get card details from AdditionalInfo for user's branch
        additional_info = AdditionalInfo.get_for_user(user)
        card_number = additional_info.bank_card if additional_info else "Noma'lum"
        card_holder = additional_info.holder_name if additional_info else "Noma'lum"

        # Calculate pricing with copy charges
        base_price, copy_charge, total_price, copy_percentage = calculate_order_pricing(
            order, user
        )

        # Determine charging type
        is_dynamic = order.product.category.charging == "dynamic"

        # Calculate pricing based on user type
        if user.is_agency:
            first_page_price = order.product.agency_first_page_price
            other_page_price = order.product.agency_other_page_price
        else:
            first_page_price = order.product.ordinary_first_page_price
            other_page_price = order.product.ordinary_other_page_price

        # Get service language name
        lang_name = ""
        try:
            if order.language:
                lang_name = order.language.name
        except Exception:
            pass

        # Create order summary with card payment info
        if language == "uz":
            summary_text = "📋 <b>Buyurtma xulosasi</b>\n\n"
            summary_text += f"📄 Buyurtma raqami: #{order.id}\n"
            summary_text += f"📎 Jami fayllar: {order.files.count()}\n"
            summary_text += f"📄 Jami sahifalar: {order.total_pages}\n"
            if lang_name:
                summary_text += f"🌍 Xizmat tili: {lang_name}\n"
            if is_dynamic:
                summary_text += f"💰 1-sahifa narxi: {first_page_price:,.0f} so'm\n"
                if order.total_pages > 1:
                    summary_text += (
                        f"💰 Qolgan sahifalar: {other_page_price:,.0f} so'm\n"
                    )
            summary_text += f"💵 Asosiy narx: {base_price:,.0f} so'm\n"

            # Add copy information
            if order.copy_number > 0:
                summary_text += f"📋 Nusxalar soni: {order.copy_number}\n"
                summary_text += f"💳 Nusxalar uchun to'lov ({copy_percentage}%): {copy_charge:,.0f} so'm\n"

            summary_text += f"💵 <b>Jami summa: {total_price:,.0f} so'm</b>\n"
            summary_text += f"⏱️ Taxminiy muddat: {order.product.estimated_days} kun\n\n"
            summary_text += "💳 <b>To'lov holati:</b> Kutilmoqda ⏳\n\n"
            summary_text += "━━━━━━━━━━━━━━━━━━━━\n\n"
            summary_text += "💳 <b>Karta ma'lumotlari:</b>\n"
            summary_text += f"💳 Karta raqami: <code>{card_number}</code>\n"
            summary_text += f"👤 Karta egasi: {card_holder}\n\n"
            summary_text += "📤 <b>Iltimos, to'lov chekini yuboring</b>\n"
            summary_text += (
                "📎 Ruxsat etilgan formatlar: JPG, PNG, PDF, DOC, DOCX, HEIC, HEIF"
            )
        elif language == "ru":
            summary_text = "📋 <b>Сводка заказа</b>\n\n"
            summary_text += f"📄 Номер заказа: #{order.id}\n"
            summary_text += f"📎 Всего файлов: {order.files.count()}\n"
            summary_text += f"📄 Всего страниц: {order.total_pages}\n"
            if lang_name:
                summary_text += f"🌍 Язык услуги: {lang_name}\n"
            if is_dynamic:
                summary_text += f"💰 Цена 1-й страницы: {first_page_price:,.0f} сум\n"
                if order.total_pages > 1:
                    summary_text += (
                        f"💰 Остальные страницы: {other_page_price:,.0f} сум\n"
                    )
            summary_text += f"💵 Базовая цена: {base_price:,.0f} сум\n"

            # Add copy information
            if order.copy_number > 0:
                summary_text += f"📋 Количество копий: {order.copy_number}\n"
                summary_text += (
                    f"💳 Оплата за копии ({copy_percentage}%): {copy_charge:,.0f} сум\n"
                )

            summary_text += f"💵 <b>Общая сумма: {total_price:,.0f} сум</b>\n"
            summary_text += f"⏱️ Примерный срок: {order.product.estimated_days} дней\n\n"
            summary_text += "💳 <b>Статус оплаты:</b> Ожидается ⏳\n\n"
            summary_text += "━━━━━━━━━━━━━━━━━━━━\n\n"
            summary_text += "💳 <b>Данные карты:</b>\n"
            summary_text += f"💳 Номер карты: <code>{card_number}</code>\n"
            summary_text += f"👤 Владелец карты: {card_holder}\n\n"
            summary_text += "📤 <b>Пожалуйста, загрузите чек об оплате</b>\n"
            summary_text += "📎 Разрешенные форматы: JPG, PNG, PDF, DOC, DOCX, HEIC, HEIF"
        else:  # English
            summary_text = "📋 <b>Order Summary</b>\n\n"
            summary_text += f"📄 Order number: #{order.id}\n"
            summary_text += f"📎 Total files: {order.files.count()}\n"
            summary_text += f"📄 Total pages: {order.total_pages}\n"
            if lang_name:
                summary_text += f"🌐 Service language: {lang_name}\n"
            if is_dynamic:
                summary_text += f"💰 1st page price: {first_page_price:,.0f} sum\n"
                if order.total_pages > 1:
                    summary_text += f"💰 Other pages: {other_page_price:,.0f} sum\n"
            summary_text += f"💵 Base price: {base_price:,.0f} sum\n"

            # Add copy information
            if order.copy_number > 0:
                summary_text += f"📋 Number of copies: {order.copy_number}\n"
                summary_text += (
                    f"💳 Copy charges ({copy_percentage}%): {copy_charge:,.0f} sum\n"
                )

            summary_text += f"💵 <b>Total amount: {total_price:,.0f} sum</b>\n"
            summary_text += f"⏱️ Estimated time: {order.product.estimated_days} days\n\n"
            summary_text += "💳 <b>Payment status:</b> Pending ⏳\n\n"
            summary_text += "━━━━━━━━━━━━━━━━━━━━\n\n"
            summary_text += "💳 <b>Card Details:</b>\n"
            summary_text += f"💳 Card number: <code>{card_number}</code>\n"
            summary_text += f"👤 Card holder: {card_holder}\n\n"
            summary_text += "📤 <b>Please upload your payment receipt</b>\n"
            summary_text += "📎 Allowed formats: JPG, PNG, PDF, DOC, DOCX, HEIC, HEIF"

        # Create markup with send receipt and back buttons
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        send_receipt_button = types.KeyboardButton(
            text=(
                "📤 Chekni yuborish"
                if language == "uz"
                else "📤 Send Receipt" if language == "en" else "📤 Отправить чек"
            )
        )
        back_button = types.KeyboardButton(
            text=get_text("back_to_upload_docs", language)
        )
        markup.add(send_receipt_button, back_button)

        # Send summary with buttons
        bot.send_message(
            chat_id=message.chat.id,
            text=summary_text,
            reply_markup=markup,
            parse_mode="HTML",
        )

        # Set step for receipt upload
        update_user_step(user_id, STEP_UPLOADING_RECEIPT)

    except Order.DoesNotExist:
        logger.debug(f" Order {order_id} not found")
        bot.send_message(
            message.chat.id, get_text("order_not_found_restart", language)
        )
        clear_user_files(user_id)
        update_user_step(user_id, STEP_REGISTERED)
        show_categorys(message, language)
    except Exception as e:
        logger.error(f" Failed to handle card payment: {e}")
        import traceback

        traceback.print_exc()
        bot.send_message(
            message.chat.id, get_text("error_general", language)
        )
        show_categorys(message, language)


def handle_finish_upload_message(message, language):
    """Handle finish upload button press from keyboard"""
    user_id = message.from_user.id

    # Check if user has uploaded files - access uploaded_files directly
    user_data = uploaded_files.get(user_id, {})

    logger.debug(f" Finish upload request from user {user_id}")
    logger.debug(f" User data: {user_data}")

    if not user_data or not user_data.get("files"):
        # No files uploaded, show error message
        bot.send_message(message.chat.id, get_text("upload_files_first", language))
        return

    # Check if doc_type_id exists
    if "doc_type_id" not in user_data:
        logger.debug(f" doc_type_id not found in user_data: {user_data}")
        bot.send_message(message.chat.id, get_text("doc_type_not_found", language))
        return

    logger.debug(f" Found doc_type_id: {user_data['doc_type_id']}")

    try:
        # Create order with uploaded files
        from orders.models import Order, OrderMedia
        from services.models import Product, Language
        from django.db import transaction

        user = get_bot_user(user_id)
        if not user:
            bot.send_message(message.chat.id, get_text("user_not_found", language))
            return
        
        # Validate branch assignment
        if not user.branch:
            bot.send_message(message.chat.id, get_text("error_no_branch_assigned", language))
            logger.error(f"User {user_id} has no branch assigned")
            show_main_menu(message, language)
            return
        
        try:
            doc_type = Product.objects.get(id=user_data["doc_type_id"])
        except Product.DoesNotExist:
            bot.send_message(message.chat.id, get_text("error_product_not_found", language))
            logger.error(f"Product {user_data.get('doc_type_id')} not found")
            return

        logger.debug(f" Creating order for user {user_id} with doc_type {doc_type.id}")

        # Get language ID from user data if available
        lang_id = user_data.get("lang_id")
        service_lang = None
        
        if lang_id:
            try:
                service_lang = Language.objects.get(id=lang_id)
            except Language.DoesNotExist:
                logger.warning(f" Language with ID {lang_id} not found")

        # Get copy number from user data (default to 0)
        copy_number = user_data.get("copy_number", 0)

        # Use atomic transaction to ensure all-or-nothing order creation
        with transaction.atomic():
            # Create order with language and copy number
            order = Order.objects.create(
                bot_user=user,
                product=doc_type,
                branch=user.branch,
                language=service_lang,
                total_pages=0,  # Will be calculated from files
                copy_number=copy_number,
                is_active=False,
                description="",
                payment_type="cash",  # Default, will be updated based on user choice
                total_price=0,  # Will be calculated based on pages, user type, and copies
            )

            total_pages = 0

            # Save all uploaded files (now from dictionary)
            for file_uid, file_info in user_data["files"].items():
                # Truncate file path if needed
                file_path = file_info["file_path"]
                if len(file_path) > 90:  # Leave some margin
                    logger.warning(f"File path too long: {file_path}")
                    file_path = file_path[:90]
                
                # Create OrderMedia entry
                order_file = OrderMedia.objects.create(
                    file=file_path, 
                    pages=file_info["pages"]
                )
                order.files.add(order_file)
                total_pages += file_info["pages"]

            # Update order with total pages and price
            order.total_pages = total_pages
            order.total_price = order.calculated_price
            order.save()

        logger.debug(f" Order created successfully: {order.id}")

        # Clear uploaded files for this user first
        clear_user_files(user_id)

        # Store order info for payment process (after clearing files)
        uploaded_files[user_id] = {"order_id": order.id}

        # Show payment options instead of going to main menu
        show_payment_options(message, language, order)

    except KeyError as e:
        logger.error(f" Missing required data in user_data: {e}")
        bot.send_message(message.chat.id, get_text("error_general", language))
        clear_user_files(user_id)
        show_main_menu(message, language)
    except Product.DoesNotExist:
        logger.error(f" Product not found for order creation")
        bot.send_message(message.chat.id, get_text("error_product_not_found", language))
        clear_user_files(user_id)
        show_main_menu(message, language)
    except Exception as e:
        logger.error(f" Failed to create order: {e}", exc_info=True)
        import traceback
        traceback.print_exc()
        bot.send_message(message.chat.id, get_text("error_general", language))
        clear_user_files(user_id)
        show_main_menu(message, language)


def handle_back_to_upload_docs_message(message, language):
    """Handle back to upload docs button press from keyboard"""
    user_id = message.from_user.id

    logger.debug(f" Back to upload docs request from user {user_id}")

    # Check if user has uploaded files and document type info
    user_data = uploaded_files.get(user_id, {})

    # If no data exists, start fresh
    if not user_data:
        logger.debug(f" No user data found, starting fresh")
        clear_user_files(user_id)
        update_user_step(user_id, STEP_REGISTERED)
        show_categorys(message, language)
        return

    if "order_id" in user_data:
        order_id = user_data["order_id"]
        logger.debug(f" Found order_id: {order_id}")

        try:
            # Get the order and restore files
            from orders.models import Order, OrderMedia

            order = Order.objects.get(id=order_id)

            # Build complete user data including language
            restored_data = {
                "doc_type_id": order.product.id,
                "service_id": order.product.category.id,
                "lang_id": order.language.id if order.language else None,
                "files": {},
            }

            # Restore files from order with unique IDs
            import time

            for idx, order_file in enumerate(order.files.all()):
                file_uid = f"{int(time.time() * 1000)}_{idx}"
                restored_data["files"][file_uid] = {
                    "file_path": order_file.file.name,
                    "file_name": order_file.file.name.split("/")[-1],
                    "pages": order_file.pages,
                    "file_size": (
                        order_file.file.size if hasattr(order_file.file, "size") else 0
                    ),
                }

            # Assign all at once to trigger save to persistent storage
            uploaded_files[user_id] = restored_data

            print(
                f"[DEBUG] Restored {len(uploaded_files[user_id]['files'])} files from order"
            )

            # Update user step
            update_user_step(user_id, STEP_UPLOADING_FILES)

            # Show upload interface
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
            finish_button = types.KeyboardButton(
                text=get_text("finish_upload", language)
            )
            back_button = types.KeyboardButton(
                text=get_text("back_to_documents", language)
            )
            markup.add(finish_button, back_button)

            upload_text = get_text("upload_files", language)
            upload_text += "\n\n📎 <b>Ruxsat etilgan formatlar:</b>\n"
            upload_text += "📄 DOC, DOCX, PDF\n"
            upload_text += "🖼️ JPG, PNG, GIF, BMP, TIFF, WEBP, HEIC, HEIF"

            bot.send_message(
                chat_id=message.chat.id,
                text=upload_text,
                reply_markup=markup,
                parse_mode="HTML",
            )

        except Order.DoesNotExist:
            logger.debug(f" Order {order_id} not found, starting fresh")
            # Order doesn't exist, start fresh
            clear_user_files(user_id)
            update_user_step(user_id, STEP_REGISTERED)
            show_categorys(message, language)
        except Exception as e:
            logger.error(f" Failed to restore order: {e}")
            bot.send_message(
                message.chat.id, get_text("error_general", language)
            )
            show_categorys(message, language)
    else:
        # No order found, start fresh
        logger.debug(f" No order_id found for user {user_id}")
        clear_user_files(user_id)
        update_user_step(user_id, STEP_REGISTERED)
        bot.send_message(message.chat.id, get_text("data_lost_restart", language))
        show_categorys(message, language)


def handle_cash_payment_message(message, language):
    """Handle cash payment button press from keyboard"""
    user_id = message.from_user.id

    logger.debug(f" Cash payment request from user {user_id}")

    # Get order_id from uploaded_files
    user_data = uploaded_files.get(user_id, {})
    if "order_id" not in user_data:
        bot.send_message(
            message.chat.id, get_text("order_not_found_restart", language)
        )
        return

    order_id = user_data["order_id"]

    try:
        from accounts.models import BotUser
        from orders.models import Order

        order = Order.objects.get(id=order_id)

        # Update order payment type to cash
        order.payment_type = "cash"
        order.status = "pending"
        order.is_active = True  # Mark as completed since cash payment is immediate
        order.save()

        # Forward order to channel
        forward_success = forward_order_to_channel(order, language)

        if not forward_success:
            logger.warning(f" Failed to forward order {order.id} to channel")

        # Clear uploaded files data
        clear_user_files(user_id)
        update_user_step(user_id, STEP_REGISTERED)

        # Generate order summary with cash payment status
        user = get_bot_user(user_id)
        if not user:
            logger.error(f" User not found for cash payment: {user_id}")
            return

        # Calculate pricing with copy charges
        base_price, copy_charge, total_price, copy_percentage = calculate_order_pricing(
            order, user
        )

        # Determine charging type
        is_dynamic = order.product.category.charging == "dynamic"

        # Calculate pricing based on user type
        if user.is_agency:
            first_page_price = order.product.agency_first_page_price
            other_page_price = order.product.agency_other_page_price
        else:
            first_page_price = order.product.ordinary_first_page_price
            other_page_price = order.product.ordinary_other_page_price

        # Get service language name
        lang_name = ""
        try:
            if order.language:
                lang_name = order.language.name
        except Exception:
            pass

        # Format user display with username if available
        user_display = user.name
        if user.username:
            user_display += f" (@{user.username})"

        # Create order summary message
        if language == "uz":
            cash_text = "✅ <b>Yuborildi!</b>\n\n"
            cash_text += "🟡 <b>To'lov holati:</b> Joyida (naqd pul)\n\n"
            cash_text += "📋 <b>Buyurtma ma'lumotlari:</b>\n"
            cash_text += f"👤 Mijoz: {user_display}\n"
            cash_text += f"📞 Telefon: {user.phone}\n"
            cash_text += f"📄 Buyurtma raqami: {order.id}\n"
            cash_text += f"📊 Jami sahifalar: {order.total_pages}\n"
            if lang_name:
                cash_text += f"🌍 Xizmat tili: {lang_name}\n"
            if is_dynamic:
                cash_text += f"💰 1-sahifa narxi: {first_page_price:,.0f} so'm\n"
                if order.total_pages > 1:
                    cash_text += f"💰 Qolgan sahifalar: {other_page_price:,.0f} so'm\n"
            cash_text += f"💵 Asosiy narx: {base_price:,.0f} so'm\n"

            # Add copy information
            if order.copy_number > 0:
                cash_text += f"📋 Nusxalar soni: {order.copy_number}\n"
                cash_text += f"💳 Nusxalar uchun to'lov ({copy_percentage}%): {copy_charge:,.0f} so'm\n"

            cash_text += f"💵 <b>Jami summa: {total_price:,.0f} so'm</b>\n"
            cash_text += f"📅 Taxminiy muddat: {order.product.estimated_days} kun\n\n"
            cash_text += "✅ Buyurtmangiz muvaffaqiyatli yuborildi!\n"
            cash_text += "📞 Operatorlarimiz tez orada siz bilan bog'lanishadi."
        elif language == "ru":
            cash_text = "✅ <b>Отправлено!</b>\n\n"
            cash_text += "🟡 <b>Статус оплаты:</b> На месте (наличными)\n\n"
            cash_text += "📋 <b>Информация о заказе:</b>\n"
            cash_text += f"👤 Клиент: {user_display}\n"
            cash_text += f"📞 Телефон: {user.phone}\n"
            cash_text += f"📄 Номер заказа: {order.id}\n"
            cash_text += f"📊 Всего страниц: {order.total_pages}\n"
            if lang_name:
                cash_text += f"🌍 Язык услуги: {lang_name}\n"
            if is_dynamic:
                cash_text += f"💰 Цена 1-й страницы: {first_page_price:,.0f} сум\n"
                if order.total_pages > 1:
                    cash_text += f"💰 Остальные страницы: {other_page_price:,.0f} сум\n"
            cash_text += f"💵 Базовая цена: {base_price:,.0f} сум\n"

            # Add copy information
            if order.copy_number > 0:
                cash_text += f"📋 Количество копий: {order.copy_number}\n"
                cash_text += (
                    f"💳 Оплата за копии ({copy_percentage}%): {copy_charge:,.0f} сум\n"
                )

            cash_text += f"💵 <b>Общая сумма: {total_price:,.0f} сум</b>\n"
            cash_text += f"📅 Примерный срок: {order.product.estimated_days} дней\n\n"
            cash_text += "✅ Ваш заказ успешно отправлен!\n"
            cash_text += "📞 Наши операторы свяжутся с вами в ближайшее время."
        else:  # English
            cash_text = "✅ <b>Sent!</b>\n\n"
            cash_text += "🟡 <b>Payment status:</b> On place (cash)\n\n"
            cash_text += "📋 <b>Order information:</b>\n"
            cash_text += f"👤 Client: {user_display}\n"
            cash_text += f"📞 Phone: {user.phone}\n"
            cash_text += f"📄 Order number: {order.id}\n"
            cash_text += f"📊 Total pages: {order.total_pages}\n"
            if lang_name:
                cash_text += f"🌐 Service language: {lang_name}\n"
            if is_dynamic:
                cash_text += f"💰 1st page price: {first_page_price:,.0f} sum\n"
                if order.total_pages > 1:
                    cash_text += f"💰 Other pages: {other_page_price:,.0f} sum\n"
            cash_text += f"💵 Base price: {base_price:,.0f} sum\n"

            # Add copy information
            if order.copy_number > 0:
                cash_text += f"📋 Number of copies: {order.copy_number}\n"
                cash_text += (
                    f"💳 Copy charges ({copy_percentage}%): {copy_charge:,.0f} sum\n"
                )

            cash_text += f"💵 <b>Total amount: {total_price:,.0f} sum</b>\n"
            cash_text += f"📅 Estimated time: {order.product.estimated_days} days\n\n"
            cash_text += "✅ Your order has been successfully sent!\n"
            cash_text += "📞 Our operators will contact you shortly."

        # Send order summary first
        bot.send_message(chat_id=message.chat.id, text=cash_text, parse_mode="HTML")

        # Send branch location for pickup
        if order.branch:
            send_branch_location(message.chat.id, order.branch, language)

        # Then show main menu
        show_main_menu(message, language)

    except Order.DoesNotExist:
        logger.debug(f" Order {order_id} not found")
        bot.send_message(
            message.chat.id, get_text("order_not_found_restart", language)
        )
        clear_user_files(user_id)
        update_user_step(user_id, STEP_REGISTERED)
        show_categorys(message, language)
    except Exception as e:
        logger.error(f" Failed to handle cash payment: {e}")
        import traceback

        traceback.print_exc()
        bot.send_message(
            message.chat.id, get_text("error_general", language)
        )
        show_categorys(message, language)


def handle_back_to_documents_message(message, language):
    """Handle back to documents button press from keyboard"""
    user_id = message.from_user.id

    # Get service_id from uploaded files
    user_data = uploaded_files.get(user_id, {})

    if user_data and "service_id" in user_data:
        service_id = user_data["service_id"]
        logger.debug(f" Going back to documents for service_id: {service_id}")
        show_products(message, language, service_id)
    else:
        # Fallback if service_id not found - reset and go to main services
        print(
            f"[DEBUG] No service_id found for user {user_id}, resetting to main services"
        )
        # Clear any incomplete data
        clear_user_files(user_id)
        update_user_step(user_id, STEP_REGISTERED)
        bot.send_message(message.chat.id, get_text("data_lost_use_service", language))
        show_categorys(message, language)


def handle_back_to_copy_number_message(message, language):
    """Handle back to copy number button press from keyboard"""
    user_id = message.from_user.id

    # Get document type info from uploaded_files
    user_data = uploaded_files.get(user_id, {})
    doc_type_id = user_data.get("doc_type_id")
    lang_id = user_data.get("lang_id")

    if doc_type_id:
        try:
            from services.models import Product, Language

            doc_type = Product.objects.get(id=doc_type_id)
            lang_name = Language.objects.get(id=lang_id).name if lang_id else ""

            # Clear any uploaded files but keep doc_type and service info
            if user_id in uploaded_files:
                files_to_keep = {
                    "doc_type_id": uploaded_files[user_id].get("doc_type_id"),
                    "service_id": uploaded_files[user_id].get("service_id"),
                    "lang_id": uploaded_files[user_id].get("lang_id"),
                    "lang_name": uploaded_files[user_id].get("lang_name"),
                }
                uploaded_files[user_id] = files_to_keep

            # Show copy number selection again
            show_copy_number_selection(message, language, doc_type, lang_name)

        except Exception as e:
            logger.error(f" Failed to go back to copy number: {e}")
            bot.send_message(message.chat.id, get_text("error_occurred", language))
            show_categorys(message, language)
    else:
        # No doc_type found, go back to services
        clear_user_files(user_id)
        update_user_step(user_id, STEP_REGISTERED)
        bot.send_message(message.chat.id, get_text("error_occurred", language))
        show_categorys(message, language)


@bot.callback_query_handler(func=lambda call: call.data.startswith("payment_cash_"))
def handle_payment_cash(call):
    """Handle cash payment selection"""
    language = get_user_language(call.message.chat.id)
    order_id = int(call.data.split("_")[2])

    try:
        from orders.models import Order

        order = Order.objects.get(id=order_id)

        # Update order payment type
        order.payment_type = "cash"
        order.save()

        # Show cash payment information
        cash_text = get_text("payment_done", language)
        cash_text += f"\n\n📋 {get_text('order_number', language)}: {order.id}"
        cash_text += f"\n💰 {get_text('total_amount', language)}: {order.total_price}"
        cash_text += f"\n📞 {get_text('payment_receipt_received', language)}"

        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=cash_text,
            parse_mode="HTML",
        )

        # Mark order as completed
        order.is_active = True
        order.save()

    except Exception as e:
        logger.error(f" Failed to handle cash payment: {e}")
        bot.answer_callback_query(call.id, get_text("error_general", language))


def handle_main_menu(call):
    bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.message_id)
    show_main_menu(call.message, get_user_language(call.message.chat.id))


@bot.callback_query_handler(func=lambda call: call.data == "edit_profile")
def handle_profile_actions(call):
    show_edit_profile_menu(call.message)


def show_edit_profile_menu(message):
    user_id = message.chat.id
    language = get_user_language(user_id)
    update_user_step(user_id, STEP_EDITING_PROFILE)

    markup = types.InlineKeyboardMarkup(row_width=2)
    edit_name_button = types.InlineKeyboardButton(
        text=get_text("edit_name", language), callback_data="edit_name"
    )
    edit_phone_button = types.InlineKeyboardButton(
        text=get_text("edit_phone", language), callback_data="edit_phone"
    )
    edit_language_button = types.InlineKeyboardButton(
        text=get_text("edit_language", language), callback_data="edit_language"
    )
    back_button = types.InlineKeyboardButton(
        text=get_text("main_menu", language), callback_data="main_menu"
    )

    markup.add(edit_name_button, edit_phone_button)
    markup.add(edit_language_button)
    markup.add(back_button)


@bot.callback_query_handler(func=lambda call: call.data == "edit_name")
def handle_edit_name_request(call):
    user_id = call.message.chat.id
    language = get_user_language(user_id)
    update_user_step(user_id, STEP_EDITING_NAME)
    bot.send_message(call.message.chat.id, get_text("enter_new_name", language))


@bot.callback_query_handler(func=lambda call: call.data == "edit_phone")
def handle_edit_phone_request(call):
    user_id = call.message.chat.id
    language = get_user_language(user_id)
    update_user_step(user_id, STEP_EDITING_PHONE)

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    contact_btn = types.KeyboardButton(
        get_text("phone_button", language), request_contact=True
    )
    markup.add(contact_btn)

    bot.send_message(
        call.message.chat.id, get_text("enter_new_phone", language), reply_markup=markup
    )


@bot.message_handler(commands=["admin"])
def admin_panel(message):
    user_id = message.from_user.id
    language = get_user_language(user_id)
    
    if user_id in ADMINS:
        markup = types.InlineKeyboardMarkup()
        btn1 = types.InlineKeyboardButton("👥 Users", callback_data="admin_users")
        btn2 = types.InlineKeyboardButton("📋 Orders", callback_data="admin_orders")
        btn3 = types.InlineKeyboardButton("📊 Stats", callback_data="admin_stats")
        markup.add(btn1, btn2)
        markup.add(btn3)
        bot.send_message(
            message.chat.id,
            "🔧 <b>Admin Panel</b>\n\nChoose an option:",
            reply_markup=markup,
            parse_mode="HTML",
        )
    else:
        bot.send_message(message.chat.id, get_text("no_admin_permission", language))


@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_"))
def handle_admin_callbacks(call):
    if call.from_user.id not in ADMINS:
        return
    if call.data == "admin_users":
        try:
            from accounts.models import BotUser
            
            center = get_current_center()
            if center:
                total_users = BotUser.objects.filter(center=center).count()
                active_users = BotUser.objects.filter(center=center, is_active=True).count()
            else:
                total_users = BotUser.objects.count()
                active_users = BotUser.objects.filter(is_active=True).count()
            text = f"👥 <b>Users Statistics</b>\n\n"
            text += f"Total users: {total_users}\n"
            text += f"Active users: {active_users}\n"
            text += f"Inactive users: {total_users - active_users}"
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id)
        except:
            bot.edit_message_text(
                get_text("error_stats", "en"),
                call.message.chat.id,
                call.message.message_id,
            )


@bot.callback_query_handler(func=lambda call: call.data.startswith("delete_file_"))
def handle_delete_file(call):
    user_id = call.message.chat.id
    language = get_user_language(user_id)

    try:
        # Extract file_uid from callback data (format: delete_file_{file_uid})
        file_uid = call.data.replace("delete_file_", "")
        logger.debug(f" Delete request for file_uid: {file_uid}")

        # Get user's uploaded files
        current_data = uploaded_files.get(user_id)
        if not current_data:
            current_data = {}
        else:
            # Convert to regular dict for modification
            current_data = dict(current_data)
            
        if not current_data or "files" not in current_data:
            logger.debug(f" No user data found for user {user_id}")
            bot.answer_callback_query(call.id, get_text("no_files_to_delete", language))
            return

        files = current_data["files"]
        logger.debug(f" User has {len(files)} files")

        if not files:
            logger.debug(f" Files dict is empty for user {user_id}")
            bot.answer_callback_query(call.id, get_text("no_files_to_delete", language))
            return

        if file_uid not in files:
            logger.debug(f" File UID {file_uid} not found in files: {list(files.keys())}")
            bot.answer_callback_query(call.id, get_text("file_not_found", language))
            return

        # Get file info before deletion
        file_info = files[file_uid]
        file_path = file_info["file_path"]
        file_name = file_info["file_name"]

        logger.debug(f" Deleting file: {file_name} at path: {file_path}")

        # Delete file from storage if it exists
        from django.core.files.storage import default_storage

        if default_storage.exists(file_path):
            default_storage.delete(file_path)
            logger.debug(f" Successfully deleted file from storage: {file_path}")
        else:
            logger.debug(f" File not found in storage: {file_path}")

        # Remove file from the dict
        del files[file_uid]
        
        # Reassign to trigger save to persistent storage
        uploaded_files[user_id] = current_data
        logger.debug(f" Successfully removed file from uploaded_files: {file_name}")

        # Send confirmation message first (before deleting the original message)
        if language == "uz":
            confirm_text = f"✅ Fayl muvaffaqiyatli o'chirildi!\n📄 {file_name}"
        elif language == "ru":
            confirm_text = f"✅ Файл успешно удален!\n📄 {file_name}"
        else:  # English
            confirm_text = f"✅ File successfully deleted!\n📄 {file_name}"

        confirmation = bot.send_message(call.message.chat.id, confirm_text)
        logger.debug(f" Sent confirmation message {confirmation.message_id}")

        # Try to delete the message with the file (might fail if already deleted)
        try:
            bot.delete_message(
                chat_id=call.message.chat.id, message_id=call.message.message_id
            )
            logger.debug(f" Successfully deleted message {call.message.message_id}")
        except Exception as e:
            logger.debug(f" Failed to delete message {call.message.message_id}: {e}")
            # Don't fail the whole operation if message deletion fails

        # Update totals message
        update_totals_message(user_id, language)

    except Exception as e:
        logger.error(f" Failed to delete file: {e}")
        import traceback

        traceback.print_exc()
        bot.answer_callback_query(call.id, get_text("delete_file_failed", language))


from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods


@csrf_exempt
@require_http_methods(["GET", "POST"])
def index(request):
    if request.method == "GET":
        from django.http import HttpResponse

        return HttpResponse("<h1>Bot Webhook Active</h1>", status=200)

    # POST request
    try:
        import json

        update_data = request.body.decode("utf-8")
        update_dict = json.loads(update_data)

        # Check if update is from a bot and ignore it
        if "message" in update_dict:
            if update_dict["message"].get("from", {}).get("is_bot", False):
                logger.debug("Ignoring message from bot")
                return JsonResponse({"ok": True}, status=200)

        if "callback_query" in update_dict:
            if update_dict["callback_query"].get("from", {}).get("is_bot", False):
                logger.debug("Ignoring callback from bot")
                return JsonResponse({"ok": True}, status=200)

        logger.debug(f"Received update: {update_data[:100]}...")  # Debug

        bot.process_new_updates([telebot.types.Update.de_json(update_data)])

        return JsonResponse({"ok": True}, status=200)

    except Exception as e:
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()
        return JsonResponse({"ok": False, "error": str(e)}, status=200)
