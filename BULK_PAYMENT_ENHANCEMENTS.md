# Bulk Payment Page Enhancements

## Overview
Enhanced the bulk payment page with a comprehensive top debtors table, advanced filters, and proper RBAC (Role-Based Access Control).

## New Features

### 1. Top Debtors Table
- **Location**: Displayed at the top of the bulk payment page
- **Purpose**: Shows customers/agencies with the highest outstanding debts
- **Features**:
  - Displays up to 50 top debtors by default
  - Color-coded debt amounts:
    - 🔴 Red: Debts > $1,000 (High)
    - 🟠 Orange: Debts > $500 (Medium)
    - 🟢 Green: Debts < $500 (Low)
  - Shows customer type badges (Agency/Individual)
  - One-click selection to process payment
  - Real-time filtering

### 2. RBAC Filtering
Access is automatically filtered based on user role:

| User Role | Access Scope |
|-----------|--------------|
| **Superuser** | All centers and branches |
| **Owner** | Only their translation center (all branches) |
| **Manager** | Only their specific branch |
| **Staff** | No access (requires `can_manage_bulk_payments` permission) |

### 3. Advanced Filters

#### Customer Type Filter
- **All Customers**: Shows both agencies and individuals
- **Agencies Only**: B2B customers only
- **Individuals Only**: B2C customers only

#### Branch Filter (Conditional)
- **Superusers**: Can filter by any branch in any center
- **Owners**: Can filter by branches within their center
- **Managers**: See only their branch (no filter needed)

### 4. Interactive Table
- Click on any row to select that customer
- Click "Select" button to load customer details
- Automatically scrolls to payment processing section
- Visual feedback with row highlighting
- Selected row stays highlighted

## Implementation Details

### Backend Changes

#### New Function: `get_top_debtors(user, limit, customer_type, branch_id)`
**File**: `orders/bulk_payment_views.py` (lines 73-140)

```python
def get_top_debtors(user, limit=50, customer_type=None, branch_id=None):
    """
    Get top debtors with RBAC filtering.
    - Applies user's permission scope (superuser/owner/manager)
    - Filters by customer type (agency/individual)
    - Filters by branch if specified
    - Returns top N debtors sorted by debt amount
    """
```

**RBAC Logic**:
- Uses existing `get_user_orders(user)` function which handles RBAC
- Automatically restricts orders based on user's center/branch
- No additional permission checks needed (handled by decorator)

#### Updated View: `bulk_payment_page(request)`
**File**: `orders/bulk_payment_views.py` (lines 56-89)

**Changes**:
- Loads top 50 debtors on initial page load
- Determines which filters to show based on user role
- Passes debtor data to template

#### New API Endpoint: `get_top_debtors_api(request)`
**File**: `orders/bulk_payment_views.py` (lines 592-619)

**URL**: `/orders/bulk-payment/top-debtors/`
**Method**: GET
**Parameters**:
- `customer_type`: 'agency' | 'individual' | '' (optional)
- `branch_id`: integer (optional)
- `limit`: integer, default 50, max 100 (optional)

**Response**:
```json
{
  "debtors": [
    {
      "id": 123,
      "name": "ABC Translation Agency",
      "phone": "+998901234567",
      "is_agency": true,
      "customer_type": "Agency",
      "total_debt": 2500.50,
      "order_count": 12
    }
  ]
}
```

### Frontend Changes

#### New HTML Section
**File**: `templates/orders/bulk_payment.html`

Added before the existing payment form:
1. **Top Debtors Card** (lines 88-220)
   - Header with payment history link
   - Filter section with dropdowns
   - Responsive table with 7 columns
   - Empty state with success message

2. **Filter Section** (lines 110-143)
   - Customer type dropdown
   - Branch dropdown (conditional)
   - Apply/Clear filter buttons

#### New CSS Styles
**File**: `templates/orders/bulk_payment.html` (lines 85-113)

