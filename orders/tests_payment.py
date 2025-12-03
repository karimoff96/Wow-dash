"""
Tests for Partial Payment Support

Tests cover:
- Partial payment flow
- Full payment acceptance
- Extra fee handling
- Validation (negative amounts, etc.)
- Race condition handling (concurrent updates)
"""
from decimal import Decimal
from django.test import TestCase, TransactionTestCase
from django.contrib.auth.models import User
from django.db import transaction
from concurrent.futures import ThreadPoolExecutor
import threading

from orders.models import Order, OrderMedia
from orders.payment_service import PaymentService, PaymentError, record_payment, add_extra_fee
from accounts.models import BotUser
from organizations.models import TranslationCenter, Branch, Role, AdminUser
from services.models import Category, Product


class PaymentTestBase(TestCase):
    """Base class with common test fixtures"""
    
    @classmethod
    def setUpTestData(cls):
        # Create user
        cls.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )
        cls.superuser = User.objects.create_superuser(
            username='admin',
            password='admin123'
        )
        
        # Create center and branch
        cls.center = TranslationCenter.objects.create(
            name='Test Center',
            owner=cls.superuser
        )
        cls.branch = Branch.objects.create(
            name='Test Branch',
            center=cls.center
        )
        
        # Create role and admin user
        cls.role = Role.objects.create(
            name='staff',
            display_name='Staff',
            can_receive_payments=True
        )
        cls.admin_user = AdminUser.objects.create(
            user=cls.user,
            role=cls.role,
            branch=cls.branch,
            center=cls.center
        )
        
        # Create bot user
        cls.bot_user = BotUser.objects.create(
            user_id=123456789,
            name='Test Bot User',
            phone='+998901234567'
        )
        
        # Create category and product
        cls.category = Category.objects.create(
            name='Translation',
            is_active=True
        )
        cls.product = Product.objects.create(
            name='Standard Translation',
            category=cls.category,
            price_per_page=10000,
            is_active=True
        )
    
    def create_order(self, total_price=100000, **kwargs):
        """Helper to create test orders"""
        return Order.objects.create(
            bot_user=self.bot_user,
            product=self.product,
            branch=self.branch,
            total_pages=10,
            total_price=Decimal(str(total_price)),
            status='pending',
            **kwargs
        )


class OrderPaymentFieldsTest(PaymentTestBase):
    """Test Order model payment fields and properties"""
    
    def test_order_has_payment_fields(self):
        """Test that Order model has all required payment fields"""
        order = self.create_order()
        
        self.assertEqual(order.received, Decimal('0'))
        self.assertEqual(order.extra_fee, Decimal('0'))
        self.assertIsNone(order.extra_fee_description)
        self.assertFalse(order.payment_accepted_fully)
    
    def test_total_due_without_extra_fee(self):
        """Test total_due property without extra fee"""
        order = self.create_order(total_price=100000)
        self.assertEqual(order.total_due, Decimal('100000'))
    
    def test_total_due_with_extra_fee(self):
        """Test total_due property with extra fee"""
        order = self.create_order(total_price=100000)
        order.extra_fee = Decimal('5000')
        order.save()
        
        self.assertEqual(order.total_due, Decimal('105000'))
    
    def test_remaining_not_paid(self):
        """Test remaining when nothing paid"""
        order = self.create_order(total_price=100000)
        self.assertEqual(order.remaining, Decimal('100000'))
    
    def test_remaining_partial_payment(self):
        """Test remaining after partial payment"""
        order = self.create_order(total_price=100000)
        order.received = Decimal('30000')
        order.save()
        
        self.assertEqual(order.remaining, Decimal('70000'))
    
    def test_remaining_fully_paid(self):
        """Test remaining when fully paid"""
        order = self.create_order(total_price=100000)
        order.received = Decimal('100000')
        order.save()
        
        self.assertEqual(order.remaining, Decimal('0'))
    
    def test_remaining_when_accepted_fully(self):
        """Test remaining is 0 when payment_accepted_fully is True"""
        order = self.create_order(total_price=100000)
        order.received = Decimal('50000')  # Less than total
        order.payment_accepted_fully = True
        order.save()
        
        self.assertEqual(order.remaining, Decimal('0'))
    
    def test_is_fully_paid_false(self):
        """Test is_fully_paid when not fully paid"""
        order = self.create_order(total_price=100000)
        order.received = Decimal('50000')
        
        self.assertFalse(order.is_fully_paid)
    
    def test_is_fully_paid_by_amount(self):
        """Test is_fully_paid when paid by amount"""
        order = self.create_order(total_price=100000)
        order.received = Decimal('100000')
        
        self.assertTrue(order.is_fully_paid)
    
    def test_is_fully_paid_by_acceptance(self):
        """Test is_fully_paid when accepted fully"""
        order = self.create_order(total_price=100000)
        order.payment_accepted_fully = True
        
        self.assertTrue(order.is_fully_paid)
    
    def test_payment_percentage(self):
        """Test payment percentage calculation"""
        order = self.create_order(total_price=100000)
        
        # 0%
        self.assertEqual(order.payment_percentage, 0)
        
        # 50%
        order.received = Decimal('50000')
        self.assertEqual(order.payment_percentage, 50)
        
        # 100%
        order.received = Decimal('100000')
        self.assertEqual(order.payment_percentage, 100)
        
        # Accepted fully shows 100%
        order.received = Decimal('0')
        order.payment_accepted_fully = True
        self.assertEqual(order.payment_percentage, 100)


