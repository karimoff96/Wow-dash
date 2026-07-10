# Admin Bot Complete Guide (@uzmultilang_bot)

Complete guide for admin notification bot setup, testing, and deployment.

---

## Overview

The admin bot (`@uzmultilang_bot`) sends notifications to administrators for:
- 📧 **Contact form submissions** from landing page
- 🔄 **Subscription renewal requests** from customers

**Features:**
- ✅ Multiple recipients (users, channels, groups)
- ✅ Interactive commands (`/start`, `/myid`, `/status`)
- ✅ Auto-reconnect on network errors
- ✅ Runs 24/7 alongside Django and customer bots

---

## Quick Start

### 1. Get Your Telegram ID

**For User ID:**
- Open Telegram, search `@userinfobot`, send any message
- Or send `/myid` to `@uzmultilang_bot`

**For Channel/Group ID:**
- Add `@uzmultilang_bot` as administrator to channel/group
- Forward any message from channel to `@userinfobot`
- ID will be negative (e.g., `-1001234567890`)

### 2. Configure Admin IDs

Edit `.env` file:
```bash
# Single recipient
ADMIN_TELEGRAM_ID=123456789

# Multiple recipients (comma-separated)
ADMIN_TELEGRAM_ID=123456789,987654321,-1001234567890
```

Or edit `bot/admin_bot_service.py` line ~43:
```python
ADMIN_TELEGRAM_ID = ADMIN_TELEGRAM_ID or "123456789,987654321"
```

### 3. Test Configuration

```bash
# Show configuration
python manage.py admin_bot --configure

# Send test notification
python manage.py admin_bot --test

# Test contact form notification
python manage.py test_contact_notification

# Test channel access
python manage.py test_channel_access -1003856186766 --send-test
```

### 4. Deploy to Production

**Ubuntu Server with Supervisor:**
```bash
# Copy config
sudo cp multilang-admin-bot.conf /etc/supervisor/conf.d/

# Start service
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start multilang-admin-bot

# Check status
sudo supervisorctl status multilang-admin-bot

# View logs
sudo tail -f /var/log/supervisor/multilang-admin-bot.log
```

---

## Bot Commands

Users can interact with `@uzmultilang_bot`:

### For Everyone:
- `/start` - Welcome message + show your Telegram ID
- `/help` - Show available commands
- `/myid` - Get your Telegram ID for configuration

### For Admins Only:
- `/status` - View bot configuration and recipient list

---

## Development Testing

### Run Bot Locally

```bash
# Start bot (blocking, shows logs in console)
python manage.py admin_bot
# Press Ctrl+C to stop

# In another terminal, run Django
python manage.py runserver
```

Both must run simultaneously for full functionality.

### Test Notifications

**1. Test directly:**
```bash
python manage.py test_contact_notification
```

**2. Test via landing page:**
- Open `http://localhost:8000/landing/`
- Submit contact form
- Check Telegram for notification

**3. Test renewal request:**
- Login as organization owner
- Request subscription renewal
- Check Telegram for notification

---

## Production Deployment (Ubuntu)

### Prerequisites

✅ Ubuntu server with Django app running
✅ Supervisor installed
✅ Admin bot tested locally
✅ `ADMIN_TELEGRAM_ID` configured

### Deployment Steps

**1. Test on server first:**
```bash
cd /home/wemard/app
source venv/bin/activate
python manage.py admin_bot --test
```

**2. Copy supervisor config:**
```bash
sudo cp multilang-admin-bot.conf /etc/supervisor/conf.d/
```

**3. Start service:**
```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start multilang-admin-bot
```

**4. Verify:**
```bash
# Check status
sudo supervisorctl status multilang-admin-bot

# View logs
sudo tail -f /var/log/supervisor/multilang-admin-bot.log

# Test on Telegram
# Send /start to @uzmultilang_bot
```

### Control Commands

