# 🚀 Safe Deployment Guide

## Current Situation

**Production Commit:** `e4ca45a5f49ec2ddfaf04e537fdf99b5626ce0ad`  
**Current Commit:** `267576f` (16 commits ahead)  
**Status:** All changes committed, working tree clean ✅

---

## ⚠️ Changes Since Production

### 🗄️ Database Migrations (CRITICAL!)

You have **7 new migrations** that MUST be run:

#### Orders App:
- `0011_bulkpayment_paymentorderlink_and_more.py` - Bulk payment system tables

#### Organizations App:
- `0019_role_can_assign_bulk_payment_permission_and_more.py` - Bulk payment permissions
- `0020_role_can_create_languages_role_can_edit_languages_and_more.py` - Language management permissions

#### Services App:
- `0004_product_agency_copy_price_decimal_and_more.py` - Agency pricing changes
- `0005_alter_product_agency_copy_price_decimal_and_more.py` - Decimal value adjustments
- `0006_split_expense_price_fields.py` - **BREAKING**: Split expense pricing
- `0007_add_language_pricing.py` - Language-specific pricing

### 📝 Major Code Changes:

1. **Translation System** ✅ Safe
   - Added translations (UZ/RU/EN)
   - Compiled .mo files
   - Updated translations.js

2. **Bulk Payment System** ⚠️ New Feature
   - New views and URLs
   - New templates
   - New models (BulkPayment, PaymentOrderLink)

3. **Expense Model Changes** ⚠️ Breaking Change
   - Split `price` field into `price_original` and `price_copy`
   - Requires data migration

4. **Permission System** ✅ Safe (adds new permissions)
   - New bulk payment permissions
   - New language management permissions

5. **Excel Export Fixes** ✅ Safe
   - Fixed TruncDate error
   - Improved export functionality

6. **Product Model Changes** ⚠️ Schema Change
   - Changed `agency_copy_price_percentage` from percentage to decimal
   - Added language-specific pricing

---

## 🛡️ Pre-Deployment Checklist

### 1. Backup Your Production Database

```bash
# SSH into your production server
ssh user@your-server.com

# Create backup
cd /home/wemard/app
./backup_db.sh

# Verify backup exists
ls -lh backups/

# Download backup to local machine (optional but recommended)
# From your local machine:
scp user@your-server.com:/home/wemard/app/backups/backup_*.sql.gz ./local-backup/
```

### 2. Check Current Production State

```bash
# On production server
cd /home/wemard/app
source venv/bin/activate

# Check current commit
git log -1 --oneline

# Check for uncommitted changes
git status

# Check which migrations are applied
python manage.py showmigrations
```

### 3. Review Environment Variables

Check if any new environment variables are needed:

```bash
# Compare .env files
diff .env.example .env
```

**New/Updated Variables (none required for this deployment):**
- All existing variables should work

---

## 📋 Deployment Steps (SAFE METHOD)

### Step 1: Pull Changes

```bash
# On production server
cd /home/wemard/app
source venv/bin/activate

# Fetch latest changes
git fetch origin

# See what will be pulled
git log HEAD..origin/main --oneline

# Pull changes
git pull origin main
```

### Step 2: Update Dependencies

```bash
# Check if requirements.txt changed
git diff e4ca45a5f49ec2ddfaf04e537fdf99b5626ce0ad HEAD -- requirements.txt

# If changed, update packages
pip install -r requirements.txt --upgrade
```

### Step 3: Run Migrations (CRITICAL STEP!)

```bash
# DRY RUN FIRST - See what will happen
python manage.py migrate --plan

# Check for any migration conflicts
python manage.py showmigrations

# Run migrations
python manage.py migrate

# Verify migrations succeeded
python manage.py showmigrations | grep "\[ \]"  # Should be empty
```

**Expected Migration Order:**
```
services.0004_product_agency_copy_price_decimal_and_more
services.0005_alter_product_agency_copy_price_decimal_and_more
services.0006_split_expense_price_fields
services.0007_add_language_pricing
organizations.0019_role_can_assign_bulk_payment_permission_and_more
organizations.0020_role_can_create_languages_role_can_edit_languages_and_more
orders.0011_bulkpayment_paymentorderlink_and_more
```

### Step 4: Compile Translations

