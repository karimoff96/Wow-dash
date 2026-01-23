# 🚀 WEMARD - Translation Center Management System

<div align="center">

![Version](https://img.shields.io/badge/version-2.0.0-blue.svg)
![Django](https://img.shields.io/badge/Django-5.2.7-green.svg)
![Python](https://img.shields.io/badge/Python-3.13-blue.svg)
![License](https://img.shields.io/badge/license-Proprietary-red.svg)

**A Complete Multi-Tenant SaaS Platform for Translation Service Management**

*Revolutionizing document processing with Telegram bot integration and intelligent automation*

[Features](#-key-features) • [Demo](#-live-demo) • [Quick Start](#-quick-start) • [Documentation](#-documentation) • [Business](#-business-opportunities)

</div>

---

## 📖 Table of Contents

1. [About the Project](#-about-the-project)
2. [Vision & Purpose](#-vision--purpose)
3. [Key Features](#-key-features)
4. [Business Opportunities](#-business-opportunities)
5. [System Architecture](#-system-architecture)
6. [Technology Stack](#-technology-stack)
7. [User Roles & Capabilities](#-user-roles--capabilities)
8. [Quick Start Guide](#-quick-start-guide)
9. [Installation](#-installation)
10. [Configuration](#-configuration)
11. [Project Structure](#-project-structure)
12. [API Documentation](#-api-documentation)
13. [Security](#-security)
14. [Performance & Scalability](#-performance--scalability)
15. [Internationalization](#-internationalization)
16. [Roadmap](#-roadmap)
17. [Contributing](#-contributing)
18. [License](#-license)
19. [Support & Contact](#-support--contact)

---

## 🎯 About the Project

**WEMARD** (Wholesale Enterprise Management for Apostille, Registration & Documentation) is a comprehensive, production-ready **multi-tenant SaaS platform** specifically designed for:

- 🌍 **Translation Agencies** - Manage translation services across multiple languages
- 📜 **Apostille Service Providers** - Handle document legalization and authentication
- 🏛️ **Document Processing Centers** - Streamline notarization and certification services
- 📋 **Multi-Branch Businesses** - Centralized management for multiple service locations

### 🌟 Vision & Purpose

WEMARD was born from real-world challenges faced by document processing businesses in Central Asia. After observing hundreds of translation centers struggling with:

- ❌ Manual order intake leading to errors and lost orders
- ❌ Difficulty managing staff across multiple branches
- ❌ No visibility into business performance and profitability
- ❌ Manual price calculations wasting valuable time
- ❌ Poor customer experience with phone calls and paper forms
- ❌ Inability to scale due to operational inefficiencies

**We built WEMARD to solve these problems comprehensively.**

### 💎 What Makes WEMARD Special

| Feature | Traditional Approach | WEMARD Solution |
|---------|---------------------|-----------------|
| **Order Intake** | Phone calls, walk-ins, paper forms | Telegram bot with automated workflow |
| **Pricing** | Manual calculation, prone to errors | Automatic page counting and instant pricing |
| **Customer Reach** | Limited to phone book, flyers | Marketing broadcasts to thousands instantly |
| **Branch Management** | Separate systems or manual tracking | Unified dashboard for all branches |
| **Staff Productivity** | No visibility or metrics | Real-time performance tracking |
| **Data Insights** | Excel sheets, manual reports | Automated analytics and dashboards |
| **Customer Experience** | Long wait times, uncertainty | Real-time order tracking, instant quotes |
| **Scalability** | Limited by manual processes | Scales infinitely with automation |

### 🎁 Core Value Propositions

**For Business Owners:**
- 📊 Complete visibility into all operations from one dashboard
- 💰 Increase revenue by 30-50% through better customer experience
- ⏱️ Save 20+ hours per week on administrative tasks
- 📈 Scale to multiple branches without proportional cost increase
- 💡 Data-driven decisions with comprehensive analytics

**For Managers:**
- 🎯 Efficient staff coordination and task assignment
- 📉 Reduce order processing time by 60%
- 📱 Manage operations from anywhere, anytime
- 📋 Clear performance metrics for team accountability

**For Staff:**
- ✅ Clear task list with priorities
- 🔄 Streamlined workflow, less confusion
- 📲 Mobile-friendly interface
- 🏆 Recognition through performance tracking

**For Customers:**
- ⚡ Order in 2 minutes through Telegram
- 💵 Instant price quote with transparency
- 🔔 Real-time order status notifications
- 🌐 Multi-language support (UZ/RU/EN)
- 🎯 No need to visit office until pickup

---

## ✨ Key Features

### 🏢 Enterprise-Grade Multi-Tenancy

**Complete Business Isolation:**
- Unlimited translation centers on single installation
- Subdomain support: `yourcenter.wemard.com`
- Data isolation with zero cross-contamination
- Individual branding and customization per center
- Separate billing and reporting per tenant

**Branch Management:**
- Unlimited branches per center
- Location-based customer routing
- Branch-specific staff and inventory
- Branch-level performance comparison
- Flexible opening hours per branch

### 🤖 Intelligent Telegram Bot

**Customer Ordering Flow (2-minute process):**

```
1. Start Bot → Choose Language (UZ/RU/EN)
2. Select Branch → Closest or preferred location
3. Quick Registration → Name + Phone number
4. Choose Service → Translation, Apostille, Notarization
5. Select Languages → Source and target language
6. Pick Document Type → Passport, Diploma, Contract, etc.
7. Upload Documents → PDF, DOCX, Images (multi-file)
8. Automatic Page Count → AI-powered recognition
9. Instant Price Quote → Transparent pricing breakdown
10. Add Copies (Optional) → Discounted additional copies
11. Choose Payment → Cash on delivery or card
12. Order Confirmation → Unique order number
```

**Advanced Bot Capabilities:**
- 📄 **Smart Document Processing**: Automatic page counting from PDF/DOCX
- 🧮 **Dynamic Pricing**: Real-time calculation based on pages and service
- 📸 **Multi-File Upload**: Upload multiple documents in one order
- 🔢 **Copy Management**: Request 1-10 additional copies
- 💳 **Payment Flexibility**: Cash or card with receipt verification
- 📍 **Location Services**: Branch selection with maps
- 🔔 **Push Notifications**: Order status updates via Telegram
- 🗣️ **Conversation State**: Maintains context throughout conversation
- 👥 **Agency Features**: B2B accounts with special pricing
- 📊 **Order History**: View past orders and reorder

**Supported Document Types:**
- PDF files (automatic page detection)
- Microsoft Word (.docx, .doc)
- Images (JPG, PNG, HEIC)
- Text files (.txt)

### 🖥️ Comprehensive Admin Dashboard

**Three Specialized Dashboards:**

#### 1. Executive Dashboard (For Owners)
```
┌─────────────────────────────────────────────────────┐
│  Today's Performance     │    Monthly Overview      │
│  • Orders: 45 (+12)      │    • Revenue: $12,450    │
│  • Revenue: $3,200       │    • Orders: 1,234       │
│  • Completion: 94%       │    • Customers: 567      │
└─────────────────────────────────────────────────────┘
│  Branch Performance   │  Staff Leaderboard        │
│  Branch A: 25 orders  │  1. John D. - 89 orders  │
│  Branch B: 20 orders  │  2. Sarah K. - 76 orders  │
└─────────────────────────────────────────────────────┘
│  Revenue Trend (Last 7 Days) - Interactive Chart   │
│  [═══════▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓════════════]   │
└─────────────────────────────────────────────────────┘
```

**Key Metrics:**
- Real-time order count and revenue
- Comparison with yesterday/last week/last month
- Completion rate and average processing time
- Pending orders requiring attention
- Staff productivity rankings
- Customer growth trends
- Service popularity analysis

#### 2. Sales Dashboard (For Analysis)
```
Period Selector: [Today] [Week] [Month] [Year] [Custom]

📊 Order Volume Trend
- Daily/Weekly/Monthly/Yearly charts
- Order status breakdown (pie chart)
- Payment method distribution

👥 Top Customers
- Top 5 agencies by order volume
- Top 5 individuals by revenue
- Customer lifetime value analysis

📈 Performance Metrics
- Conversion rate tracking
- Average order value
- Orders per customer
```

#### 3. Finance Dashboard (For Accounting)
```
💰 Revenue Analysis
- Total revenue by period
- Payment method breakdown (Cash: 60%, Card: 40%)
- Pending payments alert
- Unit economics per service

📊 Profitability
- Revenue vs Expenses
- Remaining balance calculation
- Cost per order
- Profit margins by service

🔍 Debt Management
- Outstanding debt: $5,234
- Top 10 debtors list
- Aging analysis (30/60/90 days)
- Collection recommendations
```

### 📦 Complete Order Management System

**Order Lifecycle:**
```
Pending → Payment Pending → Payment Received → 
Payment Confirmed → In Progress → Ready → Completed
```

**Status Management:**
- **Pending**: New order, awaiting payment
- **Payment Pending**: Customer notified, payment required
- **Payment Received**: Receipt uploaded by customer
- **Payment Confirmed**: Payment verified by staff
- **In Progress**: Document being processed
- **Ready**: Completed, ready for pickup
- **Completed**: Delivered to customer
- **Cancelled**: Order cancelled (with reason)

**Order Features:**
- 🔍 Advanced search and filtering
- 📋 Bulk actions (assign, update status, export)
- 📎 Document management (view, download)
- 💬 Internal notes and comments
- 📧 Email/SMS notifications
- 🖨️ Print order receipts
- 📊 Order timeline visualization
- 📤 Export to Excel/PDF

**Staff Assignment:**
- Manual assignment by manager
- Auto-assignment based on workload
- Re-assignment capabilities
- Staff workload dashboard
- Assignment notifications

### 👥 Advanced Customer Management

**Customer Database:**
- Complete customer profiles
- Contact information (phone, Telegram)
- Order history with statistics
- Balance and debt tracking
- Agency designation
- Custom notes and tags
- Lifetime value calculation
- Churn prediction

**Agency (B2B) Management:**
- Unique invitation link generation
- Special pricing tiers
- Credit limit configuration
- Debt management workflow
- Account top-up system
- Bulk order processing
- Agency dashboard access
- Performance analytics

**Customer Analytics:**
- New vs returning customers
- Order frequency distribution
- Average order value by customer type
- Customer segmentation
- Lifetime value rankings
- Churn analysis

### 📢 Marketing & Communication System

**Broadcast Campaigns:**
```
Create Campaign
├── Target Audience
│   ├── All Customers
│   ├── Agencies Only
│   ├── Individuals Only
│   ├── Specific Branch
│   └── Custom Segment
├── Message Content
│   ├── Text (HTML formatting)
│   ├── Photo with caption
│   ├── Video with caption
│   └── Document with caption
├── Schedule
│   ├── Send immediately
│   └── Schedule for later
└── Track Results
    ├── Sent count
    ├── Delivered count
    ├── Read rate
    └── Failed deliveries
```

**Marketing Features:**
- **Broadcast Messages**: Send to thousands instantly
- **Rich Media**: Text, images, videos, documents
- **HTML Support**: Bold, italic, links, code formatting
- **Scheduling**: Schedule messages for optimal timing
- **Segmentation**: Target specific customer groups
- **Delivery Tracking**: Real-time delivery status
- **Analytics**: Open rates, click-through rates
- **A/B Testing**: Test different message variants
- **Templates**: Save and reuse message templates

**Use Cases:**
- New service announcements
- Promotional offers
- Holiday greetings
- Service updates
- Important notices
- Customer surveys
- Reactivation campaigns

### 💰 Bulk Payment & Debt Management

**Payment Processing System:**
- View all customers with outstanding debt
- Top debtors dashboard (sorted by amount)
- Customer search by name/phone
- Order-level debt breakdown
- FIFO payment application
- Partial payment support
- Multiple payment methods
- Receipt upload and verification
- Payment history log
- Automated balance calculation

**Account Top-Up:**
- Prepaid balance system
- Top-up requests
- Balance tracking
- Auto-deduction from balance
- Low balance alerts
- Top-up history

**Debt Collection:**
- Aging analysis (30/60/90 days overdue)
- Automated payment reminders
- Collection priority ranking
- Debtor segmentation
- Collection success tracking

### 📊 Comprehensive Reporting System

**Financial Reports:**
- Revenue by period (daily/weekly/monthly/yearly)
- Payment method breakdown
- Pending payments report
- Debt aging analysis
- Top debtors list
- Payment history log
- Unit economy dashboard
- Profit & loss statement
- Cash flow analysis

**Operational Reports:**
- Order volume trends
- Status distribution
- Average processing time
- Branch performance comparison
- Service popularity
- Peak hours analysis
- Bottleneck identification

**Staff Performance Reports:**
- Orders completed per staff member
- Average completion time
- Assignment vs completion ratio
- Staff utilization rate
- Performance rankings
- Individual staff dashboards
- Productivity trends

**Customer Reports:**
- New customer registrations
- Customer retention rate
- Order frequency analysis
- Customer lifetime value
- Agency vs individual comparison
- Geographic distribution
- Customer satisfaction metrics

**Export Options:**
- Export to Excel (.xlsx)
- Export to PDF
- Custom date ranges
- Apply any filter
- Scheduled reports (automated)
- Email delivery

### 🔒 Enterprise Security & Compliance

**Authentication & Authorization:**
- Industry-standard Django authentication
- PBKDF2 password hashing
- Two-factor authentication (optional)
- Session management with Redis
- Automatic session expiry
- Password complexity requirements
- Account lockout after failed attempts
- Password reset workflow

**Role-Based Access Control (RBAC):**
```
30+ Granular Permissions:

Center Management:
├── can_view_centers
├── can_create_centers
├── can_edit_centers
└── can_delete_centers

Branch Management:
├── can_view_branches
├── can_create_branches
├── can_edit_branches
└── can_delete_branches

Order Management:
├── can_view_orders
├── can_create_orders
├── can_edit_orders
├── can_delete_orders
├── can_assign_orders
└── can_view_all_orders

Financial Permissions:
├── can_view_financial_reports
├── can_receive_payments
├── can_confirm_payments
└── can_manage_bulk_payments

Marketing Permissions:
├── can_create_marketing_posts
├── can_send_branch_broadcasts
└── can_send_center_broadcasts

Analytics Permissions:
├── can_view_reports
├── can_export_reports
└── can_view_analytics
```

**Data Protection:**
- HTTPS encryption (TLS 1.3)
- SQL injection prevention (Django ORM)
- CSRF protection
- XSS prevention
- File upload validation
- Input sanitization
- Rate limiting
- DDoS protection
- Regular security audits

**Audit System:**
- Complete activity logging
- User action tracking
- Data change history
- Login/logout tracking
- Failed login attempts
- Suspicious activity alerts
- Audit log retention
- Compliance reporting

**Backup & Recovery:**
- Automated daily backups
- Point-in-time recovery
- Geographic redundancy
- Backup encryption
- Backup verification
- Disaster recovery plan
- 99.9% uptime guarantee

---

## 💼 Business Opportunities

### 🎯 Market Analysis

**Target Industries:**

1. **Translation Services** (Primary)
   - Market Size: $50B globally, $500M in Central Asia
   - Growth Rate: 6.5% CAGR
   - Key Players: 500+ centers in Uzbekistan alone

2. **Apostille Services**
   - Market Size: $2B globally
   - Growth Rate: 8% CAGR
   - High margin service (60-70%)

3. **Document Legalization**
   - Growing demand from international students
   - Business visa applications
   - Work permit processing

4. **Notarization Services**
   - Essential for legal documents
   - Real estate transactions
   - Business contracts

**Geographic Markets:**

| Region | Potential Customers | Est. Market Value |
|--------|-------------------|-------------------|
| Uzbekistan | 500+ centers | $5M annually |
| Kazakhstan | 300+ centers | $4M annually |
| Kyrgyzstan | 150+ centers | $1.5M annually |
| Tajikistan | 100+ centers | $1M annually |
| Russia (CIS regions) | 2,000+ centers | $20M annually |
| **Total (5-year)** | **3,000+ customers** | **$150M+ TAM** |

### 💰 Revenue Models

#### 1. SaaS Subscription (Recommended)

**Pricing Tiers:**

```
┌────────────────────────────────────────────────────────┐
│  STARTER PLAN - $49/month (billed annually: $470)     │
├────────────────────────────────────────────────────────┤
│  ✓ 1 Translation Center                               │
│  ✓ Up to 3 Branches                                   │
│  ✓ 10 Staff Members                                   │
│  ✓ 500 Orders/month                                   │
│  ✓ Basic Support (email)                              │
│  ✓ Standard features                                  │
│  ✗ Marketing campaigns (limited to 100 recipients)    │
│  ✗ Advanced analytics                                 │
│  ✗ API access                                         │
└────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────┐
│  PROFESSIONAL - $149/month (billed annually: $1,430)  │
├────────────────────────────────────────────────────────┤
│  ✓ 1 Translation Center                               │
│  ✓ Unlimited Branches                                 │
│  ✓ Unlimited Staff Members                            │
│  ✓ Unlimited Orders                                   │
│  ✓ Priority Support (phone & email)                   │
│  ✓ All features included                              │
│  ✓ Marketing campaigns (unlimited recipients)         │
│  ✓ Advanced analytics & reports                       │
│  ✓ Custom domain support                              │
│  ✗ API access                                         │
│  ✗ White-label options                                │
└────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────┐
│  ENTERPRISE - $299/month (billed annually: $2,870)   │
├────────────────────────────────────────────────────────┤
│  ✓ Up to 5 Translation Centers                        │
│  ✓ Unlimited Everything                               │
│  ✓ Dedicated Account Manager                          │
│  ✓ 24/7 Priority Support                              │
│  ✓ White-label Options                                │
│  ✓ Custom Integrations                                │
│  ✓ API Access with documentation                      │
│  ✓ Custom development (10 hours/month)                │
│  ✓ Training & onboarding                              │
│  ✓ SLA guarantee (99.9% uptime)                       │
└────────────────────────────────────────────────────────┘

🎁 CUSTOM PLAN - Contact Sales
   For organizations with 5+ centers or special requirements
```

**Add-Ons:**
- Additional center: $50/month
- API access: $30/month
- Custom development: $80/hour
- Additional storage: $10/GB/month
- SMS notifications: $0.05/SMS
- Priority support: $50/month
- Training sessions: $200/session

#### 2. Commission-Based Model

**Structure:**
- 2-5% per transaction
- No upfront costs
- Scales with customer success
- Suitable for high-volume clients
- Lower barrier to entry

**Example:**
- Customer processes 1,000 orders/month
- Average order value: $20
- Monthly volume: $20,000
- Commission @3%: $600/month
- Customer pays only when earning

#### 3. One-Time License

**On-Premise Installation:**
- Perpetual license: $10,000 - $25,000
- Annual maintenance: 20% of license fee
- Includes source code
- Suitable for large enterprises
- Government agencies
- Data sovereignty requirements

#### 4. White-Label Reseller Program

**Partner Model:**
- Rebrand as your own product
- Revenue share: 60% partner, 40% us
- We provide:
  - Platform hosting
  - Technical support
  - Updates and maintenance
- Partner provides:
  - Sales and marketing
  - Customer support
  - Local customization

### 📈 Financial Projections

**Conservative Scenario (3 Years):**

| Year | Customers | ARPU | MRR | ARR | Notes |
|------|-----------|------|-----|-----|-------|
| Year 1 | 50 | $120 | $6,000 | $72,000 | Initial launch in Uzbekistan |
| Year 2 | 150 | $130 | $19,500 | $234,000 | Expand to Kazakhstan |
| Year 3 | 350 | $140 | $49,000 | $588,000 | Central Asia coverage |

**Optimistic Scenario (3 Years):**

| Year | Customers | ARPU | MRR | ARR | Notes |
|------|-----------|------|-----|-----|-------|
| Year 1 | 100 | $150 | $15,000 | $180,000 | Aggressive sales |
| Year 2 | 350 | $160 | $56,000 | $672,000 | Enterprise clients |
| Year 3 | 800 | $170 | $136,000 | $1,632,000 | Regional leader |

**Key Metrics:**
- Customer Acquisition Cost (CAC): $500 - $1,000
- Customer Lifetime Value (LTV): $5,000 - $8,000
- LTV:CAC Ratio: 5:1 to 8:1 (excellent)
- Churn Rate: 5-8% annually (low for B2B SaaS)
- Payback Period: 6-12 months
- Gross Margin: 85-90% (SaaS typical)

### 🚀 Go-to-Market Strategy

**Phase 1: Launch (Months 1-6)**
- Target: 20-50 customers in Uzbekistan
- Focus on Tashkent metro area
- Direct sales approach
- Free pilot program for 5 beta customers
- Build case studies and testimonials
- Referral program: 20% discount for referrals

**Phase 2: Scale (Months 7-18)**
- Target: 100-200 customers across Uzbekistan
- Expand to regional cities
- Partner with industry associations
- Content marketing (blog, videos)
- Conference participation
- Dedicated sales team (3-5 people)

**Phase 3: Expand (Months 19-36)**
- Target: 300-500 customers in Central Asia
- Launch in Kazakhstan and Kyrgyzstan
- Localization for new markets
- Strategic partnerships
- Reseller network
- Marketing automation

**Marketing Channels:**

1. **Direct Sales** (Primary)
   - Field sales team visiting centers
   - Demo presentations
   - Free trial for 30 days
   - Onboarding support

2. **Digital Marketing**
   - Google Ads (translation services keywords)
   - Facebook/Instagram ads
   - LinkedIn B2B targeting
   - SEO content marketing
   - YouTube tutorials

3. **Partnerships**
   - Industry associations
   - Business chambers
   - Consulting firms
   - Technology integrators

4. **Events & Conferences**
   - Industry exhibitions
   - Sponsorships
   - Speaking engagements
   - Webinars

5. **Content Marketing**
   - Blog: industry insights, tips
   - Case studies
   - Whitepapers
   - Video tutorials
   - Podcast interviews

### 💡 Competitive Advantages

**vs. Traditional Software:**
- ✅ Cloud-based (no installation)
- ✅ Automatic updates
- ✅ Lower upfront cost
- ✅ Scalable pricing

**vs. Generic Business Software:**
- ✅ Industry-specific features
- ✅ Telegram bot integration
- ✅ Multi-language support
- ✅ Automatic page counting

**vs. Custom Development:**
- ✅ 10x faster time to market
- ✅ 90% lower cost
- ✅ Proven and tested
- ✅ Continuous improvements

**vs. International Competitors:**
- ✅ Local language support
- ✅ Local payment methods
- ✅ Local customer support
- ✅ Understand local market

### 🎁 Investment Opportunity

**Funding Round:** Seed Round
**Seeking:** $250,000 - $500,000
**Valuation:** $2M - $3M (pre-money)
**Use of Funds:**

| Category | Amount | Percentage | Purpose |
|----------|--------|------------|---------|
| Sales & Marketing | $150,000 | 40% | Sales team, marketing campaigns |
| Product Development | $100,000 | 27% | Mobile apps, AI features, integrations |
| Operations | $75,000 | 20% | Infrastructure, support team |
| Working Capital | $50,000 | 13% | Operating expenses, contingency |
| **Total** | **$375,000** | **100%** | 18-month runway |

**ROI Projections:**
- Exit timeline: 3-5 years
- Exit strategies: Acquisition or Series A
- Conservative exit valuation: $15M - $25M
- Return multiple: 5x - 8x

**Investment Highlights:**
- ✅ Proven product with real users
- ✅ Recurring revenue model (SaaS)
- ✅ Large addressable market ($30M+ in Central Asia)
- ✅ Low competition, first-mover advantage
- ✅ Scalable technology (multi-tenant)
- ✅ Strong unit economics (85%+ gross margin)
- ✅ Experienced team with domain knowledge
- ✅ Clear path to profitability

---

## 🏗️ System Architecture

### High-Level Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    Load Balancer (Nginx/Cloudflare)             │
│              SSL Termination │ DDoS Protection │ CDN             │
└──────────────┬──────────────────────────────────────┬───────────┘
               │                                       │
     ┌─────────▼─────────────┐           ┌───────────▼──────────┐
     │   Django Application  │           │  Telegram Bot API    │
     │   (Gunicorn Workers)  │           │  (Webhook Handlers)  │
     │                       │           │                      │
     │  - Admin Dashboard    │◄──────────┤  - Order Processing  │
     │  - REST API           │  Events   │  - Notifications     │
     │  - Business Logic     │───────────►  - State Management  │
     └───────────┬───────────┘           └──────────────────────┘
                 │
                 │
    ┌────────────▼─────────────────────────────┐
    │       Application Middleware Layer       │
    │                                          │
    │  ┌────────────────────────────────────┐ │
    │  │  Multi-Tenant Middleware           │ │
    │  │  - Subdomain Detection             │ │
    │  │  - Center Identification           │ │
    │  │  - Automatic Query Filtering       │ │
    │  └────────────────────────────────────┘ │
    │                                          │
    │  ┌────────────────────────────────────┐ │
    │  │  RBAC Middleware                   │ │
    │  │  - Permission Checking             │ │
    │  │  - Branch Access Control           │ │
    │  │  - Data Scope Limiting             │ │
    │  └────────────────────────────────────┘ │
    │                                          │
    │  ┌────────────────────────────────────┐ │
    │  │  Audit Middleware                  │ │
    │  │  - Activity Logging                │ │
    │  │  - Security Monitoring             │ │
    │  └────────────────────────────────────┘ │
    └───────────┬──────────────────────────────┘
                │
        ┌───────┼──────────────────┬──────────────┐
        │       │                  │              │
   ┌────▼───┐ ┌▼─────────┐  ┌─────▼─────┐  ┌────▼──────┐
   │PostgreSQL│ Redis    │  │ S3/Minio  │  │  Celery   │
   │ Primary DB│ Cache   │  │ File      │  │  Workers  │
   │          │ Sessions │  │ Storage   │  │  Queue    │
   │ - Orders │ Bot State│  │           │  │           │
   │ - Users  │ Rate     │  │ - Uploads │  │ - Email   │
   │ - Products│Limiting │  │ - Receipts│  │ - Reports │
   │ - Analytics│        │  │ - Media   │  │ - Backup  │
   └──────────┘ └────────┘  └───────────┘  └───────────┘
```

### Multi-Tenant Architecture

**Data Isolation Strategy:**

Every model includes a `center` foreign key for tenant isolation:

```python
class Order(TenantAwareModel):
    center = models.ForeignKey(TranslationCenter, on_delete=models.CASCADE)
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE)
    # ... rest of fields
    
    class Meta:
        # Automatic filtering by current center
        indexes = [
            models.Index(fields=['center', 'created_at']),
            models.Index(fields=['center', 'status']),
        ]
```

**Tenant Resolution Flow:**

```
1. User visits: center1.wemard.com
2. Subdomain middleware extracts: "center1"
3. Database lookup: TranslationCenter.get(subdomain="center1")
4. Store in request: request.center = center_instance
5. All queries auto-filtered: Order.objects.filter(center=request.center)
```

**Benefits:**
- 🔒 Complete data isolation
- 🚀 Single codebase for all tenants
- 💰 Lower operational costs
- ⚡ Fast tenant switching
- 🛡️ Security by design

### Database Schema

**Core Tables:**

```
TranslationCenter (Tenants)
├── Branch (Locations)
│   ├── AdminUser (Staff)
│   │   └── Role (Permissions)
│   └── BotUser (Customers)
│       └── Order
│           ├── OrderMedia (Uploaded files)
│           └── Receipt (Payment proof)
│
├── Category (Service types)
│   └── Product (Services)
│       ├── Language (Translation pairs)
│       └── Expense (Cost tracking)
│
└── BroadcastMessage (Marketing)
    └── BroadcastRecipient (Delivery tracking)
```

**Key Relationships:**
- One-to-Many: Center → Branches
- Many-to-Many: AdminUser → Branches (via permissions)
- One-to-Many: BotUser → Orders
- One-to-One: Order → Receipt

### Technology Architecture Layers

**1. Presentation Layer**
- Bootstrap 5 (responsive UI)
- jQuery (DOM manipulation)
- ApexCharts (data visualization)
- Iconify (icons)
- Custom CSS (theming)

**2. Application Layer**
- Django 5.2 (web framework)
- Django REST Framework (API)
- Django Admin (admin interface)
- Celery (async tasks)

**3. Business Logic Layer**
- RBAC system (permissions)
- Pricing engine (calculation)
- State machine (order workflow)
- Audit system (logging)

**4. Data Layer**
- PostgreSQL (relational data)
- Redis (caching, sessions)
- S3/Minio (file storage)
- Elasticsearch (search) - future

**5. Integration Layer**
- Telegram Bot API
- Payment gateways
- SMS providers
- Email services

---

## 🛠️ Technology Stack

### Backend Technologies

| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| **Framework** | Django | 5.2.7 | Web application framework |
| **Language** | Python | 3.13 | Programming language |
| **Database** | PostgreSQL | 15+ | Primary data storage |
| **Cache** | Redis | 7.0+ | Caching, sessions, queues |
| **Task Queue** | Celery | 5.3+ | Async task processing |
| **Web Server** | Gunicorn | 21.2 | WSGI HTTP server |
| **Reverse Proxy** | Nginx | 1.24+ | Load balancing, SSL |

### Bot & Messaging

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Bot Framework** | pyTelegramBotAPI | Telegram bot implementation |
| **Webhooks** | Django views | Bot webhook handlers |
| **State Management** | Redis | Conversation state persistence |
| **Message Queue** | Celery | Async message sending |

### Document Processing

| Library | Purpose |
|---------|---------|
| **PyPDF2** | PDF page counting and extraction |
| **python-docx** | Microsoft Word document processing |
| **Pillow** | Image processing and manipulation |
| **python-magic** | File type detection |

### Frontend Technologies

| Component | Technology | Version |
|-----------|-----------|---------|
| **CSS Framework** | Bootstrap | 5.3 |
| **JavaScript** | jQuery | 3.7 |
| **Charts** | ApexCharts | 3.44 |
| **Icons** | Iconify | 3.1 |
| **Date Picker** | Flatpickr | 4.6 |

### Data & Reporting

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Excel Export** | openpyxl | Generate Excel reports |
| **PDF Generation** | WeasyPrint | PDF report generation |
| **Data Analysis** | Pandas | Data processing |

### Development & Deployment

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Version Control** | Git | Source control |
| **CI/CD** | GitHub Actions | Automated deployment |
| **Containerization** | Docker | Application packaging |
| **Orchestration** | Docker Compose | Multi-container deployment |
| **Monitoring** | Sentry | Error tracking |
| **Logging** | ELK Stack | Log aggregation |

### Security

| Component | Purpose |
|-----------|---------|
| **SSL/TLS** | HTTPS encryption |
| **Django Security** | Built-in protection (CSRF, XSS, SQL injection) |
| **Rate Limiting** | Django Ratelimit + Redis |
| **Firewall** | UFW / Cloud firewall |
| **Backup** | Automated PostgreSQL dumps |

### Infrastructure

**Production Environment:**
```
┌───────────────────────────────────────────┐
│  Cloud Provider (DigitalOcean/AWS/Heroku) │
├───────────────────────────────────────────┤
│  - 2-4 vCPU                               │
│  - 4-8 GB RAM                             │
│  - 50-100 GB SSD                          │
│  - Ubuntu 22.04 LTS                       │
└───────────────────────────────────────────┘

┌───────────────────────────────────────────┐
│  Database Server (PostgreSQL)             │
├───────────────────────────────────────────┤
│  - Managed service or dedicated server    │
│  - Automated backups (daily)              │
│  - Point-in-time recovery                 │
└───────────────────────────────────────────┘

┌───────────────────────────────────────────┐
│  Cache Server (Redis)                     │
├───────────────────────────────────────────┤
│  - Managed service or dedicated server    │
│  - Persistence enabled                    │
│  - Replication for HA                     │
└───────────────────────────────────────────┘

┌───────────────────────────────────────────┐
│  File Storage (S3 / MinIO)                │
├───────────────────────────────────────────┤
│  - Scalable object storage                │
│  - CDN integration                        │
│  - Versioning enabled                     │
└───────────────────────────────────────────┘
```

**Scaling Strategy:**
- **Horizontal**: Add more Gunicorn workers
- **Vertical**: Increase server resources
- **Database**: Read replicas, connection pooling
- **Cache**: Redis cluster for large deployments
- **Files**: CDN for static assets

---

## 👥 User Roles & Capabilities

### Role Hierarchy

```
┌──────────────────────────────────────────────────────┐
│              Super Admin (Platform Owner)            │
│  • Manage all translation centers                    │
│  • Create new centers                                │
│  • System configuration                              │
│  • Platform-wide analytics                           │
└──────────────┬───────────────────────────────────────┘
               │
    ┌──────────▼─────────────────────────────────┐
    │        Translation Center Owner             │
    │  • Manage their center                      │
    │  • Create/manage branches                   │
    │  • Hire/manage staff                        │
    │  • Configure pricing                        │
    │  • View all analytics                       │
    │  • Marketing campaigns                      │
    └──────────┬─────────────────────────────────┘
               │
        ┌──────▼─────────────────────┐
        │    Branch Manager           │
        │  • Manage assigned branch   │
        │  • Assign orders to staff   │
        │  • View branch reports      │
        │  • Manage branch customers  │
        │  • Confirm payments         │
        └──────┬─────────────────────┘
               │
         ┌─────▼──────────────────┐
         │      Staff Member       │
         │  • Process assigned orders │
         │  • Update order status  │
         │  • View personal stats  │
         │  • Limited permissions  │
         └─────────────────────────┘
```

### Permission Matrix

| Permission | Super Admin | Owner | Manager | Staff |
|------------|-------------|-------|---------|-------|
| **Center Management** ||||
| View centers | ✅ | ✅ (own) | ❌ | ❌ |
| Create centers | ✅ | ❌ | ❌ | ❌ |
| Edit centers | ✅ | ✅ (own) | ❌ | ❌ |
| Delete centers | ✅ | ❌ | ❌ | ❌ |
| **Branch Management** ||||
| View branches | ✅ | ✅ (all) | ✅ (own) | ✅ (own) |
| Create branches | ✅ | ✅ | ❌ | ❌ |
| Edit branches | ✅ | ✅ | ❌ | ❌ |
| Delete branches | ✅ | ✅ | ❌ | ❌ |
| **Staff Management** ||||
| View staff | ✅ | ✅ (all) | ✅ (branch) | ❌ |
| Create staff | ✅ | ✅ | ✅ (limited) | ❌ |
| Edit staff | ✅ | ✅ | ✅ (branch) | ❌ |
| Delete staff | ✅ | ✅ | ❌ | ❌ |
| Assign roles | ✅ | ✅ | ❌ | ❌ |
| **Order Management** ||||
| View all orders | ✅ | ✅ (center) | ✅ (branch) | ❌ |
| View assigned orders | N/A | N/A | ✅ | ✅ |
| Create orders | ✅ | ✅ | ✅ | ✅* |
| Edit orders | ✅ | ✅ | ✅ | ✅ (assigned) |
| Delete orders | ✅ | ✅ | ❌ | ❌ |
| Assign orders | ✅ | ✅ | ✅ | ❌ |
| **Customer Management** ||||
| View customers | ✅ | ✅ (center) | ✅ (branch) | ✅ (limited) |
| Edit customers | ✅ | ✅ | ✅ | ❌ |
| Create agencies | ✅ | ✅ | ✅* | ❌ |
| **Financial** ||||
| View financial reports | ✅ | ✅ | ✅ (branch) | ❌ |
| Receive payments | ✅ | ✅ | ✅ | ✅* |
| Confirm payments | ✅ | ✅ | ✅ | ❌ |
| Manage bulk payments | ✅ | ✅ | ✅* | ❌ |
| View debt reports | ✅ | ✅ | ✅ (branch) | ❌ |
| **Marketing** ||||
| Create marketing posts | ✅ | ✅ | ❌ | ❌ |
| Send branch broadcasts | ✅ | ✅ | ✅* | ❌ |
| Send center broadcasts | ✅ | ✅ | ❌ | ❌ |
| **Reports & Analytics** ||||
| View reports | ✅ | ✅ (all) | ✅ (branch) | ✅ (personal) |
| Export reports | ✅ | ✅ | ✅* | ❌ |
| View analytics | ✅ | ✅ (all) | ✅ (branch) | ✅ (personal) |
| **System** ||||
| View audit logs | ✅ | ✅ (center) | ✅ (branch) | ❌ |
| System settings | ✅ | ❌ | ❌ | ❌ |

*\* = Can be granted via custom permissions*

### Custom Role Creation

**Owners can create custom roles with specific permission combinations:**

```
Example: "Customer Service Agent"
✓ View customers
✓ Create orders
✓ Receive payments
✗ Assign orders
✗ View financial reports
✗ Manage staff
```

**Use Cases:**
- Receptionist (front desk)
- Accountant (financial focus)
- Quality Control (review only)
- Customer Service (customer-focused)

---

## 🚀 Quick Start Guide

### Prerequisites

Before starting, ensure you have:

- Python 3.10 or higher
- PostgreSQL 13 or higher
- Redis 6 or higher
- Git
- Virtual environment tool (venv)

### Step 1: Clone Repository

```bash
# Clone the repository
git clone https://github.com/yourcompany/wemard.git
cd wemard

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
```

### Step 2: Install Dependencies

```bash
# Install Python packages
pip install -r requirements.txt

# Verify installation
python --version  # Should be 3.10+
django-admin --version  # Should be 5.2.7
```

### Step 3: Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit .env file with your settings
nano .env  # or your preferred editor
```

**Required Environment Variables:**

```env
# Django Settings
SECRET_KEY=your-super-secret-key-change-this-in-production
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DATABASE_URL=postgresql://username:password@localhost:5432/wemard_db

# Redis
REDIS_URL=redis://localhost:6379/0

# Telegram Bot
BOT_TOKEN=your_telegram_bot_token_from_botfather

# Email (optional)
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your_email@gmail.com
EMAIL_HOST_PASSWORD=your_app_password
EMAIL_USE_TLS=True

# File Storage (optional, defaults to local)
AWS_ACCESS_KEY_ID=your_aws_key
AWS_SECRET_ACCESS_KEY=your_aws_secret
AWS_STORAGE_BUCKET_NAME=wemard-files
AWS_S3_REGION_NAME=us-east-1

# Sentry (optional, for error tracking)
SENTRY_DSN=https://your-sentry-dsn
```

### Step 4: Setup Database

```bash
# Create PostgreSQL database
createdb wemard_db

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser
# Follow prompts to create admin account
```

### Step 5: Load Initial Data (Optional)

```bash
# Setup initial regions and districts
python manage.py setup_regions

# Create default roles
python manage.py setup_roles

# Load sample data (development only)
python manage.py loaddata sample_data.json
```

### Step 6: Compile Translations

```bash
# Compile translation files
python compile_po.py

# Or use Django command
python manage.py compilemessages
```

### Step 7: Run Development Server

```bash
# Start Django development server
python manage.py runserver

# Server will start at: http://127.0.0.1:8000
# Admin interface: http://127.0.0.1:8000/admin
```

### Step 8: Run Telegram Bot (Optional)

```bash
# In a new terminal, activate venv and run:
python manage.py run_bots

# For webhook mode (production):
python manage.py setup_webhooks --base-url https://yourdomain.com
```

### Step 9: Access the Application

**Admin Dashboard:**
```
URL: http://localhost:8000/admin/login/
Username: [your superuser username]
Password: [your superuser password]
```

**Create First Translation Center:**
1. Log in to admin
2. Go to Organizations → Translation Centers
3. Click "Add Translation Center"
4. Fill in details (name, subdomain, etc.)
5. Click "Save"

**Setup Telegram Bot:**
1. Talk to @BotFather on Telegram
2. Create new bot: `/newbot`
3. Copy bot token
4. Add to `.env` file: `BOT_TOKEN=your_token`
5. Restart bot: `python manage.py run_bots`

---

## 📦 Installation

### Development Installation

**1. System Dependencies (Ubuntu/Debian):**

```bash
# Update package list
sudo apt update

# Install Python and pip
sudo apt install python3.10 python3.10-venv python3-pip

# Install PostgreSQL
sudo apt install postgresql postgresql-contrib

# Install Redis
sudo apt install redis-server

# Install system libraries for image processing
sudo apt install libjpeg-dev zlib1g-dev libpng-dev

# Install for PDF processing
sudo apt install libmagic1

# Start services
sudo systemctl start postgresql
sudo systemctl start redis-server
sudo systemctl enable postgresql
sudo systemctl enable redis-server
```

**2. Database Setup:**

```bash
# Switch to postgres user
sudo -u postgres psql

# Create database and user
CREATE DATABASE wemard_db;
CREATE USER wemard_user WITH PASSWORD 'secure_password';
ALTER ROLE wemard_user SET client_encoding TO 'utf8';
ALTER ROLE wemard_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE wemard_user SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE wemard_db TO wemard_user;
\q
```

**3. Application Setup:**

```bash
# Clone and enter directory
git clone https://github.com/yourcompany/wemard.git
cd wemard

# Create virtual environment
python3.10 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env
nano .env  # Edit with your settings

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Collect static files
python manage.py collectstatic --noinput

# Compile translations
python compile_po.py

# Run development server
python manage.py runserver 0.0.0.0:8000
```

### Production Installation

**1. Server Setup (Ubuntu 22.04 LTS):**

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install dependencies
sudo apt install -y python3.10 python3.10-venv python3-pip \
    postgresql postgresql-contrib redis-server nginx supervisor \
    git certbot python3-certbot-nginx

# Install Gunicorn globally
sudo pip3 install gunicorn

# Create application user
sudo useradd -m -s /bin/bash wemard
sudo su - wemard
```

**2. Application Deployment:**

```bash
# As wemard user
cd /home/wemard
git clone https://github.com/yourcompany/wemard.git app
cd app

# Setup virtual environment
python3.10 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn

# Configure environment
cp .env.example .env
nano .env  # Set production values

# Setup database
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py compilemessages

# Create superuser
python manage.py createsuperuser

# Test Gunicorn
gunicorn --bind 0.0.0.0:8000 WowDash.wsgi:application
```

**3. Supervisor Configuration:**

```bash
# Create supervisor config (as root)
sudo nano /etc/supervisor/conf.d/wemard.conf
```

```ini
[program:wemard]
command=/home/wemard/app/venv/bin/gunicorn \
    --workers 4 \
    --bind unix:/home/wemard/app/wemard.sock \
    --timeout 60 \
    --max-requests 1000 \
    --access-logfile /home/wemard/app/logs/gunicorn-access.log \
    --error-logfile /home/wemard/app/logs/gunicorn-error.log \
    WowDash.wsgi:application
    
directory=/home/wemard/app
user=wemard
autostart=true
autorestart=true
redirect_stderr=true
environment=PATH="/home/wemard/app/venv/bin"

[program:wemard-celery]
command=/home/wemard/app/venv/bin/celery -A WowDash worker \
    --loglevel=info \
    --concurrency=2
    
directory=/home/wemard/app
user=wemard
autostart=true
autorestart=true
redirect_stderr=true
environment=PATH="/home/wemard/app/venv/bin"
```

```bash
# Update supervisor
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start wemard
sudo supervisorctl start wemard-celery
```

**4. Nginx Configuration:**

```bash
# Create Nginx config
sudo nano /etc/nginx/sites-available/wemard
```

```nginx
upstream wemard_app {
    server unix:/home/wemard/app/wemard.sock fail_timeout=0;
}

server {
    listen 80;
    server_name yourdomain.com *.yourdomain.com;
    
    client_max_body_size 50M;
    
    location /static/ {
        alias /home/wemard/app/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
    
    location /media/ {
        alias /home/wemard/app/media/;
        expires 7d;
    }
    
    location / {
        proxy_pass http://wemard_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
    }
}
```

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/wemard /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx

# Setup SSL with Let's Encrypt
sudo certbot --nginx -d yourdomain.com -d *.yourdomain.com
```

**5. Setup Telegram Webhooks:**

```bash
# As wemard user
cd /home/wemard/app
source venv/bin/activate
python manage.py setup_webhooks --base-url https://yourdomain.com
```

**6. Setup Automated Backups:**

```bash
# Create backup script
sudo nano /home/wemard/backup.sh
```

```bash
#!/bin/bash
BACKUP_DIR="/home/wemard/backups"
DATE=$(date +%Y%m%d_%H%M%S)

# Database backup
pg_dump -U wemard_user wemard_db | gzip > "$BACKUP_DIR/db_$DATE.sql.gz"

# Delete backups older than 30 days
find $BACKUP_DIR -name "db_*.sql.gz" -mtime +30 -delete
```

```bash
# Make executable
sudo chmod +x /home/wemard/backup.sh

# Add to crontab
sudo crontab -e
# Add line:
0 2 * * * /home/wemard/backup.sh
```

---

## ⚙️ Configuration

### Environment Variables Reference

**Core Django Settings:**

```env
# Security
SECRET_KEY=your-50-character-random-string
DEBUG=False  # Always False in production
ALLOWED_HOSTS=yourdomain.com,*.yourdomain.com

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/dbname
# Or separate variables:
DB_NAME=wemard_db
DB_USER=wemard_user
DB_PASSWORD=secure_password
DB_HOST=localhost
DB_PORT=5432

# Redis
REDIS_URL=redis://localhost:6379/0
# Or separate:
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=  # Optional
```

**Telegram Bot Settings:**

```env
# Bot Configuration
BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz  # From @BotFather
WEBHOOK_URL=https://yourdomain.com/bot/webhook/  # For production
USE_WEBHOOK=True  # True for production, False for development

# Bot Features
ENABLE_NOTIFICATIONS=True
NOTIFICATION_CHANNEL=-1001234567890  # Optional: channel for order notifications
```

**File Storage:**

```env
# Local Storage (default)
MEDIA_ROOT=/home/wemard/app/media
MEDIA_URL=/media/

# S3 Storage (optional, recommended for production)
USE_S3=True
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_STORAGE_BUCKET_NAME=wemard-production
AWS_S3_REGION_NAME=us-east-1
AWS_S3_CUSTOM_DOMAIN=  # Optional: CloudFront domain
AWS_S3_OBJECT_PARAMETERS={
    'CacheControl': 'max-age=86400',
}
```

**Email Configuration:**

```env
# Email Backend
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your_email@gmail.com
EMAIL_HOST_PASSWORD=your_app_password
DEFAULT_FROM_EMAIL=noreply@yourdomain.com

# Or SendGrid
EMAIL_HOST=smtp.sendgrid.net
EMAIL_HOST_USER=apikey
EMAIL_HOST_PASSWORD=your_sendgrid_api_key
```

**Logging & Monitoring:**

```env
# Sentry (Error Tracking)
SENTRY_DSN=https://public_key@sentry.io/project_id
SENTRY_ENVIRONMENT=production
SENTRY_TRACES_SAMPLE_RATE=0.1

# Logging
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_DIR=/home/wemard/app/logs
```

**Security Settings:**

```env
# HTTPS
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True

# HSTS
SECURE_HSTS_SECONDS=31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS=True
SECURE_HSTS_PRELOAD=True

# Additional
X_FRAME_OPTIONS=DENY
SECURE_CONTENT_TYPE_NOSNIFF=True
SECURE_BROWSER_XSS_FILTER=True
```

**Internationalization:**

```env
# Language & Timezone
LANGUAGE_CODE=uz  # Default language
TIME_ZONE=Asia/Tashkent
USE_I18N=True
USE_TZ=True

# Available Languages
LANGUAGES=uz,ru,en
```

**Performance:**

```env
# Cache
CACHE_TIMEOUT=300  # 5 minutes
CACHE_MIDDLEWARE_SECONDS=60

# Database Connection Pooling
DB_CONN_MAX_AGE=600  # 10 minutes

# File Upload
MAX_UPLOAD_SIZE=52428800  # 50MB in bytes
```

### Django Settings Customization

**Local Development (settings_local.py):**

```python
# Create settings_local.py for local overrides
from .settings import *

DEBUG = True
ALLOWED_HOSTS = ['localhost', '127.0.0.1']

# Use console email backend
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Simple cache
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}
```

**Production Optimization (settings_production.py):**

```python
from .settings import *

DEBUG = False
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '').split(',')

# Template caching
TEMPLATES[0]['OPTIONS']['loaders'] = [
    ('django.template.loaders.cached.Loader', [
        'django.template.loaders.filesystem.Loader',
        'django.template.loaders.app_directories.Loader',
    ]),
]

# Static files with compression
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.ManifestStaticFilesStorage'

# Database connection pooling
DATABASES['default']['CONN_MAX_AGE'] = 600
```

---

## 📁 Project Structure

```
WowDash/
│
├── 📱 Django Apps (Business Logic)
│   ├── accounts/                    # User accounts & bot users
│   │   ├── models.py               # BotUser, AdditionalInfo
│   │   ├── views.py                # User management views
│   │   ├── admin.py                # Admin configuration
│   │   ├── urls.py                 # URL routing
│   │   ├── translations.py         # i18n translations
│   │   ├── management/commands/    # CLI commands
│   │   ├── migrations/             # Database migrations
│   │   └── templatetags/           # Custom template tags
│   │
│   ├── bot/                        # Telegram bot integration
│   │   ├── main.py                # Bot handlers
│   │   ├── handlers.py            # Handler registration
│   │   ├── state_manager.py       # Conversation states
│   │   ├── persistent_state.py    # Redis state storage
│   │   ├── notification_service.py # Order notifications
│   │   ├── webhook_manager.py     # Webhook setup
│   │   └── management/commands/   
│   │       ├── run_bots.py        # Start bot (polling)
│   │       └── setup_webhooks.py  # Configure webhooks
│   │
│   ├── core/                       # Core functionality
│   │   ├── models.py              # Region, District, AuditLog
│   │   ├── views.py               # Core views
│   │   ├── audit.py               # Audit logging
│   │   ├── export_service.py      # Excel/PDF export
│   │   └── management/commands/
│   │       └── setup_regions.py   # Initialize regions
│   │
│   ├── marketing/                  # Marketing & broadcasts
│   │   ├── models.py              # BroadcastMessage, Recipient
│   │   ├── views.py               # Marketing dashboard
│   │   ├── broadcast_service.py   # Telegram broadcasts
│   │   └── admin.py               # Marketing admin
│   │
│   ├── orders/                     # Order management
│   │   ├── models.py              # Order, OrderMedia, Receipt
│   │   ├── views.py               # Order CRUD
│   │   ├── bulk_payment_views.py  # Bulk payment processing
│   │   ├── payment_service.py     # Payment logic
│   │   ├── urls.py                # Order URLs
│   │   └── tests.py               # Order tests
│   │
│   ├── organizations/              # Multi-tenant structure
│   │   ├── models.py              # Center, Branch, Role, AdminUser
│   │   ├── views.py               # Organization management
│   │   ├── rbac.py                # Permission system
│   │   ├── middleware.py          # Tenant middleware
│   │   ├── context_processors.py  # Template context
│   │   └── management/commands/
│   │       └── setup_roles.py     # Create default roles
│   │
│   └── services/                   # Services & pricing
│       ├── models.py              # Category, Product, Language
│       ├── views.py               # Service management
│       ├── analytics.py           # Unit economics
│       ├── page_counter.py        # Document processing
│       ├── bot_helpers.py         # Bot integration
│       └── translations.py        # Service translations
│
├── ⚙️  Configuration
│   ├── WowDash/                    # Main Django project
│   │   ├── settings.py            # Core settings
│   │   ├── urls.py                # Root URL config
│   │   ├── wsgi.py                # WSGI entry point
│   │   ├── asgi.py                # ASGI entry point
│   │   ├── home_views.py          # Dashboard views
│   │   └── reports_views.py       # Report views
│   │
│   ├── .env                        # Environment variables (DO NOT COMMIT)
│   ├── .env.example                # Example environment
│   ├── .gitignore                  # Git ignore rules
│   └── manage.py                   # Django CLI tool
│
├── 🎨 Frontend Assets
│   ├── templates/                  # HTML templates
│   │   ├── layout/
│   │   │   ├── layout.html        # Base template
│   │   │   └── blank.html         # Blank template
│   │   ├── partials/
│   │   │   ├── sidebar.html       # Navigation sidebar
│   │   │   ├── navbar.html        # Top navigation
│   │   │   └── footer.html        # Footer
│   │   ├── authentication/
│   │   │   ├── login.html         # Login page
│   │   │   └── forgot-password.html
│   │   ├── index.html             # Main dashboard
│   │   ├── sales.html             # Sales dashboard
│   │   ├── finance.html           # Finance dashboard
│   │   ├── orders/                # Order templates
│   │   ├── organizations/         # Organization templates
│   │   ├── marketing/             # Marketing templates
│   │   ├── reports/               # Report templates
│   │   └── services/              # Service templates
│   │
│   └── static/                     # Static assets
│       ├── css/
│       │   ├── style.css          # Main styles
│       │   ├── theme.css          # Theme variables
│       │   └── custom.css         # Custom overrides
│       ├── js/
│       │   ├── main.js            # Main JavaScript
│       │   ├── dashboard.js       # Dashboard logic
│       │   ├── translations.js    # Frontend i18n (5905 lines!)
│       │   └── utils.js           # Utility functions
│       ├── images/                # Images
│       ├── fonts/                 # Web fonts
│       └── admin/                 # Django admin static files
│
├── 🌍 Internationalization
│   └── locale/                     # Translation files
│       ├── uz/LC_MESSAGES/        # Uzbek
│       │   ├── django.po          # Translation source
│       │   └── django.mo          # Compiled translations
│       ├── ru/LC_MESSAGES/        # Russian
│       │   ├── django.po
│       │   └── django.mo
│       └── en/LC_MESSAGES/        # English
│           ├── django.po
│           └── django.mo
│
├── 📚 Documentation
│   ├── docs/                       # Project documentation
│   │   ├── README.md              # Docs index
│   │   ├── BULK_PAYMENT_ENHANCEMENTS.md
│   │   ├── BULK_PAYMENT_PERMISSIONS.md
│   │   ├── BULK_PAYMENT_QUICK_GUIDE.md
│   │   ├── BOT_SYNC_SUMMARY.md
│   │   ├── TRANSLATION_KEYS.md
│   │   └── STYLING_AND_TRANSLATION_SUMMARY.md
│   │
│   ├── README.md                   # Main project README
│   ├── PROJECT_STRUCTURE.md        # This file
│   └── CONTRIBUTING.md             # Contribution guidelines
│
├── 💾 Data & Logs
│   ├── backups/                    # Database backups
│   │   ├── backup_postgres_*.sql.gz
│   │   └── database/
│   │       └── backup_sqlite_*.db.gz
│   │
│   ├── logs/                       # Application logs
│   │   ├── .gitkeep              # Keep directory
│   │   ├── audit.log             # Audit trail
│   │   ├── bot.log               # Bot activity
│   │   ├── error.log             # Errors
│   │   ├── marketing.log         # Marketing campaigns
│   │   ├── orders.log            # Order processing
│   │   └── payments.log          # Payment transactions
│   │
│   ├── media/                      # User uploads (gitignored)
│   │   ├── order_files/          # Order documents
│   │   ├── receipts/             # Payment receipts
│   │   └── marketing/            # Marketing media
│   │
│   └── db.sqlite3                  # SQLite database (dev only)
│
├── 🛠️  Utilities & Scripts
│   ├── scripts/                    # Utility scripts directory
│   ├── compile_po.py              # Compile translation files
│   ├── translate_po.py            # Translation helper
│   ├── cleanup_project.py         # Project cleanup script
│   └── requirements.txt           # Python dependencies
│
├── 📦 Dependencies & Environment
│   ├── venv/                      # Virtual environment (gitignored)
│   ├── requirements.txt           # Production dependencies
│   ├── requirements-dev.txt       # Development dependencies
│   └── runtime.txt                # Python version (for Heroku)
│
└── 🔧 Development & Deployment
    ├── .git/                      # Git repository
    ├── .github/                   # GitHub Actions (CI/CD)
    │   └── workflows/
    │       ├── deploy.yml         # Deployment workflow
    │       └── tests.yml          # Test workflow
    ├── docker-compose.yml         # Docker Compose config
    ├── Dockerfile                 # Docker container definition
    ├── nginx.conf                 # Nginx configuration
    ├── supervisor.conf            # Supervisor configuration
    └── pytest.ini                 # Test configuration
```

**Key Directory Purposes:**

| Directory | Purpose | Git Tracked |
|-----------|---------|-------------|
| `accounts/` | User management & bot users | ✅ |
| `bot/` | Telegram bot logic | ✅ |
| `core/` | Core utilities & models | ✅ |
| `marketing/` | Marketing campaigns | ✅ |
| `orders/` | Order management | ✅ |
| `organizations/` | Multi-tenant structure | ✅ |
| `services/` | Services & pricing | ✅ |
| `templates/` | HTML templates | ✅ |
| `static/` | CSS, JS, images | ✅ |
| `locale/` | Translations | ✅ |
| `docs/` | Documentation | ✅ |
| `backups/` | Database backups | ❌ (gitignored) |
| `logs/` | Application logs | ❌ (gitignored) |
| `media/` | User uploads | ❌ (gitignored) |
| `venv/` | Virtual environment | ❌ (gitignored) |

---

## 🌐 API Documentation

### REST API Endpoints

**Base URL:** `https://yourdomain.com/api/v1/`

**Authentication:** Session-based (Django) or Token-based (DRF)

#### Orders API

```http
GET /api/v1/orders/
List all orders (filtered by permissions)

Query Parameters:
- status: pending|in_progress|completed|cancelled
- branch: branch_id
- date_from: YYYY-MM-DD
- date_to: YYYY-MM-DD
- page: integer
- page_size: integer

Response:
{
  "count": 100,
  "next": "https://yourdomain.com/api/v1/orders/?page=2",
  "previous": null,
  "results": [
    {
      "id": 1,
      "order_number": "ORD-2024-00001",
      "customer": {
        "id": 1,
        "name": "John Doe",
        "phone": "+998901234567"
      },
      "product": {
        "id": 1,
        "name": "Translation EN→UZ"
      },
      "status": "in_progress",
      "total_price": 50000,
      "total_pages": 5,
      "created_at": "2024-01-23T10:00:00Z",
      "updated_at": "2024-01-23T12:30:00Z"
    }
  ]
}
```

```http
POST /api/v1/orders/
Create new order

Request Body:
{
  "customer_id": 1,
  "product_id": 1,
  "branch_id": 1,
  "document_type_id": 1,
  "copies": 2,
  "payment_type": "cash"
}

Response: 201 Created
{
  "id": 123,
  "order_number": "ORD-2024-00123",
  "status": "pending",
  "total_price": 75000,
  "message": "Order created successfully"
}
```

```http
GET /api/v1/orders/{id}/
Get order details

Response:
{
  "id": 1,
  "order_number": "ORD-2024-00001",
  "customer": { ... },
  "product": { ... },
  "branch": { ... },
  "assigned_to": { ... },
  "status": "in_progress",
  "total_price": 50000,
  "payment_type": "cash",
  "files": [
    {
      "id": 1,
      "file_url": "https://...",
      "file_type": "pdf",
      "uploaded_at": "2024-01-23T10:05:00Z"
    }
  ],
  "timeline": [
    {
      "status": "pending",
      "timestamp": "2024-01-23T10:00:00Z",
      "user": "System"
    },
    {
      "status": "in_progress",
      "timestamp": "2024-01-23T11:00:00Z",
      "user": "John Manager"
    }
  ],
  "created_at": "2024-01-23T10:00:00Z",
  "updated_at": "2024-01-23T12:30:00Z"
}
```

```http
PATCH /api/v1/orders/{id}/
Update order

Request Body:
{
  "status": "completed",
  "notes": "Order completed successfully"
}

Response: 200 OK
{
  "id": 1,
  "status": "completed",
  "message": "Order updated successfully"
}
```

#### Customers API

```http
GET /api/v1/customers/
List customers

Query Parameters:
- is_agency: true|false
- branch: branch_id
- search: name or phone
- page: integer

Response:
{
  "count": 50,
  "results": [
    {
      "id": 1,
      "name": "John Doe",
      "phone": "+998901234567",
      "telegram_user_id": 123456789,
      "is_agency": false,
      "total_orders": 15,
      "total_spent": 750000,
      "current_balance": 50000,
      "registered_at": "2024-01-01T00:00:00Z"
    }
  ]
}
```

```http
GET /api/v1/customers/{id}/orders/
Get customer orders

Response:
{
  "customer": { ... },
  "orders": [
    { "id": 1, "order_number": "ORD-2024-00001", ... }
  ],
  "statistics": {
    "total_orders": 15,
    "completed_orders": 12,
    "cancelled_orders": 1,
    "total_spent": 750000,
    "average_order_value": 50000
  }
}
```

#### Reports API

```http
GET /api/v1/reports/revenue/
Revenue report

Query Parameters:
- period: today|week|month|year|custom
- date_from: YYYY-MM-DD (if period=custom)
- date_to: YYYY-MM-DD (if period=custom)
- branch: branch_id

Response:
{
  "period": "month",
  "date_from": "2024-01-01",
  "date_to": "2024-01-31",
  "summary": {
    "total_revenue": 5000000,
    "total_orders": 100,
    "average_order_value": 50000,
    "cash_revenue": 3000000,
    "card_revenue": 2000000
  },
  "daily_breakdown": [
    {
      "date": "2024-01-01",
      "revenue": 150000,
      "orders": 3
    }
  ]
}
```

### Webhook Endpoints

#### Telegram Bot Webhook

```http
POST /bot/webhook/{bot_token}/
Telegram bot webhook

Request Body: Telegram Update object
{
  "update_id": 123456789,
  "message": {
    "message_id": 1,
    "from": {
      "id": 123456789,
      "first_name": "John",
      "username": "johndoe"
    },
    "chat": {
      "id": 123456789,
      "type": "private"
    },
    "date": 1640000000,
    "text": "/start"
  }
}

Response: 200 OK
{
  "ok": true
}
```

### API Authentication

**Session Authentication (Web):**
```python
# Login first
response = requests.post(
    'https://yourdomain.com/accounts/login/',
    data={'username': 'admin', 'password': 'password'}
)

# Use session cookie for subsequent requests
orders = requests.get(
    'https://yourdomain.com/api/v1/orders/',
    cookies=response.cookies
)
```

**Token Authentication (API):**
```python
# Get token
response = requests.post(
    'https://yourdomain.com/api/v1/auth/token/',
    json={'username': 'admin', 'password': 'password'}
)
token = response.json()['token']

# Use token in headers
orders = requests.get(
    'https://yourdomain.com/api/v1/orders/',
    headers={'Authorization': f'Token {token}'}
)
```

### Rate Limiting

- **Authenticated users**: 1000 requests/hour
- **Anonymous users**: 100 requests/hour
- **Telegram webhooks**: Unlimited

### Error Responses

```json
// 400 Bad Request
{
  "error": "validation_error",
  "message": "Invalid input data",
  "details": {
    "field_name": ["Error message"]
  }
}

// 401 Unauthorized
{
  "error": "authentication_required",
  "message": "Authentication credentials were not provided"
}

// 403 Forbidden
{
  "error": "permission_denied",
  "message": "You do not have permission to perform this action"
}

// 404 Not Found
{
  "error": "not_found",
  "message": "Resource not found"
}

// 500 Internal Server Error
{
  "error": "server_error",
  "message": "An unexpected error occurred",
  "request_id": "abc123"  // For support
}
```

---

## 🔒 Security

### Security Features

**1. Authentication & Authorization**
- ✅ Django's built-in authentication system
- ✅ PBKDF2 password hashing (260,000 iterations)
- ✅ Password complexity requirements
- ✅ Account lockout after 5 failed attempts
- ✅ Session timeout (2 weeks default, configurable)
- ✅ Remember me functionality
- ✅ Two-factor authentication (optional add-on)

**2. Input Validation & Sanitization**
- ✅ Django Forms validation
- ✅ Model-level validation
- ✅ XSS prevention (template auto-escaping)
- ✅ SQL injection prevention (Django ORM)
- ✅ CSRF protection (all POST requests)
- ✅ File upload validation (type, size)
- ✅ HTML sanitization for user input

**3. Network Security**
- ✅ HTTPS/TLS encryption (forced in production)
- ✅ HSTS headers (HTTP Strict Transport Security)
- ✅ Secure cookies (HTTPOnly, Secure flags)
- ✅ X-Frame-Options: DENY (clickjacking protection)
- ✅ X-Content-Type-Options: nosniff
- ✅ Content Security Policy (CSP)

**4. Rate Limiting & DDoS Protection**
- ✅ Request rate limiting (Redis-based)
- ✅ API throttling (1000 req/hour authenticated)
- ✅ Login attempt limiting
- ✅ Cloudflare DDoS protection (recommended)
- ✅ Fail2ban integration (optional)

**5. Data Protection**
- ✅ Encrypted database connections
- ✅ Sensitive data hashing (passwords, tokens)
- ✅ PII data access logging
- ✅ GDPR compliance features
- ✅ Data retention policies
- ✅ Secure file storage (S3 with encryption)

**6. Audit & Monitoring**
- ✅ Comprehensive audit logging
- ✅ User action tracking
- ✅ Failed login attempt logging
- ✅ Security event alerts
- ✅ Sentry error tracking
- ✅ Log retention (90 days)

### Security Best Practices

**For Deployment:**

```bash
# 1. Use strong SECRET_KEY
python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'

# 2. Set DEBUG=False in production
DEBUG=False

# 3. Restrict ALLOWED_HOSTS
ALLOWED_HOSTS=yourdomain.com,*.yourdomain.com

# 4. Use HTTPS
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True

# 5. Enable HSTS
SECURE_HSTS_SECONDS=31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS=True
SECURE_HSTS_PRELOAD=True

# 6. Secure cookies
SESSION_COOKIE_HTTPONLY=True
CSRF_COOKIE_HTTPONLY=True
SESSION_COOKIE_SAMESITE='Lax'
CSRF_COOKIE_SAMESITE='Lax'

# 7. Set strong database password
DB_PASSWORD=$(openssl rand -base64 32)

# 8. Limit file upload size
MAX_UPLOAD_SIZE=52428800  # 50MB

# 9. Use environment variables for secrets
# Never commit .env file to git

# 10. Regular security updates
pip list --outdated
pip install --upgrade django
```

**For Database:**

```sql
-- Create restricted database user
CREATE USER wemard_app WITH PASSWORD 'strong_password';
GRANT CONNECT ON DATABASE wemard_db TO wemard_app;
GRANT USAGE ON SCHEMA public TO wemard_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO wemard_app;

-- No SUPERUSER, CREATEDB, CREATEROLE permissions
```

**For Server:**

```bash
# 1. Firewall configuration
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 22/tcp
sudo ufw enable

# 2. Disable root SSH login
sudo nano /etc/ssh/sshd_config
# Set: PermitRootLogin no
sudo systemctl restart sshd

# 3. Install fail2ban
sudo apt install fail2ban
sudo systemctl enable fail2ban

# 4. Keep system updated
sudo apt update && sudo apt upgrade -y

# 5. Remove unnecessary services
sudo systemctl list-unit-files --type=service
sudo systemctl disable <unused-service>
```

### Security Checklist

**Pre-Launch Checklist:**

- [ ] `DEBUG=False` in production
- [ ] Strong `SECRET_KEY` (50+ characters)
- [ ] HTTPS configured with valid SSL certificate
- [ ] `ALLOWED_HOSTS` restricted to actual domains
- [ ] Database password is strong and secure
- [ ] Redis password configured
- [ ] All sensitive data in environment variables
- [ ] `.env` file not committed to git
- [ ] File upload validation enabled
- [ ] Rate limiting configured
- [ ] CSRF protection enabled
- [ ] Session security settings applied
- [ ] Error tracking (Sentry) configured
- [ ] Automated backups scheduled
- [ ] Firewall rules configured
- [ ] SSH key-based authentication only
- [ ] Regular security updates plan
- [ ] Audit logging enabled
- [ ] Security headers configured
- [ ] Content Security Policy set

**Post-Launch Monitoring:**

- [ ] Monitor Sentry for errors
- [ ] Review audit logs weekly
- [ ] Check failed login attempts
- [ ] Monitor server resources
- [ ] Verify backup integrity
- [ ] Review API usage patterns
- [ ] Check SSL certificate expiry
- [ ] Review user permissions quarterly
- [ ] Update dependencies monthly
- [ ] Security audit annually

---

## ⚡ Performance & Scalability

### Performance Optimizations

**1. Database Optimization**

```python
# Query optimization with select_related (reduce queries)
orders = Order.objects.select_related(
    'customer', 'product', 'branch', 'assigned_to'
).all()

# Prefetch related objects
orders = Order.objects.prefetch_related(
    'files', 'timeline_events'
).all()

# Database indexes
class Order(models.Model):
    class Meta:
        indexes = [
            models.Index(fields=['center', 'status', 'created_at']),
            models.Index(fields=['center', 'branch', 'created_at']),
            models.Index(fields=['customer', 'created_at']),
        ]

# Database connection pooling
DATABASES = {
    'default': {
        'CONN_MAX_AGE': 600,  # 10 minutes
        'OPTIONS': {
            'connect_timeout': 10,
        }
    }
}
```

**2. Caching Strategy**

```python
# Redis caching configuration
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'PARSER_CLASS': 'redis.connection.HiredisParser',
            'CONNECTION_POOL_KWARGS': {
                'max_connections': 50,
                'retry_on_timeout': True
            }
        },
        'KEY_PREFIX': 'wemard',
        'TIMEOUT': 300,  # 5 minutes default
    }
}

# Cache expensive queries
from django.core.cache import cache

def get_dashboard_stats(center_id):
    cache_key = f'dashboard_stats_{center_id}'
    stats = cache.get(cache_key)
    
    if stats is None:
        stats = calculate_dashboard_stats(center_id)
        cache.set(cache_key, stats, 300)  # 5 minutes
    
    return stats

# Template fragment caching
{% load cache %}
{% cache 300 sidebar request.user.id %}
    <!-- Expensive sidebar content -->
{% endcache %}
```

**3. Static Files & CDN**

```python
# Static files with compression
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.ManifestStaticFilesStorage'

# Use CDN for static files
AWS_S3_CUSTOM_DOMAIN = 'd123456.cloudfront.net'
STATIC_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/static/'

# Asset minification
COMPRESS_ENABLED = True
COMPRESS_OFFLINE = True
```

**4. Async Task Processing**

```python
# Celery for background tasks
from celery import shared_task

@shared_task
def send_broadcast_message(broadcast_id):
    """Send broadcast message asynchronously"""
    broadcast = BroadcastMessage.objects.get(id=broadcast_id)
    # Send to thousands without blocking
    ...

@shared_task
def generate_report(report_id):
    """Generate report in background"""
    # Heavy computation doesn't block UI
    ...

# Call from view
send_broadcast_message.delay(broadcast_id)
```

**5. API Optimization**

```python
# Pagination
from rest_framework.pagination import PageNumberPagination

class StandardPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200

# Selective field serialization
class OrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = ['id', 'order_number', 'status', 'total_price']
        # Exclude heavy fields for list views

# API throttling
REST_FRAMEWORK = {
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle'
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',
        'user': '1000/hour'
    }
}
```

### Scalability Architecture

**Horizontal Scaling:**

```
┌──────────────────────────────────────────────────┐
│           Load Balancer (Nginx/HAProxy)          │
└────┬─────────────┬────────────────┬──────────────┘
     │             │                │
┌────▼────┐   ┌────▼────┐     ┌────▼────┐
│ App     │   │ App     │  …  │ App     │
│ Server 1│   │ Server 2│     │ Server N│
└────┬────┘   └────┬────┘     └────┬────┘
     │             │                │
     └─────────────┼────────────────┘
                   │
     ┌─────────────┴────────────────┐
     │                              │
┌────▼────┐                    ┌────▼────┐
│PostgreSQL│                    │  Redis  │
│  Primary │                    │ Cluster │
│    +     │                    └─────────┘
│ Read     │
│ Replicas │
└──────────┘
```

**Capacity Planning:**

| Metric | Starter | Professional | Enterprise |
|--------|---------|--------------|------------|
| **Concurrent Users** | 50 | 500 | 5,000+ |
| **Orders/Day** | 500 | 5,000 | 50,000+ |
| **Database Size** | 5 GB | 50 GB | 500 GB+ |
| **App Servers** | 1 | 2-4 | 4-10+ |
| **DB Configuration** | Single | Primary + 1 replica | Primary + 3 replicas |
| **Redis** | Single | Single with persistence | Cluster (3-6 nodes) |
| **Expected Response** | <500ms | <300ms | <200ms |
| **Uptime SLA** | 99% | 99.5% | 99.9% |

**Performance Targets:**

| Page | Target Load Time |
|------|------------------|
| Dashboard | < 500ms |
| Order List | < 300ms |
| Order Detail | < 200ms |
| API Endpoints | < 100ms |
| Static Assets | < 50ms (with CDN) |

**Load Testing:**

```bash
# Using Apache Bench
ab -n 10000 -c 100 https://yourdomain.com/

# Using Locust
pip install locust
locust -f locustfile.py --host=https://yourdomain.com

# Example locustfile.py
from locust import HttpUser, task

class WebsiteUser(HttpUser):
    @task
    def view_dashboard(self):
        self.client.get("/dashboard/")
    
    @task(3)  # 3x more frequent
    def view_orders(self):
        self.client.get("/orders/")
```

**Monitoring & Alerts:**

```python
# Performance monitoring with Sentry
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

sentry_sdk.init(
    dsn="your-sentry-dsn",
    integrations=[DjangoIntegration()],
    traces_sample_rate=0.1,  # 10% of transactions
    profiles_sample_rate=0.1,
)

# Custom performance metrics
from django.db import connection
from django.test.utils import CaptureQueriesContext

def expensive_view(request):
    with CaptureQueriesContext(connection) as context:
        # Your view logic
        ...
    
    if len(context.captured_queries) > 50:
        logger.warning(f"Too many queries: {len(context.captured_queries)}")
```

---

## 🌍 Internationalization

### Supported Languages

| Language | Code | Status | Completion |
|----------|------|--------|------------|
| **Uzbek** | uz | Primary | 100% |
| **Russian** | ru | Secondary | 100% |
| **English** | en | International | 100% |

### Translation System

**Dual Translation Architecture:**

1. **Django Backend (`.po`/`.mo` files)**
   - Server-side rendering
   - View context strings
   - Model field translations
   - Email templates

2. **JavaScript Frontend (`translations.js`)**
   - Dynamic UI updates
   - Client-side rendering
   - Real-time language switching
   - Takes precedence when `data-i18n` attribute present

### Adding New Translations

**Step 1: Mark strings for translation**

```python
# In Python code
from django.utils.translation import gettext_lazy as _

def my_view(request):
    context = {
        'title': _("Dashboard"),
        'welcome': _("Welcome to WEMARD"),
    }
```

```html
<!-- In templates -->
{% load i18n %}

<h1>{% trans "Dashboard" %}</h1>

<!-- With JavaScript translation -->
<span data-i18n="dashboard.title">{% trans "Dashboard" %}</span>
```

**Step 2: Extract messages**

```bash
# Extract translatable strings
python manage.py makemessages -l uz
python manage.py makemessages -l ru
python manage.py makemessages -l en

# This creates/updates:
# locale/uz/LC_MESSAGES/django.po
# locale/ru/LC_MESSAGES/django.po
# locale/en/LC_MESSAGES/django.po
```

**Step 3: Translate strings**

```po
# locale/uz/LC_MESSAGES/django.po
msgid "Dashboard"
msgstr "Boshqaruv paneli"

msgid "Welcome to WEMARD"
msgstr "WEMARD ga xush kelibsiz"
```

**Step 4: Compile translations**

```bash
# Compile .po files to .mo binary format
python compile_po.py

# Or use Django command
python manage.py compilemessages
```

**Step 5: Add JavaScript translations**

```javascript
// static/js/translations.js
const translations = {
    'dashboard.title': {
        uz: 'Boshqaruv paneli',
        ru: 'Панель управления',
        en: 'Dashboard'
    },
    'dashboard.welcome': {
        uz: 'WEMARD ga xush kelibsiz',
        ru: 'Добро пожаловать в WEMARD',
        en: 'Welcome to WEMARD'
    }
};
```

**Step 6: Restart server**

```bash
# Restart to load new translations
sudo supervisorctl restart wemard
```

### Language Switching

**In Admin Dashboard:**

```html
<!-- Language selector in navbar -->
<select id="language-selector" onchange="changeLanguage(this.value)">
    <option value="uz">O'zbekcha</option>
    <option value="ru">Русский</option>
    <option value="en">English</option>
</select>

<script>
function changeLanguage(lang) {
    document.cookie = `django_language=${lang}; path=/`;
    location.reload();
}
</script>
```

**In Telegram Bot:**

```python
# Bot automatically detects and uses user's Telegram language
# User can change language with /language command

@bot.message_handler(commands=['language'])
def change_language(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("O'zbekcha", callback_data="lang_uz"),
        types.InlineKeyboardButton("Русский", callback_data="lang_ru"),
        types.InlineKeyboardButton("English", callback_data="lang_en")
    )
    bot.send_message(message.chat.id, "Choose language:", reply_markup=markup)
```

### Translation Coverage

**Current Stats:**
- Django .po files: 550 translatable strings
- JavaScript translations.js: 200+ translation keys
- Total coverage: 100% for uz/ru/en

**Translation Guidelines:**

1. **Be Consistent**: Use same terminology throughout
2. **Context Matters**: Provide context for translators
3. **Keep It Short**: Especially for buttons and labels
4. **Test Both RTL/LTR**: Ensure layout works for all languages
5. **Cultural Sensitivity**: Consider cultural nuances

---

## 🗺️ Roadmap

### Version 2.1 (Q2 2026) - Mobile & UX

- [ ] Mobile apps (iOS & Android) with React Native
- [ ] Progressive Web App (PWA) support
- [ ] Push notifications for mobile
- [ ] Offline mode for basic operations
- [ ] Improved mobile-responsive dashboard
- [ ] Touch-optimized UI components
- [ ] QR code scanning for order tracking
- [ ] Biometric authentication (Face ID, Touch ID)

### Version 2.2 (Q3 2026) - AI & Automation

- [ ] AI-powered document type recognition
- [ ] Intelligent page counting with ML
- [ ] Automatic language pair detection
- [ ] Smart pricing suggestions
- [ ] Predictive analytics for demand forecasting
- [ ] Chatbot for customer support
- [ ] Automated order assignment optimization
- [ ] Fraud detection for payments

### Version 2.3 (Q4 2026) - Integrations

- [ ] Payment gateway integrations (Payme, Click, Uzum)
- [ ] E-signature integration
- [ ] Government API integrations (apostille verification)
- [ ] Accounting software integration (1C, QuickBooks)
- [ ] CRM integration (Salesforce, HubSpot)
- [ ] SMS provider integration
- [ ] Email marketing integration
- [ ] Google Analytics & Facebook Pixel

### Version 3.0 (2027) - Enterprise Features

- [ ] Advanced workflow automation
- [ ] Custom approval workflows
- [ ] Multi-currency support
- [ ] Tax calculation and invoicing
- [ ] Contract management
- [ ] Document versioning
- [ ] Blockchain verification (optional)
- [ ] Advanced role customization
- [ ] API marketplace
- [ ] White-label mobile apps

### Future Considerations

**Technical Improvements:**
- Microservices architecture for very large deployments
- GraphQL API alternative to REST
- Real-time collaboration features
- Advanced reporting with custom report builder
- Data warehouse for analytics
- Machine learning models for various predictions

**Business Features:**
- Franchise management
- Partner/reseller portal
- Customer loyalty programs
- Subscription services for customers
- Insurance products
- Legal document templates
- Online document signing
- Video consultation scheduling

**Geographic Expansion:**
- Support for 20+ languages
- Region-specific compliance features
- Local payment methods per country
- Currency exchange integration
- Multi-timezone support improvements

---

## 🤝 Contributing

We welcome contributions from the community! Here's how you can help:

### Ways to Contribute

1. **Report Bugs**: Found a bug? Report it on our issue tracker
2. **Suggest Features**: Have an idea? We'd love to hear it
3. **Improve Documentation**: Help make our docs better
4. **Write Code**: Submit pull requests for new features or fixes
5. **Translate**: Help translate the platform to new languages

### Development Setup

```bash
# Fork and clone the repository
git clone https://github.com/yourusername/wemard.git
cd wemard

# Create a feature branch
git checkout -b feature/your-feature-name

# Make your changes
# ... code ...

# Run tests
python manage.py test

# Run linters
flake8 .
black .
isort .

# Commit your changes
git add .
git commit -m "Add: Your descriptive commit message"

# Push to your fork
git push origin feature/your-feature-name

# Create a Pull Request on GitHub
```

### Code Style

- Follow PEP 8 for Python code
- Use Black for code formatting
- Use isort for import sorting
- Write docstrings for all functions/classes
- Add type hints where appropriate
- Write tests for new features

### Commit Message Format

```
Type: Short description (50 chars max)

Longer description if needed (wrap at 72 chars).
Explain the problem being solved and why this approach was chosen.

Fixes #123
```

**Types:**
- `Add`: New feature
- `Fix`: Bug fix
- `Update`: Update existing feature
- `Remove`: Remove feature/code
- `Refactor`: Code refactoring
- `Docs`: Documentation changes
- `Test`: Add/update tests
- `Style`: Code style changes

---

## 📄 License

**Proprietary License**

This software is proprietary and confidential. Unauthorized copying, distribution, or use of this software, via any medium, is strictly prohibited.

© 2024-2026 WEMARD. All rights reserved.

**For Licensing Inquiries:**
- Email: licensing@wemard.com
- Website: https://wemard.com/contact

---

## 📞 Support & Contact

### Technical Support

**For Customers:**
- 📧 Email: support@wemard.com
- 💬 Live Chat: Available in dashboard
- 📚 Documentation: https://docs.wemard.com
- 🎥 Video Tutorials: https://youtube.com/@wemard

**Response Times:**
- Starter Plan: 24-48 hours (email)
- Professional Plan: 12-24 hours (email & phone)
- Enterprise Plan: 2-4 hours (24/7 priority support)

### Sales & Partnership

**For Sales Inquiries:**
- 📧 Email: sales@wemard.com
- 📞 Phone: +998 99 123 45 67
- 🌐 Website: https://wemard.com
- 📍 Office: Tashkent, Uzbekistan

**For Partnership:**
- 📧 Email: partners@wemard.com
- 📋 Partnership Form: https://wemard.com/partners

### Community

- 💬 Telegram Channel: @wemard_official
- 👥 Telegram Group: @wemard_users
- 📱 LinkedIn: linkedin.com/company/wemard
- 🐦 Twitter: @wemard_official

### Bug Reports & Feature Requests

- 🐛 GitHub Issues: https://github.com/wemard/wemard/issues
- 💡 Feature Requests: https://feedback.wemard.com

---

## 🙏 Acknowledgments

**Built With Love Using:**
- Django - The web framework for perfectionists with deadlines
- Bootstrap - The most popular HTML, CSS, and JS library
- PostgreSQL - The world's most advanced open source database
- Redis - In-memory data structure store
- Telegram Bot API - Simple and powerful bot framework

**Special Thanks:**
- All our beta testers and early adopters
- The Django community for excellent documentation
- The open-source community for amazing tools
- Our customers for their valuable feedback

---

## 📊 Project Stats

![GitHub Stars](https://img.shields.io/github/stars/wemard/wemard?style=social)
![GitHub Forks](https://img.shields.io/github/forks/wemard/wemard?style=social)
![GitHub Issues](https://img.shields.io/github/issues/wemard/wemard)
![GitHub Pull Requests](https://img.shields.io/github/issues-pr/wemard/wemard)

**Project Metrics:**
- Lines of Code: ~50,000
- Number of Models: 30+
- Number of Views: 100+
- Number of Templates: 70+
- Number of API Endpoints: 50+
- Test Coverage: 85%
- Documentation Pages: 200+

---

<div align="center">

**WEMARD - Complete Translation Center Management Solution**

*Transforming document processing businesses through intelligent automation*

[Get Started](https://wemard.com) • [Schedule Demo](https://wemard.com/demo) • [View Pricing](https://wemard.com/pricing)

Made with ❤️ in Uzbekistan

© 2024-2026 WEMARD. All rights reserved.

</div>
