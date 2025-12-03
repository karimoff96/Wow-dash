# WEMARD - Translation Center Management System

A comprehensive **multi-tenant SaaS platform** for managing translation centers, with an integrated Telegram bot for customer ordering and a modern admin dashboard for business operations.

---

## 🎯 Project Summary

**WEMARD** is a complete business management solution designed for translation service companies. It enables:

- **Translation Center Owners** to manage multiple branches, staff, services, and track business performance
- **Customers** to order translation/apostille services via Telegram bot with automatic pricing
- **Staff Members** to process orders with role-based access control

### Core Value Proposition
- 🏢 **Multi-tenant Architecture** - One platform serves multiple translation centers
- 🤖 **Telegram Bot Integration** - Customers order directly through Telegram
- 📊 **Real-time Analytics** - Sales, revenue, and staff performance dashboards
- 🔐 **Role-Based Access Control (RBAC)** - Granular permissions for different user types
- 🌍 **Multi-language Support** - Uzbek, Russian, and English interfaces

---

## 🏗️ System Architecture

### User Hierarchy
```
Super Admin (Platform Owner)
    └── Translation Center Owner
            └── Branch
                    ├── Manager
                    └── Staff Members
```

### Main Modules

| Module | Description |
|--------|-------------|
| **Organizations** | Centers, Branches, Staff, Roles & Permissions |
| **Services** | Categories (Translation, Apostille), Products with pricing |
| **Orders** | Order lifecycle, payments, file management, assignment |
| **Accounts** | Bot users (customers), Admin users, Agencies |
| **Analytics** | Dashboards, Reports, Staff Performance |
| **Bot** | Telegram integration for customer ordering |

---

## 👥 User Roles & Permissions

| Role | Access Level |
|------|--------------|
| **Super Admin** | Full platform access, manage all centers |
| **Owner** | Manage their center, all branches, staff, products |
| **Manager** | Manage assigned branch, view reports, assign orders |
| **Staff** | Process assigned orders, view personal statistics |

### Key Permissions
- `can_manage_center` - Center settings and configuration
- `can_manage_branches` - Branch CRUD operations
- `can_manage_staff` - Staff user management
- `can_manage_products` - Categories and products
- `can_manage_orders` - Order status updates
- `can_assign_orders` - Assign orders to staff
- `can_view_reports` - Analytics and reports access
- `can_receive_payments` - Payment confirmation

---

## 📱 Telegram Bot Features

### Customer Journey
1. **Start** → Language selection (UZ/RU/EN)
2. **Registration** → Name, phone number collection
3. **Service Selection** → Choose category (Translation/Apostille)
4. **Document Upload** → Upload files (PDF, DOCX, images)
5. **Pricing** → Automatic page counting & price calculation
6. **Payment** → Cash or card with receipt upload
7. **Tracking** → Order status notifications

### Pricing System
- **Per-page pricing** - Dynamic pricing based on document pages
- **Agency discounts** - Special rates for agency customers
- **Copy pricing** - Additional copies at percentage rate
- **Static/Dynamic** - Fixed price or per-page options

### Supported File Types
- PDF (automatic page counting)
- DOCX (content-based estimation)
- Images (JPG, PNG - 1 page each)
- Text files (line-based estimation)

---

## 🖥️ Admin Dashboard Features

### Dashboard Views
- **Main Dashboard** - Overview with key metrics
- **Sales Dashboard** - Revenue, orders, trends
- **Finance Dashboard** - Payments, pending amounts

### Management Sections
- **Organizations** - Centers, Branches, Staff, Roles
- **Customers** - Bot users with order history
- **Orders** - Full order lifecycle management
- **Services** - Categories and Products with translations
- **Reports** - Financial, Orders, Staff Performance

### UI Features
- 🌙 Dark/Light mode toggle
- 🌐 Multi-language interface (UZ/RU/EN)
- 📱 Responsive design
- 📊 Interactive charts (ApexCharts)
- 🔍 Advanced search and filtering
- 📄 Pagination with customizable page size

---

## 🛠️ Technical Stack

| Layer | Technology |
|-------|------------|
| **Backend** | Django 5.2, Python 3.10+ |
| **Database** | SQLite (dev), PostgreSQL (prod) |
| **Bot** | pyTelegramBotAPI |
| **Frontend** | Bootstrap 5, jQuery, Iconify |
| **Charts** | ApexCharts |
| **Translations** | django-modeltranslation |
| **File Processing** | PyPDF2, python-docx, Pillow |

---

## 📁 Project Structure

```
WowDash/
├── accounts/           # User authentication, bot users
├── bot/                # Telegram bot logic
├── core/               # Regions, districts, audit logs
├── orders/             # Order management
├── organizations/      # Centers, branches, staff, RBAC
├── services/           # Categories, products, pricing
├── templates/          # HTML templates
├── static/             # CSS, JS, images
├── WowDash/            # Django settings, URLs
├── manage.py
└── requirements.txt
```

---

## 🚀 Quick Start

```bash
# 1. Clone and setup
git clone <repository>
cd WowDash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run migrations
python manage.py migrate

# 4. Create superuser
python manage.py createsuperuser

# 5. Setup initial data (optional)
python manage.py setup_initial_data

# 6. Run server
python manage.py runserver
```

---

## 📊 Key Features Summary

### For Center Owners
✅ Multi-branch management  
✅ Staff management with roles  
✅ Product/service configuration  
✅ Revenue and sales analytics  
✅ Staff performance tracking  

### For Managers
✅ Branch operations oversight  
✅ Order assignment to staff  
✅ Daily/weekly reports  
✅ Customer management  

### For Staff
✅ Personal order queue  
✅ Order status updates  
✅ Personal statistics  

### For Customers (via Bot)
✅ Easy service ordering  
✅ Automatic price calculation  
✅ Order tracking  
✅ Multi-language support  
✅ Payment options (cash/card)  

---

## 🔐 Security

- Django authentication system
- Role-based access control
- Branch-level data isolation
- Secure file upload handling
- Input validation and sanitization
- Audit logging for critical actions

---

## 📈 Analytics & Reports

- **Financial Reports** - Revenue by period, payment methods
- **Order Reports** - Status distribution, volume trends
- **Staff Performance** - Completed orders, average time
- **Customer Analytics** - New registrations, order frequency

---

## 🌍 Internationalization

Full support for 3 languages:
- 🇺🇿 **Uzbek** (O'zbek) - Primary
- 🇷🇺 **Russian** (Русский) - Secondary
- 🇬🇧 **English** - International

Both admin interface and bot support language switching.

---

## 📞 Support

For questions and support, contact the system administrator.

---

**WEMARD** - Complete Translation Center Management Solution