```bash
# Compile updated translation files
python compile_po.py

# Or use Django command
python manage.py compilemessages
```

### Step 5: Collect Static Files

```bash
# Update static files (CSS, JS, translations.js)
python manage.py collectstatic --noinput

# Verify static files updated
ls -lh staticfiles/js/translations.js
```

### Step 6: Restart Application

```bash
# Restart Gunicorn
sudo supervisorctl restart wemard

# Check status
sudo supervisorctl status wemard

# If using systemd instead
sudo systemctl restart wemard

# Restart Celery workers (if running)
sudo supervisorctl restart wemard-celery
```

### Step 7: Verify Deployment

```bash
# Check application logs
tail -f /home/wemard/app/logs/error.log

# Check Gunicorn logs
sudo tail -f /var/log/supervisor/wemard-stderr.log

# Test application
curl -I https://yourdomain.com
# Should return: HTTP/2 200
```

### Step 8: Test Critical Features

**Test Checklist:**

1. **✅ Login to Admin Dashboard**
   ```
   https://yourdomain.com/admin/login/
   ```

2. **✅ Check Dashboard Loads**
   ```
   https://yourdomain.com/
   ```

3. **✅ Test Order Creation**
   - Go to Orders → Create Order
   - Verify product selection works
   - Check if receipt upload works

4. **✅ Test Bulk Payment System (NEW FEATURE)**
   ```
   https://yourdomain.com/orders/bulk-payment/
   ```
   - Should load without errors
   - Test customer search
   - Test payment processing

5. **✅ Test Translation Switching**
   - Switch language to Uzbek
   - Switch to Russian
   - Switch to English
   - Verify sidebar translations work

6. **✅ Test Reports/Excel Export**
   - Go to Reports → Financial Report
   - Click "Export to Excel"
   - Should download without errors

7. **✅ Test Bot (if applicable)**
   - Send `/start` to your bot
   - Verify bot responds
   - Test order creation flow

---

## 🚨 Rollback Plan (If Things Go Wrong)

### Quick Rollback

```bash
# Stop application
sudo supervisorctl stop wemard

# Rollback code
git reset --hard e4ca45a5f49ec2ddfaf04e537fdf99b5626ce0ad

# Restart application
sudo supervisorctl start wemard
```

### Database Rollback (ONLY IF NEEDED)

```bash
# Stop application
sudo supervisorctl stop wemard

# Restore database from backup
# For PostgreSQL:
dropdb wemard_db
createdb wemard_db
gunzip -c backups/backup_YYYYMMDD_HHMMSS.sql.gz | psql wemard_db

# For SQLite:
gunzip -c backups/database/backup_sqlite_*.db.gz > db.sqlite3

# Rollback code
git reset --hard e4ca45a5f49ec2ddfaf04e537fdf99b5626ce0ad

# Restart application
sudo supervisorctl start wemard
```

---

## ⚠️ Potential Issues & Solutions

### Issue 1: Migration Fails

**Symptom:** Migration error during `python manage.py migrate`

**Solution:**
```bash
# Check which migration failed
python manage.py showmigrations

# Try migrating app by app
python manage.py migrate services
python manage.py migrate organizations
python manage.py migrate orders

# If specific migration fails, you can fake it (USE WITH CAUTION)
python manage.py migrate services 0006 --fake
```

### Issue 2: Expense Model Data Missing

**Symptom:** Old orders show incorrect expense calculations

**Solution:**
```bash
# Run data migration to populate new fields
python manage.py shell

# In shell:
from services.models import Expense
for expense in Expense.objects.filter(price_original__isnull=True):
    if expense.price:  # Old price field
        expense.price_original = expense.price
        expense.price_copy = expense.price * 0.5  # 50% for copy (adjust as needed)
        expense.save()
```

### Issue 3: Permissions Not Working

**Symptom:** Users can't access bulk payment or language management

**Solution:**
```bash
# Assign new permissions to roles
python manage.py shell

# In shell:
from organizations.models import Role
owner_role = Role.objects.filter(is_owner=True).first()
if owner_role:
    owner_role.can_manage_bulk_payments = True
    owner_role.can_create_languages = True
    owner_role.can_edit_languages = True
    owner_role.can_delete_languages = True
    owner_role.save()
```

