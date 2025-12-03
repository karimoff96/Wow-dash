"""
Broadcast Service for Marketing Posts

Handles the actual sending of marketing messages via Telegram
with proper rate limiting, batching, retry logic, and error handling.
"""
import time
import logging
from decimal import Decimal
from datetime import timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.conf import settings

import telebot
from telebot.apihelper import ApiTelegramException

from accounts.models import BotUser
from organizations.models import TranslationCenter, Branch
from .models import (
    MarketingPost, BroadcastRecipient, 
    UserBroadcastPreference, BroadcastRateLimit
)

logger = logging.getLogger(__name__)


# Telegram error codes
TELEGRAM_USER_BLOCKED = 403
TELEGRAM_USER_DEACTIVATED = 400
TELEGRAM_CHAT_NOT_FOUND = 400
TELEGRAM_TOO_MANY_REQUESTS = 429


@dataclass
class BroadcastResult:
    """Result of a broadcast operation"""
    success: bool
    sent_count: int
    failed_count: int
    skipped_count: int
    errors: List[str]
    duration_seconds: float


class BroadcastError(Exception):
    """Custom exception for broadcast errors"""
    pass


class BroadcastService:
    """
    Service for handling marketing broadcasts.
    Implements safe patterns: batching, rate-limiting, retry, and multi-tenant support.
    """
    
    # Default rate limits (can be overridden per center)
    DEFAULT_BATCH_SIZE = 50
    DEFAULT_BATCH_DELAY = 3  # seconds
    DEFAULT_MESSAGES_PER_SECOND = 25
    MAX_RETRIES = 3
    RETRY_DELAY = 5  # seconds
    
    def __init__(self, post: MarketingPost):
        self.post = post
        self.bot = None
        self.rate_limit = None
        self._setup()
    
    def _setup(self):
        """Initialize bot and rate limit config"""
        # Get bot token based on scope
        bot_token = self._get_bot_token()
        if not bot_token:
            raise BroadcastError("No bot token available for this broadcast scope")
        
        self.bot = telebot.TeleBot(bot_token, parse_mode="HTML", threaded=False)
        
        # Get rate limit config
        if self.post.target_center:
            self.rate_limit = BroadcastRateLimit.get_or_create_for_center(
                self.post.target_center
            )
    
    def _get_bot_token(self) -> Optional[str]:
        """Get appropriate bot token based on scope"""
        if self.post.target_scope == MarketingPost.SCOPE_ALL:
            # Platform-wide: use default bot from settings
            return getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
        
        elif self.post.target_scope == MarketingPost.SCOPE_CENTER:
            if self.post.target_center and self.post.target_center.bot_token:
                return self.post.target_center.bot_token
        
        elif self.post.target_scope == MarketingPost.SCOPE_BRANCH:
            if self.post.target_branch and self.post.target_branch.center:
                center = self.post.target_branch.center
                if center.bot_token:
                    return center.bot_token
        
        # Fallback to default
        return getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
    
    def get_recipients(self) -> List[BotUser]:
        """
        Get list of recipients based on post scope.
        Respects multi-tenant boundaries and user preferences.
        """
        base_query = BotUser.objects.filter(
            is_active=True,
            user_id__isnull=False  # Must have Telegram ID
        )
        
        # Filter by scope
        if self.post.target_scope == MarketingPost.SCOPE_ALL:
            # Platform-wide - all active users
            pass
        
        elif self.post.target_scope == MarketingPost.SCOPE_CENTER:
            if not self.post.target_center:
                return []
            # All users from branches belonging to this center
            center_branches = self.post.target_center.branches.values_list('id', flat=True)
            base_query = base_query.filter(branch_id__in=center_branches)
        
        elif self.post.target_scope == MarketingPost.SCOPE_BRANCH:
            if not self.post.target_branch:
                return []
            base_query = base_query.filter(branch=self.post.target_branch)
        
        # Filter by customer type
        if not self.post.include_b2c and not self.post.include_b2b:
            return []
        
        if not self.post.include_b2c:
            base_query = base_query.filter(is_agency=True)
        elif not self.post.include_b2b:
            base_query = base_query.filter(is_agency=False)
        
        # Exclude users who opted out
        opted_out_users = UserBroadcastPreference.objects.filter(
            receive_marketing=False
        ).values_list('bot_user_id', flat=True)
        
        base_query = base_query.exclude(id__in=opted_out_users)
        
        return list(base_query.distinct())
    
    def prepare_recipients(self) -> int:
        """
        Prepare recipient records for tracking.
        Returns count of recipients.
        """
        recipients = self.get_recipients()
        
        # Create recipient records
        recipient_objects = []
        for user in recipients:
            recipient_objects.append(
                BroadcastRecipient(
                    post=self.post,
                    bot_user=user,
                    status=BroadcastRecipient.STATUS_PENDING
                )
            )
        
        # Bulk create, ignoring duplicates
        BroadcastRecipient.objects.bulk_create(
            recipient_objects,
            ignore_conflicts=True
        )
        
        # Update post total
        total = BroadcastRecipient.objects.filter(
            post=self.post,
            status=BroadcastRecipient.STATUS_PENDING
        ).count()
        
        self.post.total_recipients = total
        self.post.save(update_fields=['total_recipients', 'updated_at'])
        
        return total
    
    def send_message(self, user: BotUser) -> Tuple[bool, Optional[int], Optional[str]]:
        """
        Send message to a single user.
        Returns (success, message_id, error_message)
        """
        if not user.user_id:
            return False, None, "No Telegram user ID"
        
        try:
            # Send based on content type
            if self.post.content_type == MarketingPost.CONTENT_TEXT:
                msg = self.bot.send_message(
                    chat_id=user.user_id,
                    text=self.post.content,
                    disable_web_page_preview=False
                )
            
            elif self.post.content_type == MarketingPost.CONTENT_PHOTO:
                if self.post.media_file:
                    with open(self.post.media_file.path, 'rb') as photo:
                        msg = self.bot.send_photo(
                            chat_id=user.user_id,
                            photo=photo,
                            caption=self.post.content
                        )
                else:
                    msg = self.bot.send_message(
                        chat_id=user.user_id,
                        text=self.post.content
                    )
            
            elif self.post.content_type == MarketingPost.CONTENT_VIDEO:
                if self.post.media_file:
                    with open(self.post.media_file.path, 'rb') as video:
                        msg = self.bot.send_video(
                            chat_id=user.user_id,
                            video=video,
                            caption=self.post.content
                        )
                else:
                    msg = self.bot.send_message(
                        chat_id=user.user_id,
                        text=self.post.content
                    )
            
            elif self.post.content_type == MarketingPost.CONTENT_DOCUMENT:
                if self.post.media_file:
                    with open(self.post.media_file.path, 'rb') as doc:
                        msg = self.bot.send_document(
                            chat_id=user.user_id,
                            document=doc,
                            caption=self.post.content
                        )
                else:
                    msg = self.bot.send_message(
                        chat_id=user.user_id,
                        text=self.post.content
                    )
            
            else:
                msg = self.bot.send_message(
                    chat_id=user.user_id,
                    text=self.post.content
                )
            
            return True, msg.message_id, None
        
        except ApiTelegramException as e:
            error_msg = str(e)
            
            # Check for specific errors
            if e.error_code == TELEGRAM_USER_BLOCKED:
                return False, None, "User blocked the bot"
            elif e.error_code == TELEGRAM_TOO_MANY_REQUESTS:
                # Rate limited - should retry
                retry_after = getattr(e, 'retry_after', 30)
                time.sleep(retry_after)
                return False, None, f"Rate limited, retry after {retry_after}s"
            
            return False, None, error_msg
        
        except Exception as e:
            return False, None, str(e)
    
    def send_with_retry(
        self, 
        recipient: BroadcastRecipient
    ) -> Tuple[bool, Optional[str]]:
        """
        Send message with retry logic.
        Returns (success, error_message)
        """
        for attempt in range(self.MAX_RETRIES):
            success, msg_id, error = self.send_message(recipient.bot_user)
            
            if success:
                recipient.status = BroadcastRecipient.STATUS_DELIVERED
                recipient.telegram_message_id = msg_id
                recipient.sent_at = timezone.now()
                recipient.save()
                return True, None
            
            # Check if error is permanent (no retry needed)
            if error and ('blocked' in error.lower() or 'deactivated' in error.lower()):
                recipient.status = BroadcastRecipient.STATUS_BLOCKED
                recipient.error_message = error
                recipient.save()
                return False, error
            
            # Increment retry count
            recipient.retry_count = attempt + 1
            recipient.error_message = error
            recipient.save()
            
            # Wait before retry (except for last attempt)
            if attempt < self.MAX_RETRIES - 1:
                time.sleep(self.RETRY_DELAY)
        
        # All retries failed
        recipient.status = BroadcastRecipient.STATUS_FAILED
        recipient.save()
        return False, recipient.error_message
    
    def execute(self, async_mode: bool = False) -> BroadcastResult:
        """
        Execute the broadcast.
        
        Args:
            async_mode: If True, run in background (for Celery integration)
        
        Returns:
            BroadcastResult with statistics
        """
        start_time = time.time()
        errors = []
        sent_count = 0
        failed_count = 0
        skipped_count = 0
        
        # Update post status
        self.post.status = MarketingPost.STATUS_SENDING
        self.post.sent_at = timezone.now()
        self.post.save(update_fields=['status', 'sent_at', 'updated_at'])
        
        try:
            # Get pending recipients
            pending_recipients = BroadcastRecipient.objects.filter(
                post=self.post,
                status=BroadcastRecipient.STATUS_PENDING
            ).select_related('bot_user')
            
            # Get rate limit config
            batch_size = (
                self.rate_limit.batch_size 
                if self.rate_limit 
                else self.DEFAULT_BATCH_SIZE
            )
            batch_delay = (
                self.rate_limit.batch_delay 
                if self.rate_limit 
                else self.DEFAULT_BATCH_DELAY
            )
            
            # Process in batches
            total = pending_recipients.count()
            processed = 0
            
            while processed < total:
                batch = pending_recipients[processed:processed + batch_size]
                
                for recipient in batch:
                    # Check if post was paused/cancelled
                    self.post.refresh_from_db()
                    if self.post.status in [
                        MarketingPost.STATUS_PAUSED, 
                        MarketingPost.STATUS_CANCELLED
                    ]:
                        logger.info(f"Broadcast {self.post.id} was stopped")
                        break
                    
                    # Send message
                    success, error = self.send_with_retry(recipient)
                    
                    if success:
                        sent_count += 1
                    else:
                        if 'blocked' in (error or '').lower():
                            skipped_count += 1
                        else:
                            failed_count += 1
                            if error:
                                errors.append(f"User {recipient.bot_user_id}: {error}")
                    
                    # Update post counts periodically
                    if (sent_count + failed_count) % 10 == 0:
                        self._update_counts(sent_count, failed_count)
                
                processed += batch_size
                
                # Delay between batches
                if processed < total:
                    time.sleep(batch_delay)
            
            # Final update
            self.post.sent_count = sent_count
            self.post.delivered_count = sent_count
            self.post.failed_count = failed_count
            self.post.status = MarketingPost.STATUS_SENT
            self.post.completed_at = timezone.now()
            
            if errors:
                self.post.last_error = "\n".join(errors[:10])  # Keep first 10 errors
            
            self.post.save()
            
        except Exception as e:
            logger.exception(f"Broadcast failed: {e}")
            self.post.status = MarketingPost.STATUS_FAILED
            self.post.last_error = str(e)
            self.post.save()
            errors.append(str(e))
        
        duration = time.time() - start_time
        
        return BroadcastResult(
            success=self.post.status == MarketingPost.STATUS_SENT,
            sent_count=sent_count,
            failed_count=failed_count,
            skipped_count=skipped_count,
            errors=errors[:10],
            duration_seconds=round(duration, 2)
        )
    
    def _update_counts(self, sent: int, failed: int):
        """Update post counts during broadcast"""
        MarketingPost.objects.filter(id=self.post.id).update(
            sent_count=sent,
            delivered_count=sent,
            failed_count=failed
        )
    
    @staticmethod
    def preview_message(post: MarketingPost, user: BotUser) -> str:
        """
        Generate preview of message as it would appear.
        """
        preview = f"📢 <b>Preview</b>\n\n"
        preview += f"<b>To:</b> {user.display_name}\n"
        preview += f"<b>Type:</b> {post.get_content_type_display()}\n\n"
        preview += f"<b>Message:</b>\n{post.content}"
        
        if post.media_file:
            preview += f"\n\n📎 <i>Attachment: {post.media_file.name}</i>"
        
        return preview
    
    @staticmethod
    def estimate_duration(recipient_count: int, rate_limit: BroadcastRateLimit = None) -> str:
        """
        Estimate broadcast duration.
        """
        batch_size = rate_limit.batch_size if rate_limit else 50
        batch_delay = rate_limit.batch_delay if rate_limit else 3
        
        batches = (recipient_count + batch_size - 1) // batch_size
        total_seconds = batches * batch_delay
        
        if total_seconds < 60:
            return f"{total_seconds} seconds"
        elif total_seconds < 3600:
            return f"{total_seconds // 60} minutes"
        else:
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            return f"{hours}h {minutes}m"


def send_broadcast(post_id: int, async_mode: bool = False) -> BroadcastResult:
    """
    Convenience function to send a broadcast.
    Can be called directly or via Celery task.
    """
    post = MarketingPost.objects.get(id=post_id)
    
    if not post.is_sendable:
        raise BroadcastError(f"Post is not sendable (status: {post.status})")
    
    service = BroadcastService(post)
    
    # Prepare recipients if not already done
    if post.total_recipients == 0:
        service.prepare_recipients()
    
    return service.execute(async_mode=async_mode)


def get_recipient_count(post: MarketingPost) -> int:
    """
    Get count of recipients for a post without creating records.
    Useful for preview/confirmation.
    """
    service = BroadcastService(post)
    return len(service.get_recipients())