class PartialPaymentFlowTest(PaymentTestBase):
    """Test partial payment flows"""
    
    def test_record_partial_payment(self):
        """Test recording a partial payment"""
        order = self.create_order(total_price=100000)
        
        result = PaymentService.record_payment(
            order_id=order.id,
            received_by=self.admin_user,
            amount=Decimal('30000')
        )
        
        self.assertTrue(result['success'])
        self.assertEqual(result['received'], 30000)
        self.assertEqual(result['remaining'], 70000)
        self.assertFalse(result['is_fully_paid'])
        
        # Verify order was updated
        order.refresh_from_db()
        self.assertEqual(order.received, Decimal('30000'))
        self.assertEqual(order.status, 'payment_received')
    
    def test_multiple_partial_payments(self):
        """Test multiple partial payments accumulate correctly"""
        order = self.create_order(total_price=100000)
        
        # First payment
        PaymentService.record_payment(
            order_id=order.id,
            received_by=self.admin_user,
            amount=Decimal('30000')
        )
        
        # Second payment
        result = PaymentService.record_payment(
            order_id=order.id,
            received_by=self.admin_user,
            amount=Decimal('40000')
        )
        
        self.assertEqual(result['received'], 70000)
        self.assertEqual(result['remaining'], 30000)
    
    def test_partial_payment_becomes_full(self):
        """Test partial payments that complete the full amount"""
        order = self.create_order(total_price=100000)
        
        # Pay partial
        PaymentService.record_payment(
            order_id=order.id,
            received_by=self.admin_user,
            amount=Decimal('60000')
        )
        
        # Pay remainder
        result = PaymentService.record_payment(
            order_id=order.id,
            received_by=self.admin_user,
            amount=Decimal('40000')
        )
        
        self.assertTrue(result['is_fully_paid'])
        self.assertEqual(result['remaining'], 0)
        self.assertEqual(result['status'], 'payment_confirmed')


