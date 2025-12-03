"""
Payment Service for Order Management

Handles partial payments, extra fees, and payment confirmations
with proper validation and atomic database operations.
"""
from decimal import Decimal, InvalidOperation
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from orders.models import Order
from organizations.models import AdminUser
from core.audit import log_action
import logging

logger = logging.getLogger(__name__)


class PaymentError(Exception):
    """Custom exception for payment-related errors"""
    pass


class PaymentService:
    """
    Service class for handling order payments.
    All operations are atomic to prevent race conditions.
    """
    
    @staticmethod
    def validate_amount(amount):
        """Validate that amount is a positive decimal"""
        if amount is None:
            return Decimal('0.00')
        
        try:
            decimal_amount = Decimal(str(amount))
            if decimal_amount < 0:
                raise PaymentError("Amount cannot be negative")
            return decimal_amount.quantize(Decimal('0.01'))
        except (InvalidOperation, ValueError) as e:
            raise PaymentError(f"Invalid amount: {amount}")
    
    @staticmethod
    @transaction.atomic
    def record_payment(
        order_id: int,
        received_by: AdminUser,
        amount: Decimal = None,
        accept_fully: bool = False,
        extra_fee: Decimal = None,
        extra_fee_description: str = None,
        force_accept: bool = False,
        request=None
    ):
        """
        Record a payment for an order with proper validation and locking.
        
        Args:
            order_id: The order ID to update
            received_by: AdminUser who is recording the payment
            amount: Amount being paid (for partial payments)
            accept_fully: If True, mark payment as fully accepted
            extra_fee: Additional fee to add
            extra_fee_description: Reason for extra fee
            force_accept: If True, allow owner to force full acceptance even if underpaid
            request: HTTP request for audit logging
            
        Returns:
            dict with updated order info and status
            
        Raises:
            PaymentError: If validation fails
        """
        # Lock the order row for update to prevent race conditions
        order = Order.objects.select_for_update().get(id=order_id)
        
        # Validate amounts
        if amount is not None:
            amount = PaymentService.validate_amount(amount)
        
        if extra_fee is not None:
            extra_fee = PaymentService.validate_amount(extra_fee)
        
        changes = {}
        
        # Handle extra fee update
        if extra_fee is not None:
            old_extra_fee = order.extra_fee
            order.extra_fee = extra_fee
            order.extra_fee_description = extra_fee_description or order.extra_fee_description
            changes['extra_fee'] = f"{old_extra_fee} → {extra_fee}"
            if extra_fee_description:
                changes['extra_fee_description'] = extra_fee_description
        
        # Handle payment
        if accept_fully:
            # Check if amount received is less than total (needs force_accept from owner)
            total_due = order.total_due
            current_received = Decimal(str(order.received or 0))
            
            if not force_accept and current_received < total_due:
                raise PaymentError(
                    f"Cannot mark as fully paid. Received {current_received} but total due is {total_due}. "
                    "Use force_accept=True (owner only) to override."
                )
            
            old_received = order.received
            order.payment_accepted_fully = True
            order.received = total_due  # Set received to total
            order.payment_received_by = received_by
            order.payment_received_at = timezone.now()
            order.status = "payment_confirmed"
            
            changes['payment_accepted_fully'] = True
            changes['received'] = f"{old_received} → {order.received}"
            changes['status'] = 'payment_confirmed'
            
        elif amount is not None and amount > 0:
            # Partial payment
            old_received = Decimal(str(order.received or 0))
            new_received = old_received + amount
            
            order.received = new_received
            order.payment_received_by = received_by
            order.payment_received_at = timezone.now()
            
            changes['received'] = f"{old_received} → {new_received} (+{amount})"
            
            # Check if fully paid now
            if order.remaining <= 0:
                order.status = "payment_confirmed"
                changes['status'] = 'payment_confirmed (fully paid)'
            else:
                order.status = "payment_received"
                changes['status'] = f'payment_received (remaining: {order.remaining})'
        
        # Save only payment-related fields to avoid full model validation
        update_fields = [
            'received', 'extra_fee', 'extra_fee_description', 
            'payment_accepted_fully', 'payment_received_by', 
            'payment_received_at', 'status', 'updated_at'
        ]
        order.save(update_fields=update_fields)
        
        # Log the action
        if request and changes:
            log_action(
                user=request.user,
                action='payment_update',
                target=order,
                details=f"Payment update: {changes}",
                request=request
            )
        
        logger.info(f"Payment recorded for order {order_id}: {changes}")
        
        return {
            'success': True,
            'order_id': order.id,
            'total_price': float(order.total_price),
            'extra_fee': float(order.extra_fee),
            'total_due': float(order.total_due),
            'received': float(order.received),
            'remaining': float(order.remaining),
            'payment_accepted_fully': order.payment_accepted_fully,
            'is_fully_paid': order.is_fully_paid,
            'payment_percentage': order.payment_percentage,
            'status': order.status,
        }
    
    @staticmethod
    @transaction.atomic
    def add_extra_fee(
        order_id: int,
        amount: Decimal,
        description: str,
        added_by: AdminUser,
        request=None
    ):
        """
        Add an extra fee to an order.
        
        Args:
            order_id: The order ID
            amount: Extra fee amount (must be positive)
            description: Reason for the fee
            added_by: AdminUser adding the fee
            request: HTTP request for logging
        """
        amount = PaymentService.validate_amount(amount)
        if amount <= 0:
            raise PaymentError("Extra fee must be a positive amount")
        
        order = Order.objects.select_for_update().get(id=order_id)
        
        old_extra_fee = order.extra_fee
        order.extra_fee = Decimal(str(old_extra_fee or 0)) + amount
        order.extra_fee_description = description
        order.save(update_fields=['extra_fee', 'extra_fee_description', 'updated_at'])
        
        if request:
            log_action(
                user=request.user,
                action='add_extra_fee',
                target=order,
                details=f"Added extra fee: {amount} ({description})",
                request=request
            )
        
        return {
            'success': True,
            'extra_fee': float(order.extra_fee),
            'total_due': float(order.total_due),
            'remaining': float(order.remaining),
        }
    
    @staticmethod
    @transaction.atomic
    def reset_payment(order_id: int, reset_by: AdminUser, request=None):
        """
        Reset payment status for an order.
        This clears received amount and payment_accepted_fully.
        Only owners/superusers should be able to do this.
        """
        order = Order.objects.select_for_update().get(id=order_id)
        
        old_received = order.received
        old_status = order.payment_accepted_fully
        
        order.received = Decimal('0.00')
        order.payment_accepted_fully = False
        order.payment_received_by = None
        order.payment_received_at = None
        order.status = 'pending'
        
        order.save(update_fields=[
            'received', 'payment_accepted_fully', 
            'payment_received_by', 'payment_received_at',
            'status', 'updated_at'
        ])
        
        if request:
            log_action(
                user=request.user,
                action='reset_payment',
                target=order,
                details=f"Payment reset. Was: received={old_received}, accepted_fully={old_status}",
                request=request
            )
        
        return {
            'success': True,
            'received': 0,
            'payment_accepted_fully': False,
            'remaining': float(order.remaining),
            'status': order.status,
        }


# Convenience functions
def record_payment(order_id, received_by, amount=None, accept_fully=False, **kwargs):
    """Convenience function for PaymentService.record_payment"""
    return PaymentService.record_payment(
        order_id=order_id,
        received_by=received_by,
        amount=amount,
        accept_fully=accept_fully,
        **kwargs
    )


def add_extra_fee(order_id, amount, description, added_by, **kwargs):
    """Convenience function for PaymentService.add_extra_fee"""
    return PaymentService.add_extra_fee(
        order_id=order_id,
        amount=amount,
        description=description,
        added_by=added_by,
        **kwargs
    )
