"""
Bot Handlers Registration Module

This module provides functions to register all bot handlers to any TeleBot instance.
This enables multi-tenant bot support where each Translation Center has its own bot.
"""
import logging
from telebot import types
from telebot.apihelper import ApiTelegramException

logger = logging.getLogger(__name__)


def register_all_handlers(bot, center=None):
    """
    Register all message and callback handlers to a bot instance.
    
    Args:
        bot: TeleBot instance to register handlers to
        center: Optional TranslationCenter instance for context
    """
    # Import all the helper functions from main
    from .main import (
        # Helper functions
        get_translated_field,
        get_text,
        create_or_update_user,
        send_message,
        update_user_step,
        get_user_language,
        get_user_step,
        count_document_pages,
        is_valid_file_format,
        # Step constants
        STEP_LANGUAGE_SELECTED,
        STEP_REGISTRATION_STARTED,
        STEP_NAME_REQUESTED,
        STEP_PHONE_REQUESTED,
        STEP_REGISTERED,
        STEP_EDITING_PROFILE,
        STEP_EDITING_NAME,
        STEP_EDITING_PHONE,
        STEP_SELECTING_SERVICE,
        STEP_SELECTING_DOCUMENT,
        STEP_SELECTING_COPY_NUMBER,
        STEP_UPLOADING_FILES,
        STEP_PAYMENT_METHOD,
        STEP_AWAITING_PAYMENT,
        STEP_UPLOADING_RECEIPT,
        # Data stores
        user_data,
        uploaded_files,
    )
    from .translations import get_text as translations_get_text
    from accounts.models import BotUser
    
    # =========================================================================
    # Message Handlers
    # =========================================================================
    
    @bot.message_handler(commands=["start"])
    def start(message):
        """Handle /start command"""
        import uuid as uuid_module
        
        user_id = message.from_user.id
        username = message.from_user.username
        first_name = message.from_user.first_name or ""
        language = "uz"
        
        # Check for agency invitation link
        is_agency_invite = False
        agency_token = None
        agency = None
        agency_center_id = None
        
        if len(message.text.split()) > 1:
            param = message.text.split()[1]
            if param.startswith("agency_"):
                try:
                    # Parse: agency_{token} or agency_{token}_{center_id}
                    parts = param[7:].split("_")
                    if len(parts) >= 1:
                        # First part is the UUID token (may contain hyphens from UUID format)
                        # UUID format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx (36 chars)
                        # But in the link it's without hyphens, so we reconstruct
                        token_part = parts[0]
                        # Check if there are more parts that could be center_id
                        # The token is 32 chars hex (no hyphens) or 36 chars (with hyphens)
                        if len(token_part) == 32:
                            agency_token = token_part
                            # Check for center_id at the end
                            if len(parts) > 1:
                                try:
                                    agency_center_id = int(parts[-1])
                                except ValueError:
                                    pass
                        else:
                            # Token might include hyphens, need to parse differently
                            # Full param minus "agency_" prefix
                            full_token = param[7:]
                            # Try to find center_id at the end
                            last_underscore = full_token.rfind("_")
                            if last_underscore > 0:
                                try:
                                    agency_center_id = int(full_token[last_underscore + 1:])
                                    agency_token = full_token[:last_underscore]
                                except ValueError:
                                    # No center_id, full string is token
                                    agency_token = full_token
                            else:
                                agency_token = full_token
                        
                        uuid_obj = uuid_module.UUID(agency_token)
                        agency = BotUser.get_agency_by_token(str(uuid_obj), center_id=agency_center_id)
                        if agency:
                            is_agency_invite = True
                except (ValueError, IndexError) as e:
                    logger.error(f"Invalid agency token: {e}")
        
        # Check if user exists
        existing_user = BotUser.objects.filter(user_id=user_id).first()
        
        if existing_user:
            language = existing_user.language
            
            if is_agency_invite and agency:
                if existing_user.is_agency:
                    bot.send_message(message.chat.id, get_text("already_agency", language))
                elif existing_user.agency:
                    bot.send_message(message.chat.id, 
                        get_text("already_linked_to_agency", language).format(existing_user.agency.name))
                else:
                    existing_user.agency = agency
                    existing_user.save()
                    bot.send_message(message.chat.id,
                        get_text("agency_linked_success", language).format(agency.name))
            
            if existing_user.is_active:
                show_main_menu(message, language)
            else:
                show_language_selection(message)
            return
        
        # New user
        show_language_selection(message)
    
    def show_language_selection(message):
        """Show language selection buttons"""
        markup = types.InlineKeyboardMarkup(row_width=3)
        markup.add(
            types.InlineKeyboardButton("🇺🇿 O'zbekcha", callback_data="lang_uz"),
            types.InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru"),
            types.InlineKeyboardButton("🇬🇧 English", callback_data="lang_en"),
        )
        bot.send_message(
            message.chat.id,
            "🌐 Tilni tanlang / Выберите язык / Select language:",
            reply_markup=markup,
        )
    
    def show_main_menu(message, language):
        """Show main menu"""
        from .main import show_main_menu as main_show_main_menu
        # Use the original implementation but with our bot
        main_show_main_menu(message, language)
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith("lang_"))
    def handle_language_selection(call):
        """Handle language selection"""
        from .main import handle_language_selection as main_handle
        main_handle(call)
    
    @bot.message_handler(content_types=["contact"])
    def handle_contact(message):
        """Handle contact sharing"""
        from .main import handle_contact as main_handle
        main_handle(message)
    
    # NOTE: Name and phone input are handled by the general text handler in main.py
    # (handle_text_messages function) which checks for STEP_NAME_REQUESTED, 
    # STEP_EDITING_NAME, STEP_PHONE_REQUESTED, and STEP_EDITING_PHONE.
    # Do NOT register separate handlers here as it causes duplicate message handling.
    
    # =========================================================================
    # Callback Query Handlers
    # =========================================================================
    
    @bot.callback_query_handler(func=lambda call: call.data == "edit_profile")
    def handle_edit_profile(call):
        from .main import handle_edit_profile as main_handle
        main_handle(call)
    
    @bot.callback_query_handler(func=lambda call: call.data == "edit_name")
    def handle_edit_name(call):
        from .main import handle_edit_name as main_handle
        main_handle(call)
    
    @bot.callback_query_handler(func=lambda call: call.data == "edit_phone")
    def handle_edit_phone(call):
        from .main import handle_edit_phone as main_handle
        main_handle(call)
    
    @bot.callback_query_handler(func=lambda call: call.data == "edit_language")
    def handle_edit_language(call):
        from .main import handle_edit_language as main_handle
        main_handle(call)
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith("profile_lang_"))
    def handle_profile_language(call):
        from .main import handle_profile_language as main_handle
        main_handle(call)
    
    @bot.callback_query_handler(func=lambda call: call.data == "main_menu")
    def handle_main_menu(call):
        from .main import handle_main_menu as main_handle
        main_handle(call)
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith("category_"))
    def handle_category_selection(call):
        from .main import handle_service_selection as main_handle
        main_handle(call)
    
    @bot.callback_query_handler(func=lambda call: call.data == "back_to_services")
    def handle_back_to_services(call):
        from .main import handle_back_to_services as main_handle
        main_handle(call)
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith("copy_num_"))
    def handle_copy_number(call):
        from .main import handle_copy_number as main_handle
        main_handle(call)
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith("doc_type_"))
    def handle_doc_type(call):
        from .main import handle_doc_type as main_handle
        main_handle(call)
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith("payment_card_"))
    def handle_payment_card(call):
        from .main import handle_payment_card as main_handle
        main_handle(call)
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith("payment_cash_"))
    def handle_payment_cash(call):
        from .main import handle_payment_cash as main_handle
        main_handle(call)
    
    @bot.callback_query_handler(func=lambda call: call.data.startswith("payment_receipt_"))
    def handle_payment_receipt(call):
        from .main import handle_payment_receipt as main_handle
        main_handle(call)
    
    # =========================================================================
    # File Upload Handlers
    # =========================================================================
    
    @bot.message_handler(content_types=["document", "photo"])
    def handle_file_upload(message):
        from .main import handle_file_upload as main_handle
        main_handle(message)
    
    logger.info(f"Registered all handlers for bot")
    return bot
