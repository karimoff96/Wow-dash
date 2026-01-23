# 📚 WowDash User Guide

**Complete Guide to Using the Translation Center Management System**

Version 2.0 | Last Updated: January 2026

---

## 📖 Table of Contents

1. [Getting Started](#getting-started)
2. [User Roles](#user-roles)
3. [Dashboard Overview](#dashboard-overview)
4. [Order Management](#order-management)
5. [Customer Management](#customer-management)
6. [Marketing & Broadcasts](#marketing--broadcasts)
7. [Reports & Analytics](#reports--analytics)
8. [File Archive Management](#file-archive-management)
9. [Organization Settings](#organization-settings)
10. [Telegram Bot Configuration](#telegram-bot-configuration)
11. [Best Practices](#best-practices)
12. [Troubleshooting](#troubleshooting)

---

## 🚀 Getting Started

### First Time Login

1. **Access the System**
   - Navigate to your center's URL (e.g., `https://wowdash.example.com`)
   - Use credentials provided by your administrator
   - Default login page: `/admin/login`

2. **Set Your Language**
   - Click language selector in top navigation
   - Choose: English (EN), Russian (RU), or Uzbek (UZ)
   - Settings are saved per user

3. **Update Your Profile**
   - Click your name in top-right corner
   - Update contact information
   - Set notification preferences

### Dashboard Layout

```
┌──────────────────────────────────────────────────────────┐
│  WowDash Logo    [Dashboard ▼] [Orders] [Customers]     │
│                  [Marketing] [Reports]    👤 Username ▼  │
├──────────────────────────────────────────────────────────┤
│  📊 Today's Statistics                                   │
│  Orders: 45  Revenue: $3,200  Completion: 94%           │
├──────────────────────────────────────────────────────────┤
│  [Recent Orders List]                                    │
│  [Quick Actions]                                         │
└──────────────────────────────────────────────────────────┘
```

---

## 👥 User Roles

### 1. Super Admin (Platform Owner)
**Full system access:**
- Manage all translation centers
- Create and configure centers
- Access all data across platform
- System-wide configuration
- Technical support tasks

**Key Permissions:**
✅ View/edit all centers
✅ Manage platform users
✅ System configuration
✅ Financial reports (all centers)

### 2. Center Owner
**Center-wide management:**
- Manage all branches
- View all center data
- Create/modify staff accounts
- Financial oversight
- Configure center settings

**Key Permissions:**
✅ All branch access
✅ Staff management
✅ Center configuration
✅ Financial reports
✅ Marketing broadcasts (center-wide)

### 3. Branch Manager
**Branch operations:**
- Manage assigned branch
- Assign orders to staff
- View branch analytics
- Create local broadcasts
- Staff coordination

**Key Permissions:**
✅ Branch orders
✅ Branch customers
✅ Branch reports
✅ Staff assignment
✅ Branch broadcasts

### 4. Staff Member
**Order processing:**
- View assigned orders
- Update order status
- Upload completed documents
- Contact customers
- Basic reporting

**Key Permissions:**
✅ View assigned orders
✅ Update order status
✅ Customer communication
✅ Document upload

### 5. Accountant
**Financial management:**
- Payment verification
- Financial reports
- Debt tracking
- Revenue analysis
- Expense recording

**Key Permissions:**
✅ Payment confirmation
✅ Financial reports
✅ Debt management
✅ Revenue tracking

---

## 📊 Dashboard Overview

### Executive Dashboard

**Key Metrics Displayed:**
- **Today's Performance**
  - Total orders (with % change)
  - Revenue (with comparison)
  - Completion rate
  - Pending payments

- **Trend Charts**
  - 7-day revenue trend
  - Order volume by day
  - Service distribution
  - Payment methods

- **Quick Actions**
  - View pending orders
  - Check payment requests
  - Review staff performance
  - Access reports

### Sales Dashboard

**Focus Areas:**
1. **Order Analytics**
   - Volume trends
   - Service popularity
   - Conversion rates
   - Average order value

2. **Customer Insights**
   - New vs returning
   - Top customers
   - Lifetime value
   - Churn analysis

3. **Performance Metrics**
   - Orders per staff
   - Processing time
   - Customer satisfaction
   - Branch comparison

### Finance Dashboard

**Financial Overview:**
1. **Revenue Tracking**
   - Total revenue (period)
   - Payment breakdown
   - Pending collections
   - Cash vs Card ratio

2. **Expense Management**
   - Operational costs
   - Staff salaries
   - Marketing spend
   - Net profit

3. **Debt Management**
   - Outstanding debts
   - Aging analysis
   - Top debtors
   - Collection status

---

## 📦 Order Management

### Creating Manual Orders

**Step-by-Step:**

1. **Navigate to Orders**
   ```
   Dashboard → Orders → Add New Order
   ```

2. **Select Customer**
   - Search existing customer
   - Or create new customer profile
   - Verify contact information

3. **Order Details**
   - Choose service type (Translation, Apostille, etc.)
   - Select source/target languages
   - Pick document type
   - Enter page count

4. **Upload Documents**
   - Click "Upload Files"
   - Select PDF, DOCX, or images
   - System auto-counts pages
   - Confirm or adjust count

5. **Set Pricing**
   - System calculates base price
   - Apply discounts (if authorized)
   - Add copy charges
   - Review total

6. **Payment Method**
   - Cash on delivery
   - Card payment
   - Agency account (credit)
   - Mark as prepaid

7. **Assignment**
   - Auto-assign (by workload)
   - Manually select staff
   - Set priority level
   - Add internal notes

### Order Status Workflow

```
1. Pending
   ↓ (Payment request sent)
2. Payment Pending
   ↓ (Customer uploads receipt)
3. Payment Received
   ↓ (Accountant verifies)
4. Payment Confirmed
   ↓ (Staff begins work)
5. In Progress
   ↓ (Translation completed)
6. Ready
   ↓ (Customer picks up)
7. Completed
```

**Status Actions:**

- **Pending → Payment Pending**
  - Click "Request Payment"
  - System sends Telegram notification
  - Customer receives payment details

- **Payment Received → Payment Confirmed**
  - Open order
  - Click "Verify Payment"
  - Check uploaded receipt
  - Confirm or reject

- **Payment Confirmed → In Progress**
  - Assigned staff receives notification
  - Staff opens order
  - Begins processing

- **In Progress → Ready**
  - Upload completed documents
  - Click "Mark as Ready"
  - Customer notified via Telegram

- **Ready → Completed**
  - Click "Mark as Delivered"
  - Record delivery time
  - Order archived

### Bulk Order Actions

**Available Bulk Operations:**

1. **Status Update**
   ```
   Select orders → Actions → Update Status → Choose status
   ```

2. **Staff Assignment**
   ```
   Select orders → Actions → Assign to Staff → Select staff member
   ```

3. **Export Data**
   ```
   Select orders → Actions → Export → Choose format (Excel/PDF)
   ```

4. **Print Receipts**
   ```
   Select orders → Actions → Print → Batch print
   ```

### Advanced Search & Filtering

**Search Criteria:**
- Order number
- Customer name/phone
- Date range
- Status
- Staff assignment
- Payment status
- Service type
- Document type
- Branch

**Filter Examples:**
```
Status: "Payment Pending" + Date: "This Week"
→ Shows all orders awaiting payment from this week

Staff: "John Doe" + Status: "In Progress"
→ Shows John's current workload

Branch: "Downtown" + Service: "Translation"
→ Shows translation orders at downtown branch
```

---

## 👥 Customer Management

### Customer Profiles

**Information Captured:**
- Full name
- Phone number (with Telegram)
- Email address
- Customer type (Individual/Agency)
- Registration date
- Branch preference
- Language preference

**Order History:**
- Total orders placed
- Total revenue generated
- Average order value
- Last order date
- Payment reliability
- Outstanding balance

### Agency (B2B) Management

**Creating Agency Account:**

1. **Customer Profile**
   ```
   Customers → Select Customer → Edit → Mark as Agency
   ```

2. **Set Credit Limit**
   ```
   Credit Limit: $5,000
   Payment Terms: Net 30 days
   ```

3. **Generate Invitation Link**
   ```
   Click "Generate Agency Link"
   → Copy link
   → Send to agency contact
   ```

4. **Agency Portal Access**
   - Agency clicks invitation link
   - Creates account password
   - Can place orders directly
   - View order history
   - Check balance

**Agency Features:**
- Special pricing tiers
- Credit/debit system
- Bulk order upload
- Order templates
- Dedicated dashboard
- Payment reminders

### Customer Segmentation

**Automatic Segments:**
- **VIP Customers**: $5,000+ lifetime value
- **Regular**: 5+ orders
- **New**: First-time customers
- **At-Risk**: No orders in 90 days
- **Agencies**: B2B accounts

**Marketing Use:**
```
Create Broadcast → Target Segment → Select "VIP Customers"
→ Send exclusive promotion
```

---

## 📢 Marketing & Broadcasts

### Creating Broadcasts

**Step-by-Step Guide:**

1. **Navigate to Marketing**
   ```
   Dashboard → Marketing → Create Broadcast
   ```

2. **Choose Scope**
   - **Platform-wide**: All users (Super Admin only)
   - **Center-wide**: All center customers
   - **Branch-specific**: Single branch only
   - **Custom**: Select specific customers

3. **Compose Message**
   ```
   Title: "Summer Discount!"
   
   Content:
   Hello! 🌞
   
   Get <b>20% OFF</b> on all translation services this week!
   
   Order now: [Order Link]
   
   Valid until: July 31, 2026
   ```
   
   **Formatting Options:**
   - `<b>Bold</b>` → **Bold**
   - `<i>Italic</i>` → *Italic*
   - `<a href="url">Link</a>` → [Link](url)
   - `<code>Code</code>` → `Code`

4. **Add Media (Optional)**
   - Upload image (promo banner)
   - Upload video (service demo)
   - Upload document (price list)

5. **Target Audience**
   - ☑️ Include B2C customers
   - ☑️ Include B2B agencies
   - Filter by: Last active, Order count, etc.

6. **Schedule or Send**
   - **Send Now**: Immediate delivery
   - **Schedule**: Set date/time
   - **Save Draft**: Complete later

### Broadcast Management

**During Sending:**
```
Broadcast Status: Sending...
Progress: 245 / 1,000 (24.5%)
Sent: 240 ✅
Failed: 5 ❌
Estimated completion: 15 minutes
```

**Actions:**
- **Pause**: Temporarily stop
- **Resume**: Continue sending
- **Cancel**: Stop and mark as cancelled

**After Completion:**
```
Broadcast Statistics:
Total Recipients: 1,000
Successfully Sent: 985 (98.5%)
Failed: 10 (1.0%)
Blocked by User: 5 (0.5%)
Opt-outs: 3 users
```

### Best Practices

**Timing:**
- ⏰ Send 10AM - 8PM local time
- 🚫 Avoid late night/early morning
- 📅 Tuesday-Thursday best days
- 🎯 Weekend: leisure content only

**Content:**
- ✅ Clear, concise messages
- ✅ Single call-to-action
- ✅ Personalization when possible
- ✅ Value proposition first
- ❌ Too much text
- ❌ Multiple CTAs
- ❌ All caps
- ❌ Spam keywords

**Frequency:**
- 📊 Max 2-3 per week
- 🎯 Segment messages
- 💡 Provide opt-out option
- 📈 Track engagement

---

## 📈 Reports & Analytics

### Available Reports

#### 1. Financial Report
```
Date Range: [Last Month ▼]

Revenue Summary:
├── Translation Services: $45,230
├── Apostille Services: $12,450
├── Notarization: $8,920
└── Total Revenue: $66,600

Payment Breakdown:
├── Cash: $39,960 (60%)
├── Card: $19,980 (30%)
└── Credit: $6,660 (10%)

Outstanding Debt: $8,450
```

**Export Options:**
- Excel (detailed)
- PDF (summary)
- CSV (raw data)

#### 2. Staff Performance Report
```
Period: This Month

Top Performers:
1. Sarah Johnson - 89 orders, $22,450 revenue
2. Michael Chen - 76 orders, $19,200 revenue
3. Anna Ivanova - 68 orders, $17,340 revenue

Metrics:
├── Avg processing time: 2.3 days
├── Customer satisfaction: 4.8/5
└── Error rate: 0.8%
```

#### 3. Customer Analytics
```
Customer Growth:
New customers this month: 45
Returning customers: 234
Total active: 567

Customer Lifetime Value:
├── Top 10 avg: $3,456
├── Overall avg: $876
└── Agency avg: $12,340

Churn Analysis:
At-risk customers: 23
Lost customers: 12
Retention rate: 94.5%
```

#### 4. Service Analytics
```
Service Distribution:
├── Translation: 65% (1,234 orders)
├── Apostille: 20% (380 orders)
├── Notarization: 10% (190 orders)
└── Other: 5% (95 orders)

Popular Languages:
1. English → Russian: 45%
2. Russian → English: 30%
3. Uzbek → Russian: 15%
4. Other combinations: 10%
```

### Custom Reports

**Creating Custom Reports:**
1. Navigate to Reports → Custom
2. Select data source (Orders, Customers, etc.)
3. Choose date range
4. Select metrics to include
5. Apply filters
6. Generate report
7. Save template for reuse

---

## 🗄️ File Archive Management

### Overview

The automatic file archiving system helps manage storage by compressing old order files and uploading them to Telegram, then cleaning up local storage.

### Configuration

**View Current Settings:**
```bash
python manage.py archive --config
```

**Output:**
```
============================================================
CURRENT ARCHIVE CONFIGURATION
============================================================
MIN_AGE_DAYS                        30
MIN_SIZE_MB                         100
MAX_SIZE_MB                         1500
MAX_ORDERS_PER_BATCH                500
COMPRESSION_LEVEL                   6
DELETE_LOCAL_FILES                  ✓ Enabled
LOCAL_RETENTION_DAYS                0
DRY_RUN_MODE                        ✗ Disabled
ARCHIVE_NAME_PATTERN                Archive_{year}-{month}_{center_name}
SKIP_UNCONFIGURED_CENTERS           ✓ Enabled
============================================================
```

**Modify Settings:**
Create or edit `.env` file in project root:
```env
ARCHIVE_MIN_AGE_DAYS=30          # Days before archiving
ARCHIVE_MIN_SIZE_MB=100          # Min size to trigger
ARCHIVE_MAX_SIZE_MB=1500         # Max archive size
ARCHIVE_COMPRESSION_LEVEL=6      # 0-9 (higher = smaller)
ARCHIVE_DELETE_LOCAL_FILES=True  # Delete after upload
```

### Running Archive Process

**Test Run (Dry Run):**
```bash
# Check what would be archived for specific center
python manage.py archive --run --center 1 --dry-run

# Check all centers
python manage.py archive --run --all --dry-run
```

**Actual Archiving:**
```bash
# Archive specific center
python manage.py archive --run --center 1

# Archive all centers
python manage.py archive --run --all

# Force archiving (ignore size threshold)
python manage.py archive --run --center 1 --force

# Custom age threshold
python manage.py archive --run --all --age-days 60
```

### Archive Process Flow

1. **Selection Phase**
   - Finds orders older than MIN_AGE_DAYS
   - Checks total file size >= MIN_SIZE_MB
   - Verifies center has bot token configured

2. **Compression Phase**
   - Creates ZIP archive with structure:
     ```
     Archive_2026-01_YourCenter/
     ├── Branch_Downtown/
     │   ├── Order_12345/
     │   │   ├── document1.pdf
     │   │   ├── document2.docx
     │   │   └── order_details.json
     │   └── Order_12346/
     │       └── ...
     └── Branch_Uptown/
         └── ...
     ```
   - Splits if archive > MAX_SIZE_MB

3. **Upload Phase**
   - Uploads to center's Telegram channel
   - Records message ID for reference
   - Creates FileArchive database record

4. **Cleanup Phase**
   - Marks orders as archived
   - Deletes local files (if enabled)
   - Updates storage statistics

### Monitoring Archives

**Web Interface:**
```
Dashboard → Settings → File Archives
```

**View Archive List:**
- Archive name and date
- Total orders included
- Total size
- Telegram message link
- Download option

**Archive Details:**
- Order list
- File manifest
- Upload date
- Created by user
- Notes

### Automatic Scheduling

**Setup Cron Job (Linux):**
```bash
# Edit crontab
crontab -e

# Add daily archive job (2 AM)
0 2 * * * cd /path/to/WowDash && /path/to/venv/bin/python manage.py archive --run --all >> /var/log/archive.log 2>&1
```

**Setup Windows Task Scheduler:**
```powershell
# Create scheduled task for daily 2 AM execution
$action = New-ScheduledTaskAction -Execute "C:\path\to\venv\Scripts\python.exe" -Argument "manage.py archive --run --all"
$trigger = New-ScheduledTaskTrigger -Daily -At 2am
Register-ScheduledTask -Action $action -Trigger $trigger -TaskName "WowDash Archive"
```

### Recovery & Restoration

**Accessing Archived Files:**
1. Go to File Archives list
2. Click Telegram link for archive
3. Download ZIP from Telegram
4. Extract locally
5. Files organized by branch/order

**Restoring to System:**
```bash
# If needed, you can manually upload files back
# through order management interface
```

### Presets

**View Available Presets:**
```bash
python manage.py archive --config --preset BALANCED
```

**Preset Options:**
- **AGGRESSIVE**: Archive quickly, save space
  - MIN_AGE_DAYS: 15
  - MIN_SIZE_MB: 50
  - Compression: 9 (maximum)

- **BALANCED**: Default recommended settings
  - MIN_AGE_DAYS: 30
  - MIN_SIZE_MB: 100
  - Compression: 6 (medium)

- **CONSERVATIVE**: Keep files longer
  - MIN_AGE_DAYS: 90
  - MIN_SIZE_MB: 500
  - Compression: 3 (fast)

### Troubleshooting

**Common Issues:**

1. **"No bot token configured"**
   - Solution: Add bot token in center settings

2. **"No company orders channel configured"**
   - Solution: Set company_orders_channel_id in center settings

3. **Upload failed - file too large**
   - Solution: Telegram has 2GB limit per file
   - Archive is auto-split, check MAX_SIZE_MB setting

4. **Archive files not deleting**
   - Solution: Check DELETE_LOCAL_FILES setting
   - Verify file permissions

5. **Too many orders in one archive**
   - Solution: Reduce MAX_ORDERS_PER_BATCH
   - Run more frequent archiving

---

## ⚙️ Organization Settings

### Center Configuration

**Basic Information:**
```
Settings → Center Profile
├── Center Name
├── Legal Entity Name
├── Registration Number
├── Address
├── Contact Phone
├── Email
└── Website
```

**Operational Settings:**
```
Settings → Operations
├── Working Hours (per branch)
├── Service Availability
├── Pricing Rules
├── Payment Methods
└── Document Types
```

### Branch Management

**Adding New Branch:**
1. Navigate to Settings → Branches
2. Click "Add Branch"
3. Fill details:
   ```
   Branch Name: Downtown Office
   Address: 123 Main St
   Phone: +998 90 123 4567
   Working Hours: 9:00 - 18:00
   Manager: Select user
   ```
4. Save and activate

**Branch Settings:**
- Staff assignment
- Service availability
- Pricing variations
- Customer routing
- Operating schedule

### Staff Management

**Adding Staff:**
```
Settings → Staff → Add New
├── Personal Information
│   ├── Full Name
│   ├── Email
│   ├── Phone
│   └── Photo
├── Employment Details
│   ├── Position
│   ├── Branch
│   ├── Start Date
│   └── Salary
└── System Access
    ├── Username
    ├── Password
    └── Role/Permissions
```

**Role Assignment:**
- Select predefined role (Manager, Staff, etc.)
- Or create custom role with specific permissions
- Set branch access scope

**Permission Categories:**
- Orders (view, create, edit, delete)
- Customers (view, edit)
- Reports (view, export)
- Marketing (create, send)
- Finance (view, verify payments)
- Settings (view, edit)

---

## 🤖 Telegram Bot Configuration

### Initial Setup

**1. Create Telegram Bot:**
```
1. Open Telegram, search for @BotFather
2. Send /newbot command
3. Choose bot name: "YourCenter Translation Bot"
4. Choose username: "yourcenter_bot"
5. Copy bot token: 123456789:ABCdefGHIjklMNOpqrsTUVwxyz
```

**2. Configure in WowDash:**
```
Settings → Telegram → Bot Configuration
├── Bot Token: [Paste token]
├── Bot Username: @yourcenter_bot
└── Save
```

**3. Set Webhook:**
```
Settings → Telegram → Set Webhook
Base URL: https://yourdomain.com
→ Click "Set Webhook"
✅ Webhook set successfully
```

**4. Test Bot:**
```
Open Telegram → Search @yourcenter_bot → /start
Should receive welcome message
```

### Channel Configuration

**Creating Order Channel:**
```
1. Create Telegram channel
2. Add bot as administrator
3. Get channel ID:
   - Forward message from channel to @userinfobot
   - Copy channel ID (e.g., -1001234567890)
4. In WowDash:
   Settings → Telegram → Channel Settings
   └── Company Orders Channel: -1001234567890
```

**Channel Uses:**
- Order notifications
- Payment requests
- Status updates
- Archive uploads

### Bot Commands

**Customer Commands:**
```
/start - Start interaction
/help - Show help
/language - Change language
/neworder - Create new order
/myorders - View order history
/cancel - Cancel current operation
```

**Admin Commands:**
```
/stats - View statistics
/broadcast - Send message to all
/settings - Bot settings
```

### Customization

**Bot Messages:**
```
Settings → Telegram → Messages
├── Welcome Message
├── Help Text
├── Order Confirmation
├── Payment Request
└── Status Updates
```

**Bot Behavior:**
```
Settings → Telegram → Behavior
├── Auto-reply timeout
├── File size limits
├── Allowed file types
└── Language detection
```

---

## 💡 Best Practices

### Order Processing

**Efficiency Tips:**
1. **Use Bulk Actions**
   - Process multiple orders simultaneously
   - Save time on repetitive tasks

2. **Set Default Assignments**
   - Configure auto-assignment rules
   - Balance workload automatically

3. **Use Templates**
   - Create order templates for common requests
   - One-click order creation

4. **Quick Filters**
   - Save frequently used filters
   - Access with one click

### Customer Service

**Communication:**
- ✅ Respond within 2 hours
- ✅ Use templates for common questions
- ✅ Proactive status updates
- ✅ Personalize when possible

**Payment Collection:**
- 📧 Send payment request immediately
- 🔔 Follow up after 24 hours
- 💳 Offer multiple payment methods
- 🎁 Early payment discounts

### Marketing

**Campaign Planning:**
```
Week 1: Welcome series (new customers)
Week 2: Service promotion (lapsed customers)
Week 3: Referral incentive (active customers)
Week 4: Feedback request (recent orders)
```

**A/B Testing:**
- Test message timing
- Try different offers
- Vary call-to-action
- Measure and optimize

### Financial Management

**Daily Tasks:**
- [ ] Verify payments received
- [ ] Check pending payment requests
- [ ] Update cash on hand
- [ ] Record expenses

**Weekly Tasks:**
- [ ] Review outstanding debts
- [ ] Send payment reminders
- [ ] Reconcile accounts
- [ ] Generate financial report

**Monthly Tasks:**
- [ ] Close accounting period
- [ ] Generate comprehensive reports
- [ ] Plan next month budget
- [ ] Review pricing strategy

---

## 🔧 Troubleshooting

### Common Issues & Solutions

#### 1. Cannot Login
**Problem:** Invalid credentials
**Solutions:**
- Check caps lock
- Reset password: Click "Forgot Password"
- Contact administrator
- Clear browser cache

#### 2. Orders Not Appearing
**Problem:** Empty order list
**Solutions:**
- Check date filter (expand range)
- Verify branch filter
- Clear all filters
- Check permissions with admin

#### 3. Telegram Bot Not Responding
**Problem:** Bot not sending/receiving messages
**Solutions:**
```
1. Check webhook status:
   Settings → Telegram → Check Webhook
   
2. Verify bot token:
   Test in browser: https://api.telegram.org/bot<TOKEN>/getMe
   
3. Check channel permissions:
   Bot must be channel admin
   
4. Restart webhook:
   Settings → Telegram → Remove & Set Webhook
```

#### 4. Payment Not Confirming
**Problem:** Cannot confirm payment
**Solutions:**
- Verify accountant permission
- Check order status (must be "Payment Received")
- Refresh page
- Check if payment already confirmed

#### 5. Broadcast Not Sending
**Problem:** Broadcast stuck or failing
**Solutions:**
- Check bot token validity
- Verify recipient count > 0
- Check rate limiting settings
- Review error log in broadcast details
- Pause and retry

#### 6. Reports Not Loading
**Problem:** Report generation fails
**Solutions:**
- Reduce date range
- Clear filters
- Try different browser
- Check internet connection
- Contact administrator if persists

#### 7. File Upload Issues
**Problem:** Cannot upload documents
**Solutions:**
- Check file size (max 20MB)
- Verify file type (PDF, DOCX, JPG, PNG)
- Try different browser
- Clear browser cache
- Check storage space

#### 8. Archive Not Running
**Problem:** Archive command fails
**Solutions:**
```bash
# Check configuration
python manage.py archive --config --validate

# Test with dry run
python manage.py archive --run --center 1 --dry-run

# Check error logs
tail -f logs/archive.log
```

### Getting Help

**Internal Support:**
1. Check this user guide
2. Contact your manager
3. Check system notifications
4. Review audit logs

**Technical Support:**
- Email: support@wowdash.com
- Phone: +998 90 123 4567
- Telegram: @wowdash_support
- Office hours: 9:00 - 18:00 (UTC+5)

**Emergency Support:**
- Critical issues only
- 24/7 hotline: +998 90 999 9999
- Response time: < 30 minutes

---

## 📞 Contact & Support

### Documentation

- **Full Documentation**: See [README.md](README.md)
- **Features Overview**: See [FEATURES_SUMMARY.md](FEATURES_SUMMARY.md)
- **API Documentation**: See [API_GUIDE.md](API_GUIDE.md)
- **Deployment Guide**: See [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)

### Training Resources

- **Video Tutorials**: Available in dashboard
- **Webinars**: Monthly training sessions
- **Knowledge Base**: help.wowdash.com
- **FAQ**: Frequently asked questions section

### Community

- **User Forum**: community.wowdash.com
- **Telegram Group**: @wowdash_users
- **Newsletter**: Monthly tips and updates

---

**Last Updated**: January 23, 2026  
**Version**: 2.0  
**Document Author**: WowDash Team

For questions or suggestions about this guide, contact: docs@wowdash.com
