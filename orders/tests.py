"""
Tests for Order Payment System

Tests partial payments, full payment acceptance, extra fees,
and race condition handling via database transactions.
"""
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor
import threading
from unittest import skipUnless

from django.test import TestCase, TransactionTestCase
from django.contrib.auth.models import User
from django.db import connection

from orders.models import Order
from orders.payment_service import PaymentService, PaymentError
from organizations.models import TranslationCenter, Branch, Role, AdminUser
from services.models import Category, Product, Language
from accounts.models import BotUser


class PaymentTestMixin:
    """Mixin with common test setup for payment tests"""
    
    @classmethod
    def setUpTestData(cls):
        """Set up test data once for all tests"""
        cls._create_test_data()
    
    @classmethod
    def _create_test_data(cls):
        """Create test data - called by setUpTestData or setUp"""
        # Create user
        cls.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )
        
        cls.owner_user = User.objects.create_user(
            username='owner',
            password='ownerpass123',
            first_name='Owner',
            last_name='User'
        )
        
        # Create center and branch
        cls.center = TranslationCenter.objects.create(
            name='Test Center',
            owner=cls.owner_user,
            is_active=True
        )
        
        cls.branch = Branch.objects.create(
            name='Test Branch',
            center=cls.center,
            is_active=True
        )
        
        # Create roles
        cls.staff_role = Role.objects.create(
            name='staff',
            display_name='Staff',
            can_receive_payments=True
        )
        
        cls.owner_role = Role.objects.create(
            name='owner',
            display_name='Owner',
            can_receive_payments=True,
            can_manage_orders=True
        )
        
        # Create admin users
        cls.admin_user = AdminUser.objects.create(
            user=cls.user,
            role=cls.staff_role,
            center=cls.center,
            branch=cls.branch
        )
        
        cls.owner_admin = AdminUser.objects.create(
            user=cls.owner_user,
            role=cls.owner_role,
            center=cls.center
        )
        
        # Create service category and product
        # Using static pricing with 100000 as base price for predictable test values
        cls.category = Category.objects.create(
            name='Translation',
            branch=cls.branch,
            charging='static',  # Static means first_page_price is the total price
            is_active=True
        )
        
        cls.product = Product.objects.create(
            name='Document Translation',
            category=cls.category,
            ordinary_first_page_price=100000,  # 100000 UZS for regular users
            ordinary_other_page_price=8000,    # Not used in static pricing
            agency_first_page_price=80000,     # 80000 UZS for agencies
            agency_other_page_price=6000,      # Not used in static pricing
            is_active=True
        )
        
        # Create language
        cls.language = Language.objects.create(
            name='English',
            short_name='en'
        )
        
        # Create bot user
        cls.bot_user = BotUser.objects.create(
            user_id=123456789,
            name='Test Customer',
            phone='+998901234567',
            branch=cls.branch
        )
    
    def create_order(self, extra_fee=0, received=0):
        """
        Helper to create an order for testing.
        
        With static pricing and ordinary_first_page_price=100000,
        the calculated total_price will be 100000.
        """
        order = Order.objects.create(
            branch=self.branch,
            bot_user=self.bot_user,
            product=self.product,
            total_pages=1,  # Doesn't affect static pricing
            extra_fee=Decimal(str(extra_fee)),
            received=Decimal(str(received)),
            status='pending'
        )
        # Verify the calculated price
        assert order.total_price == Decimal('100000'), f"Expected 100000, got {order.total_price}"
        return order


class OrderModelTests(PaymentTestMixin, TestCase):
    """Tests for Order model payment properties"""
    
    def test_total_due_without_extra_fee(self):
        """total_due should equal total_price when no extra fee"""
        order = self.create_order()
        self.assertEqual(order.total_due, Decimal('100000'))
    
    def test_total_due_with_extra_fee(self):
        """total_due should include extra_fee"""
        order = self.create_order(extra_fee=5000)
        self.assertEqual(order.total_due, Decimal('105000'))
    
    def test_remaining_calculation(self):
        """remaining should be total_due - received"""
        order = self.create_order(extra_fee=5000, received=50000)
        self.assertEqual(order.remaining, Decimal('55000'))
    
    def test_remaining_when_fully_paid(self):
        """remaining should be 0 when payment_accepted_fully is True"""
        order = self.create_order(received=50000)
        order.payment_accepted_fully = True
        order.save()
        self.assertEqual(order.remaining, Decimal('0'))
    
    def test_remaining_never_negative(self):
        """remaining should never be negative"""
        order = self.create_order(received=150000)
        self.assertEqual(order.remaining, Decimal('0'))
    
    def test_is_fully_paid_when_accepted(self):
        """is_fully_paid should be True when payment_accepted_fully"""
        order = self.create_order(received=0)
        order.payment_accepted_fully = True
        self.assertTrue(order.is_fully_paid)
    
    def test_is_fully_paid_when_received_equals_total(self):
        """is_fully_paid should be True when received >= total_due"""
        order = self.create_order(received=100000)
        self.assertTrue(order.is_fully_paid)
    
    def test_payment_percentage_calculation(self):
        """payment_percentage should be correctly calculated"""
        order = self.create_order(received=25000)
        self.assertEqual(order.payment_percentage, 25)
    
    def test_payment_percentage_capped_at_100(self):
        """payment_percentage should never exceed 100"""
        order = self.create_order(received=150000)
        self.assertEqual(order.payment_percentage, 100)
    
    def test_payment_percentage_when_fully_accepted(self):
        """payment_percentage should be 100 when payment_accepted_fully"""
        order = self.create_order(received=0)
        order.payment_accepted_fully = True
        self.assertEqual(order.payment_percentage, 100)


