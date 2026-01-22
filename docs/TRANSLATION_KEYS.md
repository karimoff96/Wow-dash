# Translation Keys Documentation

This document lists all translation keys added to templates during the styling and i18n overhaul.

## Table Keys (`table.*`)

```python
# Table headers
"table.customer": "Customer"
"table.product": "Product"
"table.price": "Price"
"table.status": "Status"
"table.date": "Date"
"table.action": "Actions"
"table.amount": "Amount"
"table.type": "Type"
"table.rate": "Rate"
"table.language": "Language"
"table.shortCode": "Short Code"
```

## Form Keys (`form.*`)

```python
# Customer information
"form.customerFirstName": "Customer's first name"
"form.customerLastName": "Customer's last name"
"form.phoneNumber": "+998 XX XXX XX XX"
"form.optionalNotes": "Optional notes or special instructions..."
"form.optionalDescription": "Optional description..."

# User fields
"form.fullName": "Full Name"
"form.enterFullName": "Enter full name"
"form.telegramUsername": "telegram_username"
"form.telegramUserId": "Telegram User ID"
"form.telegramUserIdPlaceholder": "123456789"
"form.usernameHint": "Optional - Telegram username without @"
"form.telegramUserIdHint": "Optional - Numeric Telegram ID"

# Language fields
"form.languageName": "Language Name"
"form.languageNamePlaceholder": "e.g., English, French, Spanish"
"form.shortName": "Short Name"
"form.shortNamePlaceholder": "e.g., EN, FR, ES"
"form.shortNameHint": "2-3 letter code (will be auto-capitalized)"
"form.searchLanguage": "Search by language name or code..."
```

## Detail Keys (`detail.*`)

```python
# Order detail page
"detail.file": "File"
"detail.component": "Component"
"detail.productPrice": "Product Price"
"detail.languagePrice": "Language Price"
"detail.combinedPrice": "Combined Price"
"detail.uploaded": "Uploaded"
"detail.deleteOrder": "Delete Order"
```

## Report Keys (`report.*`)

```python
# Debtors report
"report.debt": "Debt"
"report.expected": "Expected"
"report.received": "Received"

# General reports
"report.revenue": "Revenue"
"report.avgValue": "Avg Value"
"report.totalSpent": "Total Spent"
```

## Expense Keys (`expense.*`)

```python
# Expense types
"expense.b2b": "B2B"
"expense.b2c": "B2C"
"expense.both": "Both"
```

## Common Keys (`common.*`)

```python
# General terms
"common.pages": "Pages"
"common.total": "Total"
"common.count": "Count"
"common.location": "Location"
"common.branch": "Branch"
"common.center": "Center"
"common.staff": "Staff"
"common.search": "Search"
"common.cancel": "Cancel"
```

## Pricing Keys (`pricing.*`)

```python
# Pricing labels
"pricing.agencyPricing": "Agency Pricing (UZS)"
"pricing.ordinaryPricing": "Ordinary User Pricing (UZS)"
```

## Bulk Payment Keys (JavaScript - already in bulk_payment.html)

```javascript
// These use {% trans %} tags in JavaScript
"Paid by": translations.paidBy
"Order": translations.order
"days": translations.days
"Total": translations.total
"Paid": translations.paid
"Remaining": translations.remaining
"UZS": translations.uzs
```

## Status Keys (`status.*`)

```python
# Order/task statuses (already in existing locale files)
"status.completed": "Completed"
"status.pending": "Pending"
"status.inProgress": "In Progress"
```

## Sidebar Keys (`sidebar.*`)

```python
# Navigation (already in existing locale files)
"sidebar.customers": "Customers"
```

## Instructions

### Adding Keys to Django PO Files

1. Open each locale file:
   - `locale/en/LC_MESSAGES/django.po`
   - `locale/ru/LC_MESSAGES/django.po`
   - `locale/uz/LC_MESSAGES/django.po`

2. Add translations in this format:
   ```po
   msgid "table.customer"
   msgstr "Customer"  # (English)
   msgstr "Клиент"    # (Russian)
   msgstr "Mijoz"     # (Uzbek)
   ```

3. After updating all PO files, compile them:
   ```bash
   python manage.py compilemessages
   ```

### Translation Examples

#### English (`locale/en/LC_MESSAGES/django.po`)
```po
msgid "table.customer"
msgstr "Customer"

msgid "form.customerFirstName"
msgstr "Customer's first name"

msgid "report.debt"
msgstr "Debt"
```

#### Russian (`locale/ru/LC_MESSAGES/django.po`)
```po
msgid "table.customer"
msgstr "Клиент"

msgid "form.customerFirstName"
msgstr "Имя клиента"

msgid "report.debt"
msgstr "Долг"
```

#### Uzbek (`locale/uz/LC_MESSAGES/django.po`)
```po
msgid "table.customer"
msgstr "Mijoz"

msgid "form.customerFirstName"
msgstr "Mijozning ismi"

msgid "report.debt"
msgstr "Qarz"
```

## Files Modified

### Templates with data-i18n Attributes
- ✅ `templates/orders/myOrders.html` - Table headers
- ✅ `templates/orders/orderCreate.html` - Form placeholders
- ✅ `templates/orders/orderEdit.html` - Form placeholders
- ✅ `templates/orders/orderDetail.html` - Table headers
- ✅ `templates/orders/bulk_payment.html` - JavaScript translations
- ✅ `templates/reports/debtors_report.html` - Table headers
- ✅ `templates/reports/expense_analytics.html` - Table headers
- ✅ `templates/users/addUser.html` - Form labels and placeholders
- ✅ `templates/users/editUser.html` - Form labels and placeholders
- ✅ `templates/services/languageList.html` - Form and table headers
- ✅ `templates/finance.html` - Already complete (uses data-i18n throughout)

### CSS Files
- ✅ `static/css/custom-overrides.css` - Comprehensive styling system

### Layout Files
- ✅ `templates/partials/head.html` - Includes custom CSS

## Notes

- All report templates already use `data-i18n` extensively
- The `data-i18n` attribute is processed by JavaScript on page load
- The `data-i18n-placeholder` attribute specifically handles input placeholders
- JavaScript in `bulk_payment.html` uses Django's `{% trans %}` tags within `<script>` blocks
- Custom CSS ensures consistent styling across all themes (light/dark)

## Next Steps

1. ✅ Add all keys to django.po files (en, ru, uz)
2. ✅ Run `python manage.py compilemessages`
3. ⏳ Test language switching on all modified pages
4. ⏳ Verify WCAG AA contrast compliance
5. ⏳ Check dark theme compatibility
