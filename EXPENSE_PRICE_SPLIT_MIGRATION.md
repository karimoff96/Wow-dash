# Expense Price Field Split - Migration Summary

## Overview
Successfully split the single `price` field in the Expense model into two separate fields:
- `price_for_original` - Cost for the original document
- `price_for_copy` - Cost per copy document

## Data Safety Measures

### Migration Strategy (File: 0006_split_expense_price_fields.py)
The migration is designed to be **100% safe** and preserve all existing data:

1. **Step 1**: Add new fields with default values (0)
2. **Step 2**: **Data Migration** - Copy existing `price` data:
   - All existing `price` values → `price_for_original`
   - Set `price_for_copy` = 0 as safe default
3. **Step 3**: Remove old `price` field (only after data is copied)

### Rollback Support
- Includes backward migration function
- Can safely rollback if needed
- Restores original `price` field from `price_for_original`

## What Was Changed

### 1. Model (services/models.py)
```python
# OLD:
price = models.DecimalField(...)

# NEW:
price_for_original = models.DecimalField(..., default=0)
price_for_copy = models.DecimalField(..., default=0)
```

Added helper methods:
- `calculate_total_for_order(copy_number)` - Calculate total expense for an order
- Updated `__str__` to show both prices

### 2. Calculation Logic Updated
**Files Modified:**
- `WowDash/reports_views.py` (5 locations)
- `core/export_service.py` (5 locations)

**Old Calculation:**
```python
expense_total = expense.price * order_count
```

**New Calculation:**
```python
for order in orders:
    expense_total += expense.price_for_original + (expense.price_for_copy * order.copy_number)
```

This properly accounts for:
- Each order gets 1 original (price_for_original)
- Each order gets N copies (price_for_copy * copy_number)

### 3. Views Updated (services/views.py)
- `addExpense()` - Now handles two price inputs
- `editExpense()` - Now handles two price inputs
- `createExpenseInline()` - AJAX endpoint updated for two prices

All views include:
- Validation for both price fields
- Error handling for invalid values
- Maximum value checks (9,999,999,999.99)

### 4. Export Service
Excel exports now show both columns:
- "Price (Original)" column
- "Price (Per Copy)" column

## Next Steps Needed

### Templates to Update:
1. ✅ **services/admin.py** - Add both fields to admin interface
2. ⏳ **templates/services/addExpense.html** - Two price input fields
3. ⏳ **templates/services/editExpense.html** - Two price input fields
4. ⏳ **templates/services/expenseList.html** - Display both prices
5. ⏳ **templates/services/expenseDetail.html** - Display both prices
6. ⏳ **templates/services/addProduct.html** - Inline expense modal
7. ⏳ **templates/services/editProduct.html** - Inline expense modal
8. ⏳ **templates/reports/expense_analytics.html** - Display both prices

### Tests to Update:
9. ⏳ **services/tests.py** - Update all expense tests

## Running the Migration

**IMPORTANT:** Test on a backup first!

```bash
# 1. Backup your database first!
python manage.py dumpdata services.Expense > expense_backup.json

# 2. Run migration
python manage.py migrate services 0006

# 3. Verify data integrity
python manage.py shell
>>> from services.models import Expense
>>> for e in Expense.objects.all():
...     print(f"{e.name}: Original={e.price_for_original}, Copy={e.price_for_copy}")

# 4. If needed, rollback:
python manage.py migrate services 0005
```

## Post-Migration Admin Tasks

After migration, admins should review expenses and set proper `price_for_copy` values:

1. For expenses that don't scale with copies → leave `price_for_copy` = 0
2. For expenses that do scale → set appropriate per-copy price

Example:
- **Paper cost**: price_for_original=5000, price_for_copy=3000
- **Binding**: price_for_original=2000, price_for_copy=2000  
- **Processing fee**: price_for_original=1000, price_for_copy=0 (one-time)

## Backwards Compatibility

The code changes are **not** backwards compatible with the old schema because:
- The `price` field is removed in the migration
- All calculations now use two separate fields

**Solution**: Always run migrations before deploying code changes!

## Testing Checklist

- [ ] Run migration on test/staging database
- [ ] Verify all existing expense data is preserved
- [ ] Create new expense with both prices
- [ ] Edit existing expense
- [ ] Generate expense report
- [ ] Export expense data to Excel
- [ ] View expense analytics
- [ ] Test inline expense creation from product page
- [ ] Verify order calculations include copy pricing
- [ ] Test rollback migration