class FullPaymentAcceptanceTest(PaymentTestBase):
    """Test full payment acceptance flow"""
    
    def test_accept_fully_with_full_amount(self):
        """Test accepting fully when full amount received"""
        order = self.create_order(total_price=100000)
        order.received = Decimal('100000')
        order.save()
        
        result = PaymentService.record_payment(
            order_id=order.id,
            received_by=self.admin_user,
            accept_fully=True
        )
        
        self.assertTrue(result['success'])
        self.assertTrue(result['payment_accepted_fully'])
        self.assertEqual(result['status'], 'payment_confirmed')
    
    def test_accept_fully_fails_without_full_amount(self):
        """Test accepting fully fails when amount not received (without force)"""
        order = self.create_order(total_price=100000)
        order.received = Decimal('50000')
        order.save()
        
        with self.assertRaises(PaymentError) as context:
            PaymentService.record_payment(
                order_id=order.id,
                received_by=self.admin_user,
                accept_fully=True
            )
        
        self.assertIn('Cannot mark as fully paid', str(context.exception))
    
    def test_force_accept_allows_underpayment(self):
        """Test force_accept allows owner to accept underpayment"""
        order = self.create_order(total_price=100000)
        order.received = Decimal('50000')
        order.save()
        
        result = PaymentService.record_payment(
            order_id=order.id,
            received_by=self.admin_user,
            accept_fully=True,
            force_accept=True
        )
        
        self.assertTrue(result['success'])
        self.assertTrue(result['payment_accepted_fully'])
        
        # Verify received is set to total_due
        order.refresh_from_db()
        self.assertEqual(order.received, order.total_due)


class ExtraFeeTest(PaymentTestBase):
    """Test extra fee functionality"""
    
    def test_add_extra_fee(self):
        """Test adding extra fee to order"""
        order = self.create_order(total_price=100000)
        
        result = PaymentService.add_extra_fee(
            order_id=order.id,
            amount=Decimal('5000'),
            description='Rush delivery',
            added_by=self.admin_user
        )
        
        self.assertTrue(result['success'])
        self.assertEqual(result['extra_fee'], 5000)
        self.assertEqual(result['total_due'], 105000)
        
        order.refresh_from_db()
        self.assertEqual(order.extra_fee, Decimal('5000'))
        self.assertEqual(order.extra_fee_description, 'Rush delivery')
    
    def test_extra_fee_accumulates(self):
        """Test multiple extra fees accumulate"""
        order = self.create_order(total_price=100000)
        
        PaymentService.add_extra_fee(
            order_id=order.id,
            amount=Decimal('3000'),
            description='Rush',
            added_by=self.admin_user
        )
        
        result = PaymentService.add_extra_fee(
            order_id=order.id,
            amount=Decimal('2000'),
            description='Special handling',
            added_by=self.admin_user
        )
        
        self.assertEqual(result['extra_fee'], 5000)
    
    def test_extra_fee_affects_remaining(self):
        """Test extra fee affects remaining balance"""
        order = self.create_order(total_price=100000)
        order.received = Decimal('100000')
        order.save()
        
        # Initially fully paid
        self.assertEqual(order.remaining, Decimal('0'))
        
        # Add extra fee
        PaymentService.add_extra_fee(
            order_id=order.id,
            amount=Decimal('5000'),
            description='Rush',
            added_by=self.admin_user
        )
        
        order.refresh_from_db()
        self.assertEqual(order.remaining, Decimal('5000'))


class ValidationTest(PaymentTestBase):
    """Test validation rules"""
    
    def test_negative_amount_rejected(self):
        """Test negative payment amounts are rejected"""
        order = self.create_order()
        
        with self.assertRaises(PaymentError):
            PaymentService.record_payment(
                order_id=order.id,
                received_by=self.admin_user,
                amount=Decimal('-5000')
            )
    
    def test_negative_extra_fee_rejected(self):
        """Test negative extra fee amounts are rejected"""
        order = self.create_order()
        
        with self.assertRaises(PaymentError):
            PaymentService.add_extra_fee(
                order_id=order.id,
                amount=Decimal('-1000'),
                description='Test',
                added_by=self.admin_user
            )
    
    def test_zero_extra_fee_rejected(self):
        """Test zero extra fee is rejected"""
        order = self.create_order()
        
        with self.assertRaises(PaymentError):
            PaymentService.add_extra_fee(
                order_id=order.id,
                amount=Decimal('0'),
                description='Test',
                added_by=self.admin_user
            )
    
    def test_invalid_amount_format(self):
        """Test invalid amount format is rejected"""
        order = self.create_order()
        
        with self.assertRaises(PaymentError):
            PaymentService.validate_amount('not-a-number')


