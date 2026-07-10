# MultiLang - Translation Center Management Platform

Multi-tenant SaaS platform for translation agencies with Telegram bot integration.

---

## 🚀 Quick Start

### Development
```bash
# 1. Install dependencies
pip install -r requirements.txt

# Select explicit local settings
export DJANGO_SETTINGS_MODULE=WowDash.settings_development

# 2. Run migrations
python manage.py migrate

# 3. Create superuser
python manage.py createsuperuser

# 4. Start Django
python manage.py runserver

# 5. Start admin bot (in another terminal)
python manage.py admin_bot
```

### Production
See [docs/DEPLOYMENT_GUIDE.md](docs/DEPLOYMENT_GUIDE.md)

---

## 📚 Documentation

| Document | Purpose |
|----------|---------|
| [docs/SERVER_COMMANDS.md](docs/SERVER_COMMANDS.md) | All server commands reference |
| [docs/ADMIN_BOT.md](docs/ADMIN_BOT.md) | Admin notification bot guide |
| [docs/DEPLOYMENT_GUIDE.md](docs/DEPLOYMENT_GUIDE.md) | Production deployment |
| [docs/RELIABILITY_ROLLOUT.md](docs/RELIABILITY_ROLLOUT.md) | Safe migration, webhook, archive, and rollback runbook |
| [docs/USER_GUIDE.md](docs/USER_GUIDE.md) | End-user documentation |
| [docs/README_ARCHIVE_CRON.md](docs/README_ARCHIVE_CRON.md) | Archive automation |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────┐
│           Production Server             │
├─────────────────────────────────────────┤
│                                         │
│  Django App (wemard)                    │← Web interface, admin panel
│  Telegram webhook worker                │← All translation center bots
│  Admin Bot (multilang-admin-bot)        │← Notifications bot
│                                         │
│  Managed via Supervisor                 │
└─────────────────────────────────────────┘
```

---

## 🔑 Key Features

- 📋 **Order Management** - Handle translation orders with status tracking
- 💰 **Billing System** - Payments, invoices, subscription management
- 🤖 **Telegram Bots** - Multi-tenant bot system (one bot per center)
- 👥 **RBAC** - Role-based access control (Owner, Manager, Staff)
- 🌍 **Multi-language** - Russian, Uzbek, English
- 📊 **Analytics** - Real-time reports and statistics
- 🔔 **Admin Notifications** - Contact requests, renewal alerts
- 📦 **Auto-archiving** - Automatic order archiving to Telegram

---

## 🛠️ Tech Stack

- **Backend:** Django 5.2.7, Python 3.12
- **Database:** PostgreSQL
- **Bots:** PyTelegramBotAPI (telebot), centralized webhooks
- **Process Manager:** Supervisor
- **Web Server:** Nginx + Gunicorn

---

## 📱 Bots

### Customer Bots (centralized delivery)
- Customers place orders via Telegram
- Automatic price calculation
- File uploads and downloads
- Order tracking

**Control:**
```bash
# Polling is retained only as a per-center rollback mode
python manage.py run_bots

# Production
sudo supervisorctl restart wowdash-bots
```

See [docs/RELIABILITY_ROLLOUT.md](docs/RELIABILITY_ROLLOUT.md) before applying
migrations, enabling webhooks, or allowing archive deletion.

### Admin Bot (@uzmultilang_bot)
- Receive contact form submissions
- Subscription renewal notifications
- Commands: `/start`, `/myid`, `/status`

**Control:**
```bash
# Development
python manage.py admin_bot

# Production
sudo supervisorctl restart multilang-admin-bot
```

---

## 📁 Project Structure

```
MultiLang/
├── accounts/              # User authentication
├── billing/               # Subscriptions, payments
├── bot/                   # Telegram bots
│   ├── handlers.py        # Customer bot handlers
│   ├── admin_bot_service.py  # Admin bot
│   └── management/commands/  # Bot commands
├── core/                  # Core models (documents, files)
├── landing/               # Landing page
├── orders/                # Order management
├── organizations/         # Multi-tenancy, RBAC
├── services/              # Products, pricing
├── deployment/            # Production configs (supervisor)
├── docs/                  # Documentation
├── locale/                # Translations (ru, uz, en)
├── static/                # Static files
├── templates/             # HTML templates
└── manage.py
```

---

## 🔧 Common Commands

### Django
```bash
python manage.py runserver              # Start dev server
python manage.py migrate                # Run migrations
python manage.py collectstatic          # Collect static files
python manage.py createsuperuser        # Create admin user
```

### Bots
```bash
python manage.py admin_bot              # Start admin bot  
python manage.py admin_bot --configure  # Show configuration
python manage.py admin_bot --test       # Test notifications
python manage.py run_bots               # Start customer bots
```

### Production (Supervisor)
```bash
sudo supervisorctl status               # Check all services
sudo supervisorctl restart all          # Restart all
sudo supervisorctl restart wemard       # Restart Django
sudo supervisorctl restart wowdash-bots # Restart customer bots
sudo supervisorctl restart multilang-admin-bot # Restart admin bot
```

**See [docs/SERVER_COMMANDS.md](docs/SERVER_COMMANDS.md) for complete reference.**

---

## 🚀 Deployment Workflow

```bash
# 1. Backup
pg_dump dbname > backup.sql

# 2. Pull changes
git pull origin main

# 3. Update
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput

# 4. Restart
sudo supervisorctl restart all

# 5. Verify
sudo supervisorctl status
```

---

## 🆘 Troubleshooting

### Check Service Status
```bash
sudo supervisorctl status
```

### View Logs
```bash
sudo tail -f /var/log/supervisor/wemard.log
sudo tail -f /var/log/supervisor/multilang-admin-bot.log
```

### Test Manually
```bash
cd /home/wemard/app
source venv/bin/activate
python manage.py COMMAND
```

**See [SERVER_COMMANDS.md](SERVER_COMMANDS.md#troubleshooting) for detailed troubleshooting.**

---

## 📞 Support

- **Admin Bot:** Send `/help` to `@uzmultilang_bot`
- **Email:** go.multilang@gmail.com
- **Phone:** +998(90)-029-01-19

---

## 📄 License

Proprietary - © 2026 MultiLang

---

**For detailed documentation, see [docs/](docs/) folder.**