class PaymentServiceTests(PaymentTestMixin, TestCase):
    """Tests for PaymentService"""
    
    def test_validate_amount_positive(self):
        """validate_amount should accept positive amounts"""
        result = PaymentService.validate_amount(100.50)
        self.assertEqual(result, Decimal('100.50'))
    
    def test_validate_amount_zero(self):
        """validate_amount should accept zero"""
        result = PaymentService.validate_amount(0)
        self.assertEqual(result, Decimal('0.00'))
    
    def test_validate_amount_negative_raises_error(self):
        """validate_amount should raise PaymentError for negative amounts"""
        with self.assertRaises(PaymentError) as context:
            PaymentService.validate_amount(-100)
        self.assertIn('negative', str(context.exception).lower())
    
    def test_validate_amount_invalid_raises_error(self):
        """validate_amount should raise PaymentError for invalid input"""
        with self.assertRaises(PaymentError):
            PaymentService.validate_amount('not-a-number')
    
    def test_record_partial_payment(self):
        """record_payment should correctly add partial payment"""
        order = self.create_order()
        
        result = PaymentService.record_payment(
            order_id=order.id,
            received_by=self.admin_user,
            amount=Decimal('30000')
        )
        
        self.assertTrue(result['success'])
        self.assertEqual(result['received'], 30000)
        self.assertEqual(result['remaining'], 70000)
        self.assertEqual(result['payment_percentage'], 30)
        self.assertFalse(result['is_fully_paid'])
    
    def test_record_multiple_partial_payments(self):
        """Multiple partial payments should accumulate"""
        order = self.create_order()
        
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
            amount=Decimal('20000')
        )
        
        self.assertEqual(result['received'], 50000)
        self.assertEqual(result['remaining'], 50000)
    
    def test_record_payment_accept_fully(self):
        """accept_fully should mark payment as complete"""
        order = self.create_order(received=100000)
        
        result = PaymentService.record_payment(
            order_id=order.id,
            received_by=self.admin_user,
            accept_fully=True
        )
        
        self.assertTrue(result['success'])
        self.assertTrue(result['payment_accepted_fully'])
        self.assertTrue(result['is_fully_paid'])
        self.assertEqual(result['remaining'], 0)
        self.assertEqual(result['status'], 'payment_confirmed')
    
    def test_accept_fully_fails_when_underpaid(self):
        """accept_fully should fail when received < total without force"""
        order = self.create_order(received=50000)
        
        with self.assertRaises(PaymentError) as context:
            PaymentService.record_payment(
                order_id=order.id,
                received_by=self.admin_user,
                accept_fully=True
            )
        self.assertIn('force_accept', str(context.exception))
    
    def test_accept_fully_with_force(self):
        """force_accept should allow accepting underpaid orders"""
        order = self.create_order(received=50000)
        
        result = PaymentService.record_payment(
            order_id=order.id,
            received_by=self.admin_user,
            accept_fully=True,
            force_accept=True
        )
        
        self.assertTrue(result['success'])
        self.assertTrue(result['payment_accepted_fully'])
    
    def test_add_extra_fee(self):
        """add_extra_fee should add fee to order"""
        order = self.create_order()
        
        result = PaymentService.add_extra_fee(
            order_id=order.id,
            amount=Decimal('5000'),
            description='Rush delivery',
            added_by=self.admin_user
        )
        
        self.assertTrue(result['success'])
        self.assertEqual(result['extra_fee'], 5000)
        self.assertEqual(result['total_due'], 105000)
    
    def test_add_extra_fee_accumulates(self):
        """Multiple extra fees should accumulate"""
        order = self.create_order(extra_fee=5000)
        
        result = PaymentService.add_extra_fee(
            order_id=order.id,
            amount=Decimal('3000'),
            description='Special handling',
            added_by=self.admin_user
        )
        
        self.assertEqual(result['extra_fee'], 8000)
    
    def test_add_extra_fee_zero_raises_error(self):
        """add_extra_fee should reject zero amount"""
        order = self.create_order()
        
        with self.assertRaises(PaymentError):
            PaymentService.add_extra_fee(
                order_id=order.id,
                amount=Decimal('0'),
                description='Nothing',
                added_by=self.admin_user
            )
    
    def test_reset_payment(self):
        """reset_payment should clear payment data"""
        order = self.create_order(received=50000)
        order.payment_accepted_fully = True
        order.save()
        
        result = PaymentService.reset_payment(
            order_id=order.id,
            reset_by=self.owner_admin
        )
        
        self.assertTrue(result['success'])
        self.assertEqual(result['received'], 0)
        self.assertFalse(result['payment_accepted_fully'])
        self.assertEqual(result['status'], 'pending')
    
    def test_auto_complete_when_fully_paid(self):
        """Status should change to payment_confirmed when fully paid"""
        order = self.create_order(received=80000)
        
        result = PaymentService.record_payment(
            order_id=order.id,
            received_by=self.admin_user,
            amount=Decimal('20000')  # This completes payment
        )
        
        self.assertEqual(result['status'], 'payment_confirmed')
        self.assertTrue(result['is_fully_paid'])
    
    def test_record_payment_with_extra_fee(self):
        """record_payment should handle extra_fee parameter"""
        order = self.create_order()
        
        result = PaymentService.record_payment(
            order_id=order.id,
            received_by=self.admin_user,
            amount=Decimal('30000'),
            extra_fee=Decimal('5000'),
            extra_fee_description='Rush delivery'
        )
        
        self.assertEqual(result['extra_fee'], 5000)
        self.assertEqual(result['total_due'], 105000)
        self.assertEqual(result['remaining'], 75000)  # 105000 - 30000


