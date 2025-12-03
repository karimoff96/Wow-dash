"""
Tests for Marketing & Broadcast System

Covers:
- Model creation and validation
- Permission enforcement
- Broadcast service functionality
- Rate limiting
- Multi-tenant boundaries
"""
from decimal import Decimal
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase, Client, override_settings
from django.contrib.auth.models import User
from django.utils import timezone
from django.urls import reverse

from accounts.models import BotUser
from organizations.models import TranslationCenter, Branch, AdminUser, Role
from marketing.models import (
    MarketingPost, BroadcastRecipient, 
    UserBroadcastPreference, BroadcastRateLimit
)
from marketing.broadcast_service import (
    BroadcastService, BroadcastResult, BroadcastError,
    send_broadcast, get_recipient_count
)


class MarketingPostModelTest(TestCase):
    """Test MarketingPost model"""
    
    def setUp(self):
        self.user = User.objects.create_user('testuser', 'test@example.com', 'password')
        self.center = TranslationCenter.objects.create(
            name='Test Center',
            owner=self.user,
            bot_token='test_token_123'
        )
        self.branch = Branch.objects.filter(center=self.center).first()
    
    def test_create_draft_post(self):
        """Test creating a draft marketing post"""
        post = MarketingPost.objects.create(
            title='Test Post',
            content='Hello <b>World</b>!',
            target_scope=MarketingPost.SCOPE_BRANCH,
            target_center=self.center,
            target_branch=self.branch,
            created_by=self.user
        )
        
        self.assertEqual(post.status, MarketingPost.STATUS_DRAFT)
        self.assertTrue(post.is_sendable)
        self.assertEqual(post.delivery_percentage, 0)
    
    def test_scope_display(self):
        """Test scope display method"""
        post = MarketingPost.objects.create(
            title='Branch Post',
            content='Content',
            target_scope=MarketingPost.SCOPE_BRANCH,
            target_center=self.center,
            target_branch=self.branch,
            created_by=self.user
        )
        
        display = post.get_scope_display_full()
        self.assertIn(self.branch.name, str(display))
    
    def test_is_scheduled(self):
        """Test scheduled post detection"""
        future_time = timezone.now() + timezone.timedelta(hours=1)
        past_time = timezone.now() - timezone.timedelta(hours=1)
        
        future_post = MarketingPost.objects.create(
            title='Future Post',
            content='Content',
            target_scope=MarketingPost.SCOPE_BRANCH,
            target_branch=self.branch,
            scheduled_at=future_time,
            created_by=self.user
        )
        
        past_post = MarketingPost.objects.create(
            title='Past Post',
            content='Content',
            target_scope=MarketingPost.SCOPE_BRANCH,
            target_branch=self.branch,
            scheduled_at=past_time,
            created_by=self.user
        )
        
        self.assertTrue(future_post.is_scheduled)
        self.assertFalse(past_post.is_scheduled)


class BroadcastRecipientTest(TestCase):
    """Test BroadcastRecipient model"""
    
    def setUp(self):
        self.user = User.objects.create_user('testuser', 'test@example.com', 'password')
        self.center = TranslationCenter.objects.create(
            name='Test Center',
            owner=self.user,
            bot_token='test_token_123'
        )
        self.branch = Branch.objects.filter(center=self.center).first()
        
        self.bot_user = BotUser.objects.create(
            user_id=123456789,
            name='Test Customer',
            phone='+998901234567',
            branch=self.branch,
            is_active=True
        )
        
        self.post = MarketingPost.objects.create(
            title='Test Post',
            content='Hello!',
            target_scope=MarketingPost.SCOPE_BRANCH,
            target_branch=self.branch,
            created_by=self.user
        )
    
    def test_create_recipient(self):
        """Test creating broadcast recipient"""
        recipient = BroadcastRecipient.objects.create(
            post=self.post,
            bot_user=self.bot_user
        )
        
        self.assertEqual(recipient.status, BroadcastRecipient.STATUS_PENDING)
        self.assertEqual(recipient.retry_count, 0)
    
    def test_unique_constraint(self):
        """Test unique constraint on post + bot_user"""
        BroadcastRecipient.objects.create(
            post=self.post,
            bot_user=self.bot_user
        )
        
        # Trying to create duplicate should fail
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            BroadcastRecipient.objects.create(
                post=self.post,
                bot_user=self.bot_user
            )