- `.top-debtors-table`: Table styling
- `.debtor-row`: Interactive row with hover effects
- `.debt-amount-high/medium/low`: Color-coded debt amounts
- `.filter-section`: Filter container styling

#### New JavaScript Functions
**File**: `templates/orders/bulk_payment.html` (lines 668-799)

1. **`selectDebtorFromTable(customerId)`**
   - Selects a customer from the table
   - Loads their debt details
   - Scrolls to payment form

2. **`applyFilters()`**
   - Reads filter values
   - Calls API with parameters
   - Updates table with results

3. **`clearFilters()`**
   - Resets all filters
   - Reloads default view

4. **`updateDebtorsTable(debtors)`**
   - Replaces table content
   - Maintains color coding
   - Reattaches event listeners

5. **`attachDebtorListeners()`**
   - Binds click events to table rows
   - Binds click events to select buttons

## User Workflow

### Before Enhancement
1. User opens bulk payment page
2. Sees empty form
3. Must search for customer by name/phone
4. Selects from search results
5. Processes payment

### After Enhancement
1. User opens bulk payment page
2. **Immediately sees top 50 debtors** sorted by debt amount
3. Can apply filters to narrow down results
4. Can **click directly** on any debtor in the table
5. System loads their details automatically
6. User processes payment

## Benefits

### 1. Improved Visibility
- Users can see problematic debtors immediately
- No need to remember customer names/phones
- Priority-based workflow (highest debts first)

### 2. Better Decision Making
- Color-coded amounts help prioritize
- See order counts to gauge complexity
- Filter by type to focus on specific segments

### 3. Enhanced Security
- RBAC ensures users only see their scope
- No data leakage between centers/branches
- Maintains existing permission structure

### 4. Faster Workflow
- Reduces search time
- One-click customer selection
- Visual feedback for selections

## Testing Checklist

- [ ] Superuser sees all debtors across all centers
- [ ] Owner sees only their center's debtors across all branches
- [ ] Manager sees only their branch's debtors
- [ ] Customer type filter works correctly
- [ ] Branch filter shows appropriate options
- [ ] Clicking table row selects customer and loads details
- [ ] Selected row highlights properly
- [ ] Filters update table via AJAX without page reload
- [ ] Clear filters resets to default view
- [ ] Empty state shows when no debts exist
- [ ] Debt amount colors display correctly
- [ ] Payment processing still works as before

## Performance Considerations

1. **Database Query Optimization**
   - Uses existing `get_user_orders()` with RBAC pre-filtering
   - Aggregates debt calculation in database (not Python)
   - Limited to 50 results by default (configurable up to 100)

2. **AJAX Loading**
   - Filters update via API without page reload
   - Only fetches debtor list (lightweight)
   - Fast response time

3. **Index Support**
   - Leverages existing indexes on orders table
   - Uses `bot_user` foreign key index
   - Efficient aggregation with `Sum()`

## Security Notes

1. **Permission Check**: All endpoints check `can_manage_bulk_payments` permission
2. **RBAC Enforcement**: Uses centralized `get_user_orders()` function
3. **Input Validation**: API validates customer_type and branch_id parameters
4. **SQL Injection Prevention**: Uses Django ORM (parameterized queries)

## Related Files

- **Views**: `orders/bulk_payment_views.py` (lines 56-140, 592-619)
- **URLs**: `orders/urls.py` (line 14, line 47)
- **Template**: `templates/orders/bulk_payment.html` (enhanced)
- **Models**: No changes (uses existing Order, BotUser models)

## Future Enhancements (Optional)

1. **Export to Excel**: Export top debtors list
2. **Debt Aging Report**: Show 0-30, 31-60, 60+ day breakdowns
3. **Bulk Actions**: Select multiple debtors for batch processing
4. **SMS Reminders**: Send payment reminders to top debtors
5. **Debt Trends**: Chart showing debt changes over time
6. **Custom Thresholds**: Configure high/medium/low debt thresholds