@skipUnless(connection.vendor == "postgresql", "row-lock tests require PostgreSQL")
class PaymentConcurrencyTests(PaymentTestMixin, TransactionTestCase):
    """
    Tests for race conditions and concurrent payment updates.
    Uses TransactionTestCase for proper transaction isolation testing.
    """
    
    def setUp(self):
        """TransactionTestCase doesn't support setUpTestData, so use setUp"""
        self._create_test_data()
    
    def test_concurrent_payments_handled_safely(self):
        """
        Concurrent payments should be handled atomically.
        Tests that select_for_update() prevents race conditions.
        """
        order = self.create_order()
        order_id = order.id
        
        results = []
        errors = []
        barrier = threading.Barrier(2)
        
        def make_payment(amount):
            try:
                barrier.wait()  # Synchronize threads
                result = PaymentService.record_payment(
                    order_id=order_id,
                    received_by=self.admin_user,
                    amount=Decimal(str(amount))
                )
                results.append(result)
            except Exception as e:
                errors.append(str(e))
        
        # Run two concurrent payments
        with ThreadPoolExecutor(max_workers=2) as executor:
            future1 = executor.submit(make_payment, 30000)
            future2 = executor.submit(make_payment, 20000)
            future1.result()
            future2.result()
        
        # Verify both payments were recorded (one after the other due to locking)
        order.refresh_from_db()
        self.assertEqual(order.received, Decimal('50000'))
        self.assertEqual(len(results), 2)
        self.assertEqual(len(errors), 0)
    
    def test_concurrent_accept_fully_handled(self):
        """
        Concurrent accept_fully attempts should be handled safely.
        Only one should succeed in fully accepting.
        """
        order = self.create_order(received=100000)
        order_id = order.id
        
        results = []
        errors = []
        barrier = threading.Barrier(2)
        
        def accept_payment():
            try:
                barrier.wait()
                result = PaymentService.record_payment(
                    order_id=order_id,
                    received_by=self.admin_user,
                    accept_fully=True
                )
                results.append(result)
            except Exception as e:
                errors.append(str(e))
        
        with ThreadPoolExecutor(max_workers=2) as executor:
            future1 = executor.submit(accept_payment)
            future2 = executor.submit(accept_payment)
            future1.result()
            future2.result()
        
        order.refresh_from_db()
        self.assertTrue(order.payment_accepted_fully)
        # Both should succeed since accept_fully is idempotent when already at full amount
        self.assertEqual(len(results), 2)


