# Sportsbook Agent Management System

Web-based management dashboard for sportsbook agents. Scrapes player data from allagentreports.com, tracks sub-agents and players, automates weekly settlements, and sends Telegram alerts.

## Features

- **Player & Sub-Agent Management** — hierarchical view with credit limits, balances, status tracking
- **Auto-Scraping** — pulls data from allagentreports.com on a schedule
- **Weekly Settlements (Payday Engine)** — auto-calculates what everyone owes, generates PDF reports
- **Telegram Bot** — alerts for thresholds, settlement summaries, bot commands
- **Color-Coded Dashboard** — green (they owe you), red (you owe them), yellow (near credit limit)
- **Mobile Responsive** — works on phone browsers

## Quick Setup

### 1. Clone the repo

```bash
git clone https://github.com/ethanstogsdill-hash/book.git
cd book
```

### 2. Create virtual environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
playwright install chromium
```

### 4. Configure environment

```bash
cp .env.example .env
```

Edit `.env` with your actual credentials:
- `SITE_USERNAME` / `SITE_PASSWORD` — your allagentreports.com login
- `TELEGRAM_BOT_TOKEN` — from @BotFather (see below)
- `TELEGRAM_CHAT_ID` — your personal chat ID
- `APP_USERNAME` / `APP_PASSWORD` — app login (change from defaults)

### 5. Run the app

```bash
python run.py
```

Visit `http://localhost:8000` in your browser. Login with the credentials you set in `.env`.

## Telegram Bot Setup

### Create a bot

1. Open Telegram and search for **@BotFather**
2. Send `/newbot`
3. Choose a name (e.g., "My Book Bot")
4. Choose a username (e.g., "mybook_alerts_bot")
5. BotFather will give you a **token** — copy it to `TELEGRAM_BOT_TOKEN` in `.env`

### Get your Chat ID

1. Send any message to your new bot in Telegram
2. Visit this URL in your browser (replace `<TOKEN>` with your bot token):
   ```
   https://api.telegram.org/bot<TOKEN>/getUpdates
   ```
3. Find `"chat":{"id":123456789}` in the response — that number is your chat ID
4. Copy it to `TELEGRAM_CHAT_ID` in `.env`

### Get sub-agent Chat IDs

For each sub-agent who should receive settlement messages:
1. Have them message your bot
2. Check `/getUpdates` again to find their chat ID
3. Add it to the sub-agent's profile in the app settings

## Bot Commands

Once running, you can text your bot:
- `/balance <name>` — check a player or sub-agent's balance
- `/week` — get this week's summary
- `/status` — last scrape time and system status

## Requirements

- Python 3.10+
- Google Chrome (for scraping — must be installed at default location)
- Internet connection (for scraping and Telegram)

## File Structure

```
book/
├── run.py              # Start the app
├── scrape_worker.py    # Playwright scraper (standalone)
├── app/
│   ├── main.py         # FastAPI application
│   ├── database.py     # SQLite schema & queries
│   ├── routers/        # API endpoints
│   ├── services/       # Business logic (scraper, payday, telegram)
│   └── static/         # Frontend (HTML/CSS/JS)
├── data/               # Database & Chrome profile (gitignored)
├── .env                # Your credentials (gitignored)
└── .env.example        # Template for .env
```