class UserBroadcastPreferenceTest(TestCase):
    """Test user opt-out functionality"""
    
    def setUp(self):
        self.user = User.objects.create_user('testuser', 'test@example.com', 'password')
        self.center = TranslationCenter.objects.create(
            name='Test Center',
            owner=self.user
        )
        self.branch = Branch.objects.filter(center=self.center).first()
        
        self.bot_user = BotUser.objects.create(
            user_id=123456789,
            name='Test Customer',
            phone='+998901234567',
            branch=self.branch,
            is_active=True
        )
    
    def test_default_preferences(self):
        """Test default preferences (opted in)"""
        pref = UserBroadcastPreference.objects.create(
            bot_user=self.bot_user
        )
        
        self.assertTrue(pref.receive_marketing)
        self.assertTrue(pref.receive_promotions)
        self.assertTrue(pref.receive_updates)
    
    def test_opt_out(self):
        """Test opting out of marketing"""
        pref = UserBroadcastPreference.objects.create(
            bot_user=self.bot_user,
            receive_marketing=False
        )
        
        self.assertFalse(pref.receive_marketing)


class BroadcastServiceTest(TestCase):
    """Test BroadcastService functionality"""
    
    def setUp(self):
        self.user = User.objects.create_user('testuser', 'test@example.com', 'password')
        self.center = TranslationCenter.objects.create(
            name='Test Center',
            owner=self.user,
            bot_token='test_bot_token_12345'
        )
        self.branch = Branch.objects.filter(center=self.center).first()
        
        # Create test customers
        for i in range(5):
            BotUser.objects.create(
                user_id=100000000 + i,
                name=f'Customer {i}',
                phone=f'+99890123456{i}',
                branch=self.branch,
                is_active=True,
                is_agency=(i % 2 == 0)  # Alternate B2C/B2B
            )
        
        self.post = MarketingPost.objects.create(
            title='Test Broadcast',
            content='Hello everyone!',
            target_scope=MarketingPost.SCOPE_BRANCH,
            target_center=self.center,
            target_branch=self.branch,
            include_b2c=True,
            include_b2b=True,
            created_by=self.user
        )
    
    def test_get_recipients_all(self):
        """Test getting all recipients for branch"""
        service = BroadcastService(self.post)
        recipients = service.get_recipients()
        
        self.assertEqual(len(recipients), 5)
    
    def test_get_recipients_b2c_only(self):
        """Test filtering to B2C only"""
        self.post.include_b2b = False
        self.post.save()
        
        service = BroadcastService(self.post)
        recipients = service.get_recipients()
        
        # Should only get non-agency users
        for r in recipients:
            self.assertFalse(r.is_agency)
    
    def test_get_recipients_b2b_only(self):
        """Test filtering to B2B only"""
        self.post.include_b2c = False
        self.post.save()
        
        service = BroadcastService(self.post)
        recipients = service.get_recipients()
        
        # Should only get agency users
        for r in recipients:
            self.assertTrue(r.is_agency)
    
    def test_get_recipients_respects_opt_out(self):
        """Test that opted-out users are excluded"""
        opted_out_user = BotUser.objects.filter(branch=self.branch).first()
        UserBroadcastPreference.objects.create(
            bot_user=opted_out_user,
            receive_marketing=False
        )
        
        service = BroadcastService(self.post)
        recipients = service.get_recipients()
        
        self.assertEqual(len(recipients), 4)
        self.assertNotIn(opted_out_user, recipients)
    
    def test_prepare_recipients(self):
        """Test preparing recipient records"""
        service = BroadcastService(self.post)
        count = service.prepare_recipients()
        
        self.assertEqual(count, 5)
        self.assertEqual(self.post.total_recipients, 5)
        
        # Check recipient records created
        recipients = BroadcastRecipient.objects.filter(post=self.post)
        self.assertEqual(recipients.count(), 5)
    
    @patch('marketing.broadcast_service.telebot.TeleBot')
    def test_send_message_success(self, mock_telebot):
        """Test successful message sending"""
        mock_bot = MagicMock()
        mock_msg = MagicMock()
        mock_msg.message_id = 12345
        mock_bot.send_message.return_value = mock_msg
        mock_telebot.return_value = mock_bot
        
        service = BroadcastService(self.post)
        service.bot = mock_bot
        
        bot_user = BotUser.objects.filter(branch=self.branch).first()
        success, msg_id, error = service.send_message(bot_user)
        
        self.assertTrue(success)
        self.assertEqual(msg_id, 12345)
        self.assertIsNone(error)
    
    @patch('marketing.broadcast_service.telebot.TeleBot')
    def test_send_message_blocked_user(self, mock_telebot):
        """Test handling blocked user"""
        from telebot.apihelper import ApiTelegramException
        
        mock_bot = MagicMock()
        mock_bot.send_message.side_effect = ApiTelegramException(
            'Forbidden: bot was blocked by the user',
            'sendMessage',
            {'error_code': 403, 'description': 'Forbidden: bot was blocked by the user'}
        )
        mock_telebot.return_value = mock_bot
        
        service = BroadcastService(self.post)
        service.bot = mock_bot
        
        bot_user = BotUser.objects.filter(branch=self.branch).first()
        success, msg_id, error = service.send_message(bot_user)
        
        self.assertFalse(success)
        self.assertIn('blocked', error.lower())
    
    def test_estimate_duration(self):
        """Test duration estimation"""
        # 100 recipients, batch size 50, batch delay 3s = 2 batches * 3s = 6s
        duration = BroadcastService.estimate_duration(100)
        self.assertIn('seconds', duration)
        
        # 1000 recipients = 20 batches * 3s = 60s = 1 minute
        duration = BroadcastService.estimate_duration(1000)
        self.assertIn('minute', duration)