```bash
# Start
sudo supervisorctl start multilang-admin-bot

# Stop
sudo supervisorctl stop multilang-admin-bot

# Restart (after code changes)
sudo supervisorctl restart multilang-admin-bot

# Status
sudo supervisorctl status multilang-admin-bot

# View logs live
sudo tail -f /var/log/supervisor/multilang-admin-bot.log

# View error logs
sudo tail -f /var/log/supervisor/multilang-admin-bot-error.log
```

---

## Configuration Files

### Supervisor Config

**Location:** `/etc/supervisor/conf.d/multilang-admin-bot.conf`

```ini
[program:multilang-admin-bot]
command=/home/wemard/app/venv/bin/python manage.py admin_bot
directory=/home/wemard/app
user=wemard
autostart=true
autorestart=true
startsecs=10
redirect_stderr=true
stdout_logfile=/var/log/supervisor/multilang-admin-bot.log
environment=PATH="/home/wemard/app/venv/bin",DJANGO_SETTINGS_MODULE="WowDash.settings"
```

**Key Settings:**
- Auto-starts on server boot (`autostart=true`)
- Auto-restarts on crash (`autorestart=true`)
- Logs to `/var/log/supervisor/multilang-admin-bot.log`
- Runs as `wemard` user

### Environment Variables

**`.env` file:**
```bash
# Required - comma-separated IDs
ADMIN_TELEGRAM_ID=123456789,987654321,-1001234567890

# Required - obtain this from BotFather; never commit the real value
ADMIN_BOT_TOKEN=123456789:replace-with-secret-token
```

**Supported formats:**
- Single ID: `"123456789"`
- Multiple IDs: `"123,456,789"`
- List: `[123, 456, 789]`
- Channel IDs are negative: `"-1001234567890"`

---

## Production Architecture

```
Ubuntu Server
├── Django App (wemard)                    ← Web interface
│   └── Supervisor: wemard.conf
│
├── Customer Bots (wowdash-bots)          ← Translation center bots
│   └── Supervisor: wowdash-bots.conf
│
└── Admin Bot (multilang-admin-bot)       ← Notification bot
    └── Supervisor: multilang-admin-bot.conf

All managed via: sudo supervisorctl status
```

---

## Troubleshooting

### Bot Not Starting

**Check configuration:**
```bash
cd /home/wemard/app
source venv/bin/activate
python manage.py admin_bot --configure
```

**Check logs:**
```bash
sudo tail -f /var/log/supervisor/multilang-admin-bot.log
```

**Common issues:**
- ❌ `ADMIN_TELEGRAM_ID` not set → Check `.env` file
- ❌ Bot token missing → Check `bot/admin_bot_service.py` line 35
- ❌ Import errors → Run `pip install -r requirements.txt`

### Bot Doesn't Respond on Telegram

**1. Check bot is running:**
```bash
ps aux | grep admin_bot
sudo supervisorctl status multilang-admin-bot
```

**2. Test manually:**
```bash
# Stop supervisor process
sudo supervisorctl stop multilang-admin-bot

# Run manually to see errors
cd /home/wemard/app
source venv/bin/activate
python manage.py admin_bot
# Press Ctrl+C to stop

# Start supervisor again
sudo supervisorctl start multilang-admin-bot
```

**3. Check bot token:**
```bash
python manage.py admin_bot --configure
```

### Notifications Not Received

**Check Django is calling notification:**
```bash
cd /home/wemard/app
grep -r "send_contact_request_notification" landing/views.py
grep -r "send_renewal_request_notification" billing/views.py
```

**Check admin IDs configured:**
```bash
source venv/bin/activate
python -c "from bot.admin_bot_service import ADMIN_TELEGRAM_IDS; print(ADMIN_TELEGRAM_IDS)"
```

**Test manually:**
```bash
python manage.py test_contact_notification
```

**Check both services running:**
```bash
sudo supervisorctl status
# Should show both wemard and multilang-admin-bot as RUNNING
```

### Channel Notifications Fail

**Error: "chat not found"**

**Solution 1: Activate bot in channel**
- Go to channel
- Type: `@uzmultilang_bot hello`
- This activates bot connection