### Issue 4: Static Files Not Updated

**Symptom:** Old translations.js, CSS not loading

**Solution:**
```bash
# Clear Django cache
python manage.py shell
from django.core.cache import cache
cache.clear()

# Re-collect static files
rm -rf staticfiles/*
python manage.py collectstatic --noinput

# Clear browser cache or hard refresh (Ctrl+Shift+R)
```

### Issue 5: 502 Bad Gateway

**Symptom:** Nginx returns 502 error

**Solution:**
```bash
# Check Gunicorn is running
sudo supervisorctl status wemard

# Check Gunicorn logs
sudo tail -f /var/log/supervisor/wemard-stderr.log

# Restart everything
sudo supervisorctl restart wemard
sudo systemctl restart nginx
```

---

## 📊 Post-Deployment Verification

### 1. Check Application Health

```bash
# Application responds
curl -I https://yourdomain.com
# Expected: HTTP/2 200

# Database connection works
python manage.py dbshell
\dt  # List tables
\q   # Quit

# Redis connection works
redis-cli ping
# Expected: PONG
```

### 2. Monitor Logs

```bash
# Watch application logs
tail -f logs/error.log

# Watch Gunicorn logs
sudo tail -f /var/log/supervisor/wemard-stderr.log

# Watch Nginx logs
sudo tail -f /var/log/nginx/error.log
```

### 3. Performance Check

```bash
# Check response time
time curl -o /dev/null -s -w '%{time_total}\n' https://yourdomain.com
# Should be < 2 seconds

# Check memory usage
free -h

# Check disk space
df -h
```

---

## ✅ Success Criteria

Deployment is successful when:

- [ ] All migrations applied successfully
- [ ] No errors in logs
- [ ] Admin dashboard loads
- [ ] Can create new order
- [ ] Bulk payment page loads
- [ ] Excel exports work
- [ ] Translations work (UZ/RU/EN)
- [ ] Bot responds (if applicable)
- [ ] No 500 errors
- [ ] Response time < 2 seconds

---

## 📞 Emergency Contacts

If deployment fails and you need help:

1. **Rollback immediately** using rollback plan above
2. Check logs for specific error messages
3. Restore database from backup if needed
4. Contact your team or developer

---

## 🔄 Recommended Deployment Strategy

### Option A: Blue-Green Deployment (SAFEST)

1. Keep production running (green)
2. Setup parallel environment (blue)
3. Deploy to blue environment
4. Test thoroughly
5. Switch traffic to blue
6. Keep green as backup

### Option B: Maintenance Window (RECOMMENDED)

1. Announce maintenance (15-30 minutes)
2. Put site in maintenance mode
3. Deploy changes
4. Run tests
5. Take site live
6. Monitor closely

### Option C: Off-Peak Deployment (ACCEPTABLE)

1. Deploy during low traffic hours (2-4 AM)
2. Have rollback plan ready
3. Monitor closely for 1 hour
4. Fix issues immediately or rollback

---

## 📝 Deployment Log Template

Keep a record of your deployments:

```
Date: YYYY-MM-DD HH:MM
Deployed by: [Your Name]
From Commit: e4ca45a5f49ec2ddfaf04e537fdf99b5626ce0ad
To Commit: 267576f
Migrations Run: 7
Downtime: X minutes
Issues Encountered: [None / List issues]
Rollback Required: [Yes / No]
Notes: [Additional notes]
```

---

## 🎯 Summary

**YES, you can safely deploy, BUT:**

1. ✅ **Take a database backup first** (mandatory!)
2. ✅ **Run migrations** (7 new migrations required)
3. ✅ **Compile translations** (updated .po files)
4. ✅ **Collect static files** (updated translations.js)
5. ✅ **Test thoroughly** before declaring success
6. ✅ **Have rollback plan ready**

**Risk Level:** 🟡 **MEDIUM**
- New database tables (bulk payment system)
- Schema changes (expense price fields, product pricing)
- New features (may have bugs)

**Recommendation:**
- Deploy during low-traffic hours
- Announce brief maintenance window
- Test on staging environment first (if available)
- Have someone available to help if issues arise

---

**Good luck with your deployment! 🚀**

If you encounter any issues, follow the rollback plan immediately and investigate the error messages.