class PaymentValidationTests(PaymentTestMixin, TestCase):
    """Tests for payment validation rules"""
    
    def test_cannot_record_negative_payment(self):
        """Negative payment amounts should be rejected"""
        order = self.create_order()
        
        with self.assertRaises(PaymentError):
            PaymentService.record_payment(
                order_id=order.id,
                received_by=self.admin_user,
                amount=Decimal('-5000')
            )
    
    def test_cannot_add_negative_extra_fee(self):
        """Negative extra fee should be rejected"""
        order = self.create_order()
        
        with self.assertRaises(PaymentError):
            PaymentService.add_extra_fee(
                order_id=order.id,
                amount=Decimal('-1000'),
                description='Invalid',
                added_by=self.admin_user
            )
    
    def test_nonexistent_order_raises_error(self):
        """Recording payment for nonexistent order should raise error"""
        with self.assertRaises(Order.DoesNotExist):
            PaymentService.record_payment(
                order_id=99999,
                received_by=self.admin_user,
                amount=Decimal('1000')
            )
    
    def test_overpayment_allowed(self):
        """Overpayment should be allowed (refund handled separately)"""
        order = self.create_order()
        
        result = PaymentService.record_payment(
            order_id=order.id,
            received_by=self.admin_user,
            amount=Decimal('150000')
        )
        
        self.assertTrue(result['success'])
        self.assertEqual(result['received'], 150000)
        self.assertEqual(result['remaining'], 0)  # Never negative


class PaymentFlowIntegrationTests(PaymentTestMixin, TestCase):
    """Integration tests for complete payment flows"""
    
    def test_full_partial_payment_flow(self):
        """Test complete flow: partial payments until fully paid"""
        order = self.create_order()
        
        # First partial payment
        result1 = PaymentService.record_payment(
            order_id=order.id,
            received_by=self.admin_user,
            amount=Decimal('40000')
        )
        self.assertEqual(result1['remaining'], 60000)
        self.assertEqual(result1['status'], 'payment_received')
        
        # Second partial payment
        result2 = PaymentService.record_payment(
            order_id=order.id,
            received_by=self.admin_user,
            amount=Decimal('30000')
        )
        self.assertEqual(result2['remaining'], 30000)
        
        # Final payment
        result3 = PaymentService.record_payment(
            order_id=order.id,
            received_by=self.admin_user,
            amount=Decimal('30000')
        )
        self.assertEqual(result3['remaining'], 0)
        self.assertEqual(result3['status'], 'payment_confirmed')
        self.assertTrue(result3['is_fully_paid'])
    
    def test_payment_with_extra_fee_flow(self):
        """Test payment flow when extra fee is added mid-payment"""
        order = self.create_order()
        
        # Initial partial payment
        PaymentService.record_payment(
            order_id=order.id,
            received_by=self.admin_user,
            amount=Decimal('50000')
        )
        
        # Add extra fee
        PaymentService.add_extra_fee(
            order_id=order.id,
            amount=Decimal('10000'),
            description='Rush delivery',
            added_by=self.admin_user
        )
        
        # Check remaining (should be 100000 + 10000 - 50000 = 60000)
        order.refresh_from_db()
        self.assertEqual(order.remaining, Decimal('60000'))
        
        # Complete payment
        result = PaymentService.record_payment(
            order_id=order.id,
            received_by=self.admin_user,
            amount=Decimal('60000')
        )
        
        self.assertEqual(result['remaining'], 0)
        self.assertTrue(result['is_fully_paid'])
    
    def test_force_accept_underpaid_order(self):
        """Test owner forcing acceptance of underpaid order"""
        order = self.create_order(received=30000)
        
        # Regular accept should fail
        with self.assertRaises(PaymentError):
            PaymentService.record_payment(
                order_id=order.id,
                received_by=self.admin_user,
                accept_fully=True
            )
        
        # Force accept should succeed
        result = PaymentService.record_payment(
            order_id=order.id,
            received_by=self.owner_admin,
            accept_fully=True,
            force_accept=True
        )
        
        self.assertTrue(result['success'])
        self.assertTrue(result['payment_accepted_fully'])
        # received should be set to total_due
        self.assertEqual(result['received'], 100000)
    
    def test_reset_and_repay_flow(self):
        """Test resetting payment and paying again"""
        order = self.create_order()
        
        # Make payment and accept
        PaymentService.record_payment(
            order_id=order.id,
            received_by=self.admin_user,
            amount=Decimal('100000')
        )
        PaymentService.record_payment(
            order_id=order.id,
            received_by=self.admin_user,
            accept_fully=True
        )
        
        order.refresh_from_db()
        self.assertTrue(order.is_fully_paid)
        
        # Reset
        PaymentService.reset_payment(
            order_id=order.id,
            reset_by=self.owner_admin
        )
        
        order.refresh_from_db()
        self.assertFalse(order.is_fully_paid)
        self.assertEqual(order.received, Decimal('0'))
        self.assertEqual(order.remaining, Decimal('100000'))
        
        # Pay again
        result = PaymentService.record_payment(
            order_id=order.id,
            received_by=self.admin_user,
            amount=Decimal('100000')
        )
        
        self.assertTrue(result['is_fully_paid'])