**Solution 2: Re-add bot**
- Remove `@uzmultilang_bot` from channel admins
- Add back as administrator
- Grant "Post Messages" permission

**Solution 3: Verify channel ID**
```bash
python manage.py test_channel_access -1003856186766
```

**Solution 4: Check bot permissions**
```bash
python manage.py test_channel_access -1003856186766 --send-test
```

---

## After Code Updates

When you update bot code or Django app:

```bash
# 1. Pull changes
cd /home/wemard/app
git pull origin main

# 2. Activate venv
source venv/bin/activate

# 3. Install dependencies (if changed)
pip install -r requirements.txt

# 4. Run migrations (if any)
python manage.py migrate

# 5. Restart admin bot
sudo supervisorctl restart multilang-admin-bot

# 6. Restart Django
sudo supervisorctl restart wemard

# 7. Check status
sudo supervisorctl status
```

---

## Monitoring

### Check Health

```bash
# Quick status
sudo supervisorctl status multilang-admin-bot

# Detailed process info
ps aux | grep admin_bot

# Check uptime
sudo supervisorctl status | grep multilang
```

### Monitor Logs

```bash
# Live log monitoring
sudo tail -f /var/log/supervisor/multilang-admin-bot.log

# Last 100 lines
sudo tail -n 100 /var/log/supervisor/multilang-admin-bot.log

# Search for errors
sudo grep -i error /var/log/supervisor/multilang-admin-bot.log

# Check recent start
sudo grep "Starting bot" /var/log/supervisor/multilang-admin-bot.log | tail -5
```

### Test Interactively

Send to `@uzmultilang_bot`:
- `/start` → Should respond immediately
- `/myid` → Should show your ID
- `/status` → Should show config (if admin)

---

## Security

✅ Bot runs as `wemard` user (not root)
✅ Bot token hardcoded in service file 
✅ Admin IDs in `.env` (not in public repo)
✅ Logs rotated automatically
✅ Resource limits set (512MB memory)
✅ Auto-restart on failure

---

## Performance

**Resource Usage:**
- Memory: ~50-100MB (idle), ~200MB (peak)
- CPU: <1% (mostly idle)
- Network: Minimal (only on messages)

**Capacity:**
- 30 updates/second (Telegram API limit)
- Hundreds of notifications per day
- No impact on Django app

---

## Management Commands

| Command | Purpose |
|---------|---------|
| `python manage.py admin_bot` | Start bot (development) |
| `python manage.py admin_bot --configure` | Show configuration |
| `python manage.py admin_bot --test` | Test with notification |
| `python manage.py test_contact_notification` | Test contact form notification |
| `python manage.py test_channel_access ID` | Test channel/group access |
| `python manage.py test_channel_access ID --send-test` | Test + send message |

---

## Quick Reference

### Local Testing
```bash
python manage.py admin_bot
```

### Production Deploy
```bash
sudo cp multilang-admin-bot.conf /etc/supervisor/conf.d/
sudo supervisorctl reread && sudo supervisorctl update
sudo supervisorctl start multilang-admin-bot
```

### Check Status
```bash
sudo supervisorctl status multilang-admin-bot
```

### View Logs
```bash
sudo tail -f /var/log/supervisor/multilang-admin-bot.log
```

### Restart After Changes
```bash
sudo supervisorctl restart multilang-admin-bot
```

### Test Configuration
```bash
python manage.py admin_bot --test
```

---

## Getting Help

**Check bot status:**
```bash
sudo supervisorctl status multilang-admin-bot
```

**View recent errors:**
```bash
sudo tail -n 50 /var/log/supervisor/multilang-admin-bot.log
```

**Test manually:**
```bash
cd /home/wemard/app && source venv/bin/activate
python manage.py admin_bot
```

**Verify config:**
```bash
python manage.py admin_bot --configure
```

---

**Bot now runs 24/7 on production!** 🎉  
Users can interact with `@uzmultilang_bot` anytime.