class ConcurrencyTest(TransactionTestCase):
    """Test concurrent payment updates are handled safely"""
    
    def setUp(self):
        # Create test data
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass'
        )
        self.superuser = User.objects.create_superuser(
            username='admin',
            password='admin123'
        )
        self.center = TranslationCenter.objects.create(
            name='Test Center',
            owner=self.superuser
        )
        self.branch = Branch.objects.create(
            name='Test Branch',
            center=self.center
        )
        self.role = Role.objects.create(
            name='staff',
            display_name='Staff'
        )
        self.admin_user = AdminUser.objects.create(
            user=self.user,
            role=self.role,
            branch=self.branch,
            center=self.center
        )
        self.bot_user = BotUser.objects.create(
            user_id=123456789,
            name='Test User',
            phone='+998901234567'
        )
        self.category = Category.objects.create(
            name='Translation',
            is_active=True
        )
        self.product = Product.objects.create(
            name='Standard',
            category=self.category,
            price_per_page=10000,
            is_active=True
        )
    
    def test_concurrent_partial_payments(self):
        """Test concurrent partial payments don't cause data loss"""
        order = Order.objects.create(
            bot_user=self.bot_user,
            product=self.product,
            branch=self.branch,
            total_pages=10,
            total_price=Decimal('100000'),
            status='pending'
        )
        
        results = []
        errors = []
        
        def make_payment():
            try:
                result = PaymentService.record_payment(
                    order_id=order.id,
                    received_by=self.admin_user,
                    amount=Decimal('10000')
                )
                results.append(result)
            except Exception as e:
                errors.append(e)
        
        # Make 5 concurrent payments of 10000 each
        threads = [threading.Thread(target=make_payment) for _ in range(5)]
        
        for t in threads:
            t.start()
        
        for t in threads:
            t.join()
        
        # Verify no errors
        self.assertEqual(len(errors), 0, f"Errors occurred: {errors}")
        
        # Verify final amount (should be 50000 - 5 x 10000)
        order.refresh_from_db()
        self.assertEqual(order.received, Decimal('50000'))
    
    def test_concurrent_accept_fully(self):
        """Test concurrent full acceptance doesn't cause issues"""
        order = Order.objects.create(
            bot_user=self.bot_user,
            product=self.product,
            branch=self.branch,
            total_pages=10,
            total_price=Decimal('100000'),
            received=Decimal('100000'),
            status='pending'
        )
        
        results = []
        errors = []
        
        def accept_payment():
            try:
                result = PaymentService.record_payment(
                    order_id=order.id,
                    received_by=self.admin_user,
                    accept_fully=True
                )
                results.append(result)
            except Exception as e:
                errors.append(e)
        
        # Try to accept fully from 3 threads
        threads = [threading.Thread(target=accept_payment) for _ in range(3)]
        
        for t in threads:
            t.start()
        
        for t in threads:
            t.join()
        
        # Verify final state is consistent
        order.refresh_from_db()
        self.assertTrue(order.payment_accepted_fully)
        self.assertEqual(order.status, 'payment_confirmed')


class PaymentResetTest(PaymentTestBase):
    """Test payment reset functionality"""
    
    def test_reset_payment(self):
        """Test resetting payment status"""
        order = self.create_order(total_price=100000)
        order.received = Decimal('50000')
        order.payment_accepted_fully = True
        order.status = 'payment_confirmed'
        order.save()
        
        result = PaymentService.reset_payment(
            order_id=order.id,
            reset_by=self.admin_user
        )
        
        self.assertTrue(result['success'])
        
        order.refresh_from_db()
        self.assertEqual(order.received, Decimal('0'))
        self.assertFalse(order.payment_accepted_fully)
        self.assertEqual(order.status, 'pending')