class BroadcastRateLimitTest(TestCase):
    """Test rate limiting configuration"""
    
    def setUp(self):
        self.user = User.objects.create_user('testuser', 'test@example.com', 'password')
        self.center = TranslationCenter.objects.create(
            name='Test Center',
            owner=self.user
        )
    
    def test_get_or_create(self):
        """Test getting or creating rate limit config"""
        rate_limit = BroadcastRateLimit.get_or_create_for_center(self.center)
        
        self.assertEqual(rate_limit.center, self.center)
        self.assertEqual(rate_limit.batch_size, 50)
        self.assertEqual(rate_limit.batch_delay, 3)
    
    def test_custom_rate_limit(self):
        """Test custom rate limit settings"""
        rate_limit = BroadcastRateLimit.objects.create(
            center=self.center,
            messages_per_second=20,
            batch_size=30,
            batch_delay=5
        )
        
        fetched = BroadcastRateLimit.get_or_create_for_center(self.center)
        self.assertEqual(fetched.batch_size, 30)
        self.assertEqual(fetched.batch_delay, 5)


class MarketingPermissionTest(TestCase):
    """Test permission enforcement for marketing"""
    
    def setUp(self):
        # Create superuser
        self.superuser = User.objects.create_superuser(
            'superadmin', 'super@example.com', 'password'
        )
        
        # Create owner
        self.owner_user = User.objects.create_user(
            'owner', 'owner@example.com', 'password'
        )
        self.center = TranslationCenter.objects.create(
            name='Test Center',
            owner=self.owner_user,
            bot_token='test_token_123'
        )
        self.branch = Branch.objects.filter(center=self.center).first()
        
        # Create owner admin profile
        self.owner_admin = AdminUser.objects.create(
            user=self.owner_user,
            center=self.center,
            is_owner=True
        )
        
        # Create manager
        self.manager_user = User.objects.create_user(
            'manager', 'manager@example.com', 'password'
        )
        self.role = Role.objects.create(
            name='Manager',
            center=self.center
        )
        self.manager_admin = AdminUser.objects.create(
            user=self.manager_user,
            center=self.center,
            role=self.role
        )
        self.manager_admin.branches.add(self.branch)
        
        self.client = Client()
    
    def test_superuser_can_access_all(self):
        """Test superuser can access marketing"""
        self.client.login(username='superadmin', password='password')
        response = self.client.get(reverse('marketing_list'))
        self.assertEqual(response.status_code, 200)
    
    def test_owner_can_access(self):
        """Test owner can access marketing"""
        self.client.login(username='owner', password='password')
        response = self.client.get(reverse('marketing_list'))
        self.assertEqual(response.status_code, 200)
    
    def test_manager_can_access(self):
        """Test manager can access marketing"""
        self.client.login(username='manager', password='password')
        response = self.client.get(reverse('marketing_list'))
        self.assertEqual(response.status_code, 200)


