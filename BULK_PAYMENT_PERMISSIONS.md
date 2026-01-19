# Bulk Payment Permissions System

## Overview

The bulk payment feature now uses a **permission-based access control** system instead of role-based access. This provides more flexibility for superusers to grant access to any role.

## New Permissions

### 1. `can_manage_bulk_payments`
- **Purpose**: Allows users to process bulk payments for customer/agency debts across multiple orders
- **Access**:
  - View bulk payment page
  - Search customers with outstanding debts
  - Preview payment distribution (FIFO)
  - Process bulk payments
  - View payment history
- **Default Assignment**:
  - ✅ Owner role: Enabled
  - ✅ Manager role: Enabled
  - ❌ Staff role: Disabled

### 2. `can_assign_bulk_payment_permission`
- **Purpose**: Allows users to grant the `can_manage_bulk_payments` permission to other roles
- **Access**:
  - Edit role permissions in the role management interface
  - Assign bulk payment access to any role
- **Default Assignment**:
  - ✅ Owner role: Enabled
  - ❌ Manager role: Disabled
  - ❌ Staff role: Disabled
- **⚠️ Security Note**: This is a powerful permission. Only grant it to trusted users.

## How to Assign Permissions

### For Superusers
1. Navigate to **Organizations** → **Roles**
2. Click on any role (Owner, Manager, Staff, or custom roles)
3. Scroll to the **Bulk Payments** section (highlighted in yellow/orange)
4. Check the desired permissions:
   - ☑️ **Process Bulk Payments**: User can manage bulk payments
   - ☑️ **Assign Bulk Payment Access**: User can grant bulk payment permission to others
5. Click **Update Role**

### For Users with `can_assign_bulk_payment_permission`
- Same process as superusers
- Can only edit roles they have permission to edit

## Implementation Details

### Database Changes
- Added two new boolean fields to the `Role` model:
  - `can_manage_bulk_payments` (default: False)
  - `can_assign_bulk_payment_permission` (default: False)
- Migration: `organizations/migrations/0019_role_can_assign_bulk_payment_permission_and_more.py`

### Permission Check Function
Located in: `orders/bulk_payment_views.py`

```python
def can_manage_bulk_payments(user):
    """
    Check if user has permission to manage bulk payments.
    
    Returns True if:
    - User is a superuser, OR
    - User's role has can_manage_bulk_payments permission
    """
```

### Views Protected
All bulk payment views use the `@require_permission(can_manage_bulk_payments)` decorator:
- `bulk_payment_page()` - Main UI
- `search_customers_with_debt()` - Customer search API
- `get_customer_debt_details()` - Debt details API
- `preview_payment_distribution()` - Payment preview API
- `process_bulk_payment()` - Payment processing
- `payment_history()` - Payment history view

## Access URLs
- Main Page: `/orders/bulk-payment/`
- Payment History: `/orders/bulk-payment/history/`
- Navigation: Reports → Bulk Payments (menu item visible only to users with permission)

## Security Considerations

1. **Superuser Override**: Superusers always have access, regardless of role permissions
2. **Atomic Transactions**: All payment processing uses database transactions for data integrity
3. **Audit Trail**: Every payment is logged with:
   - Who processed it
   - When it was processed
   - Which orders were affected
   - Payment amounts and methods
4. **Permission Hierarchy**: The `can_assign_bulk_payment_permission` is a meta-permission that controls who can grant access

## Migration Safety

✅ **Production-Safe**: All new permission fields are nullable with default values of `False`
✅ **No Breaking Changes**: Existing roles continue to work without modification
✅ **Backwards Compatible**: Permission checks gracefully handle missing attributes

## Quick Reference

| User Type | Process Payments | Grant Permission |
|-----------|-----------------|------------------|
| Superuser | ✅ Always | ✅ Always |
| Owner (default) | ✅ Yes | ✅ Yes |
| Manager (default) | ✅ Yes | ❌ No |
| Staff (default) | ❌ No | ❌ No |
| Custom Roles | 🔧 Configurable | 🔧 Configurable |

## Testing Checklist

- [ ] Superuser can access bulk payment page
- [ ] User with `can_manage_bulk_payments` can access bulk payment page
- [ ] User without permission gets access denied error
- [ ] User with `can_assign_bulk_payment_permission` can edit role permissions
- [ ] Permission changes take effect immediately (may require re-login)
- [ ] Payment processing works correctly with new permission system
- [ ] Audit logs capture payment activities

## Related Files

- **Models**: `organizations/models.py` (lines 300-312)
- **Views**: `orders/bulk_payment_views.py` (lines 25-47)
- **Admin**: `organizations/admin.py` (lines 151-162)
- **Templates**: `templates/organizations/role_form.html` (lines 850-890)
- **URLs**: `orders/urls.py` (lines 41-46)
- **Migration**: `organizations/migrations/0019_*.py`