class MultiTenantBroadcastTest(TestCase):
    """Test multi-tenant boundaries in broadcasting"""
    
    def setUp(self):
        # Create two separate centers with their own customers
        self.user1 = User.objects.create_user('user1', 'user1@example.com', 'password')
        self.user2 = User.objects.create_user('user2', 'user2@example.com', 'password')
        
        self.center1 = TranslationCenter.objects.create(
            name='Center 1',
            owner=self.user1,
            bot_token='token_center_1'
        )
        self.center2 = TranslationCenter.objects.create(
            name='Center 2',
            owner=self.user2,
            bot_token='token_center_2'
        )
        
        self.branch1 = Branch.objects.filter(center=self.center1).first()
        self.branch2 = Branch.objects.filter(center=self.center2).first()
        
        # Create customers for each center
        for i in range(3):
            BotUser.objects.create(
                user_id=100000 + i,
                name=f'Center1 Customer {i}',
                phone=f'+998901111{i}',
                branch=self.branch1,
                is_active=True
            )
            BotUser.objects.create(
                user_id=200000 + i,
                name=f'Center2 Customer {i}',
                phone=f'+998902222{i}',
                branch=self.branch2,
                is_active=True
            )
    
    def test_center_scope_only_gets_center_customers(self):
        """Test that center scope only includes center's customers"""
        post = MarketingPost.objects.create(
            title='Center 1 Broadcast',
            content='Hello Center 1!',
            target_scope=MarketingPost.SCOPE_CENTER,
            target_center=self.center1,
            created_by=self.user1
        )
        
        service = BroadcastService(post)
        recipients = service.get_recipients()
        
        self.assertEqual(len(recipients), 3)
        for r in recipients:
            self.assertEqual(r.branch.center, self.center1)
    
    def test_branch_scope_only_gets_branch_customers(self):
        """Test that branch scope only includes branch's customers"""
        post = MarketingPost.objects.create(
            title='Branch 2 Broadcast',
            content='Hello Branch 2!',
            target_scope=MarketingPost.SCOPE_BRANCH,
            target_center=self.center2,
            target_branch=self.branch2,
            created_by=self.user2
        )
        
        service = BroadcastService(post)
        recipients = service.get_recipients()
        
        self.assertEqual(len(recipients), 3)
        for r in recipients:
            self.assertEqual(r.branch, self.branch2)
    
    def test_correct_bot_token_used(self):
        """Test that correct center's bot token is used"""
        post = MarketingPost.objects.create(
            title='Center 1 Broadcast',
            content='Hello!',
            target_scope=MarketingPost.SCOPE_CENTER,
            target_center=self.center1,
            created_by=self.user1
        )
        
        service = BroadcastService(post)
        token = service._get_bot_token()
        
        self.assertEqual(token, 'token_center_1')


class RecipientCountAPITest(TestCase):
    """Test recipient count API endpoint"""
    
    def setUp(self):
        self.user = User.objects.create_user('testuser', 'test@example.com', 'password')
        self.center = TranslationCenter.objects.create(
            name='Test Center',
            owner=self.user,
            bot_token='test_token'
        )
        self.branch = Branch.objects.filter(center=self.center).first()
        
        # Create test customers
        for i in range(10):
            BotUser.objects.create(
                user_id=100000 + i,
                name=f'Customer {i}',
                phone=f'+99890123456{i}',
                branch=self.branch,
                is_active=True
            )
        
        self.admin = AdminUser.objects.create(
            user=self.user,
            center=self.center,
            is_owner=True
        )
        
        self.client = Client()
        self.client.login(username='testuser', password='password')
    
    def test_get_recipient_count(self):
        """Test getting recipient count via API"""
        response = self.client.get(
            reverse('api_recipient_count'),
            {
                'scope': 'branch',
                'branch_id': self.branch.id,
                'include_b2c': 'true',
                'include_b2b': 'true'
            }
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['count'], 10)
