"""SQLite database: schema initialization and all CRUD operations."""
import aiosqlite
import json
from datetime import datetime
from app.config import settings
from app.auth import hash_password

DB_PATH = settings.db_path

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    expires_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS sub_agents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    username TEXT UNIQUE,
    phone TEXT DEFAULT '',
    telegram_chat_id TEXT DEFAULT '',
    telegram_username TEXT DEFAULT '',
    venmo TEXT DEFAULT '',
    credit_limit REAL DEFAULT 0,
    balance REAL DEFAULT 0,
    status TEXT DEFAULT 'active',
    vig_split REAL DEFAULT 0,
    notes TEXT DEFAULT '',
    date_added TEXT DEFAULT (datetime('now')),
    last_updated TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS players (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id TEXT UNIQUE NOT NULL,
    name TEXT DEFAULT '',
    phone TEXT DEFAULT '',
    sub_agent_id INTEGER,
    credit_limit REAL DEFAULT 0,
    balance REAL DEFAULT 0,
    win_loss REAL DEFAULT 0,
    action REAL DEFAULT 0,
    status TEXT DEFAULT 'active',
    notes TEXT DEFAULT '',
    raw_data TEXT DEFAULT '{}',
    date_added TEXT DEFAULT (datetime('now')),
    last_scraped_at TEXT,
    FOREIGN KEY (sub_agent_id) REFERENCES sub_agents(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS bets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id TEXT UNIQUE,
    player_id TEXT NOT NULL,
    player_db_id INTEGER,
    placed_at TEXT,
    sport TEXT DEFAULT '',
    description TEXT DEFAULT '',
    bet_type TEXT DEFAULT '',
    risk REAL DEFAULT 0,
    win_amount REAL DEFAULT 0,
    result TEXT DEFAULT 'pending',
    raw_data TEXT DEFAULT '{}',
    scraped_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (player_db_id) REFERENCES players(id)
);

CREATE TABLE IF NOT EXISTS weekly_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER,
    sub_agent_id INTEGER,
    week_ending TEXT NOT NULL,
    won_lost REAL DEFAULT 0,
    vig REAL DEFAULT 0,
    net REAL DEFAULT 0,
    settled INTEGER DEFAULT 0,
    scraped_at TEXT,
    FOREIGN KEY (player_id) REFERENCES players(id),
    FOREIGN KEY (sub_agent_id) REFERENCES sub_agents(id),
    UNIQUE(player_id, sub_agent_id, week_ending)
);

CREATE TABLE IF NOT EXISTS settlements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    week_ending TEXT NOT NULL,
    counterparty_type TEXT NOT NULL,
    counterparty_id INTEGER,
    counterparty_name TEXT DEFAULT '',
    amount REAL NOT NULL,
    direction TEXT NOT NULL,
    vig_amount REAL DEFAULT 0,
    status TEXT DEFAULT 'pending',
    payment_method TEXT DEFAULT '',
    notes TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now')),
    settled_at TEXT
);

CREATE TABLE IF NOT EXISTS live_bets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bet_id TEXT UNIQUE,
    player_name TEXT DEFAULT '',
    player_account TEXT DEFAULT '',
    sub_agent_name TEXT DEFAULT '',
    description TEXT DEFAULT '',
    amount REAL DEFAULT 0,
    odds TEXT DEFAULT '',
    potential_payout REAL DEFAULT 0,
    time_placed TEXT DEFAULT '',
    status TEXT DEFAULT 'open',
    sport TEXT DEFAULT '',
    bet_type TEXT DEFAULT '',
    raw_data TEXT DEFAULT '{}',
    scraped_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS alerts_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT DEFAULT (datetime('now')),
    alert_type TEXT NOT NULL,
    message TEXT NOT NULL,
    related_id INTEGER,
    related_type TEXT,
    sent_via_telegram INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS scrape_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_type TEXT NOT NULL,
    status TEXT NOT NULL,
    message TEXT,
    records_affected INTEGER DEFAULT 0,
    duration_seconds REAL DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT DEFAULT (datetime('now'))
);
"""

DEFAULT_SETTINGS = {
    "balance_alert_threshold": "1000",
    "credit_limit_warning_pct": "80",
    "sub_agent_book_threshold": "5000",
    "telegram_alerts_enabled": "true",
    "auto_scrape_interval_min": "60",
    "default_vig_rate": "10",
    "backer_vig_split": "50",
    "payday_hour": "9",
}


async def get_db():
    """Open a connection with WAL mode."""
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    return db


async def init_db():
    """Create tables, seed default user and settings."""
    db = await get_db()
    try:
        await db.executescript(SCHEMA)

        # Migrate: add new columns if missing
        for col, default in [("telegram_username", "''"), ("venmo", "''")]:
            try:
                await db.execute(f"ALTER TABLE sub_agents ADD COLUMN {col} TEXT DEFAULT {default}")
                print(f"[INIT] Added column sub_agents.{col}")
            except Exception:
                pass  # Column already exists

        # Seed default user if none exists
        cur = await db.execute("SELECT COUNT(*) FROM users")
        count = (await cur.fetchone())[0]
        if count == 0:
            pw_hash = hash_password(settings.app_password)
            await db.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (settings.app_username, pw_hash),
            )
            print(f"[INIT] Default user created: {settings.app_username}")

        # Seed default settings
        for key, value in DEFAULT_SETTINGS.items():
            await db.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                (key, value),
            )

        await db.commit()
    finally:
        await db.close()


# ─── Settings ──────────────────────────────────────────────

async def get_all_settings(db) -> dict:
    cur = await db.execute("SELECT key, value FROM settings")
    rows = await cur.fetchall()
    return {r["key"]: r["value"] for r in rows}


async def get_setting(db, key: str, default: str = "") -> str:
    cur = await db.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = await cur.fetchone()
    return row["value"] if row else default


async def update_settings(db, updates: dict):
    for key, value in updates.items():
        await db.execute(
            "INSERT INTO settings (key, value, updated_at) VALUES (?, ?, datetime('now')) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
            (key, str(value)),
        )
    await db.commit()


# ─── Sub-Agents ──────────────────────────────────────────────

async def get_sub_agents(db):
    cur = await db.execute(
        "SELECT sa.*, "
        "(SELECT COUNT(*) FROM players p WHERE p.sub_agent_id = sa.id) as player_count, "
        "(SELECT COALESCE(SUM(p.balance), 0) FROM players p WHERE p.sub_agent_id = sa.id) as total_book, "
        "(SELECT COALESCE(SUM(p.win_loss), 0) FROM players p WHERE p.sub_agent_id = sa.id) as total_win_loss "
        "FROM sub_agents sa ORDER BY sa.name"
    )
    return [dict(r) for r in await cur.fetchall()]


async def get_sub_agent(db, sub_id: int):
    cur = await db.execute(
        "SELECT sa.*, "
        "(SELECT COUNT(*) FROM players p WHERE p.sub_agent_id = sa.id) as player_count, "
        "(SELECT COALESCE(SUM(p.balance), 0) FROM players p WHERE p.sub_agent_id = sa.id) as total_book, "
        "(SELECT COALESCE(SUM(p.win_loss), 0) FROM players p WHERE p.sub_agent_id = sa.id) as total_win_loss "
        "FROM sub_agents sa WHERE sa.id = ?",
        (sub_id,),
    )
    row = await cur.fetchone()
    return dict(row) if row else None


async def get_sub_agent_by_username(db, username: str):
    cur = await db.execute("SELECT * FROM sub_agents WHERE username = ?", (username,))
    row = await cur.fetchone()
    return dict(row) if row else None


async def create_sub_agent(db, data: dict) -> int:
    cur = await db.execute(
        "INSERT INTO sub_agents (name, username, phone, telegram_chat_id, telegram_username, venmo, credit_limit, status, vig_split, notes) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            data.get("name", ""),
            data.get("username"),
            data.get("phone", ""),
            data.get("telegram_chat_id", ""),
            data.get("telegram_username", ""),
            data.get("venmo", ""),
            data.get("credit_limit", 0),
            data.get("status", "active"),
            data.get("vig_split", 0),
            data.get("notes", ""),
        ),
    )
    await db.commit()
    return cur.lastrowid


async def update_sub_agent(db, sub_id: int, data: dict):
    fields = []
    values = []
    allowed = ["name", "username", "phone", "telegram_chat_id", "telegram_username",
               "venmo", "credit_limit", "balance", "status", "vig_split", "notes"]
    for key in allowed:
        if key in data:
            fields.append(f"{key} = ?")
            values.append(data[key])
    if not fields:
        return
    fields.append("last_updated = datetime('now')")
    values.append(sub_id)
    await db.execute(
        f"UPDATE sub_agents SET {', '.join(fields)} WHERE id = ?", values
    )
    await db.commit()


# ─── Players ──────────────────────────────────────────────

async def get_players(db, search: str = None, status: str = None,
                      sub_agent_id: int = None, sort_by: str = "name",
                      sort_dir: str = "asc"):
    query = (
        "SELECT p.*, sa.name as sub_agent_name "
        "FROM players p LEFT JOIN sub_agents sa ON p.sub_agent_id = sa.id "
        "WHERE 1=1"
    )
    params = []

    if search:
        query += " AND (p.name LIKE ? OR p.account_id LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])
    if status:
        query += " AND p.status = ?"
        params.append(status)
    if sub_agent_id is not None:
        if sub_agent_id == 0:
            query += " AND p.sub_agent_id IS NULL"
        else:
            query += " AND p.sub_agent_id = ?"
            params.append(sub_agent_id)

    allowed_sorts = ["name", "account_id", "balance", "win_loss", "credit_limit", "status", "action"]
    if sort_by not in allowed_sorts:
        sort_by = "name"
    direction = "DESC" if sort_dir.lower() == "desc" else "ASC"
    query += f" ORDER BY p.{sort_by} {direction}"

    cur = await db.execute(query, params)
    return [dict(r) for r in await cur.fetchall()]


async def get_player(db, player_id: int):
    cur = await db.execute(
        "SELECT p.*, sa.name as sub_agent_name "
        "FROM players p LEFT JOIN sub_agents sa ON p.sub_agent_id = sa.id "
        "WHERE p.id = ?",
        (player_id,),
    )
    row = await cur.fetchone()
    return dict(row) if row else None


async def get_player_by_account_id(db, account_id: str):
    cur = await db.execute("SELECT * FROM players WHERE account_id = ?", (account_id,))
    row = await cur.fetchone()
    return dict(row) if row else None


async def create_player(db, data: dict) -> int:
    cur = await db.execute(
        "INSERT INTO players (account_id, name, phone, sub_agent_id, credit_limit, "
        "balance, win_loss, action, status, notes, raw_data, last_scraped_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            data["account_id"],
            data.get("name", ""),
            data.get("phone", ""),
            data.get("sub_agent_id"),
            data.get("credit_limit", 0),
            data.get("balance", 0),
            data.get("win_loss", 0),
            data.get("action", 0),
            data.get("status", "active"),
            data.get("notes", ""),
            json.dumps(data.get("raw_data", {})),
            data.get("last_scraped_at"),
        ),
    )
    await db.commit()
    return cur.lastrowid


async def update_player(db, player_id: int, data: dict):
    fields = []
    values = []
    allowed = ["name", "phone", "sub_agent_id", "credit_limit", "balance",
               "win_loss", "action", "status", "notes", "raw_data", "last_scraped_at"]
    for key in allowed:
        if key in data:
            fields.append(f"{key} = ?")
            val = data[key]
            if key == "raw_data" and isinstance(val, dict):
                val = json.dumps(val)
            values.append(val)
    if not fields:
        return
    values.append(player_id)
    await db.execute(
        f"UPDATE players SET {', '.join(fields)} WHERE id = ?", values
    )
    await db.commit()


async def upsert_players(db, players_data: list, site_username: str):
    """Upsert scraped player data, auto-creating sub-agents as needed."""
    now = datetime.utcnow().isoformat()
    count = 0
    for p in players_data:
        account_id = p.get("account_id", "")
        agent_name = p.get("agent_name", "")

        # Determine sub_agent_id
        sub_agent_id = None
        if agent_name and agent_name.upper() != site_username.upper():
            sa = await get_sub_agent_by_username(db, agent_name)
            if not sa:
                sub_agent_id = await create_sub_agent(db, {
                    "name": agent_name,
                    "username": agent_name,
                })
            else:
                sub_agent_id = sa["id"]

        existing = await get_player_by_account_id(db, account_id)
        if existing:
            await update_player(db, existing["id"], {
                "win_loss": p.get("win_loss", 0),
                "balance": p.get("balance", 0),
                "action": p.get("action", 0),
                "raw_data": p.get("raw_data", {}),
                "last_scraped_at": now,
                "sub_agent_id": sub_agent_id,
            })
        else:
            await create_player(db, {
                "account_id": account_id,
                "name": p.get("name", account_id),
                "win_loss": p.get("win_loss", 0),
                "balance": p.get("balance", 0),
                "action": p.get("action", 0),
                "sub_agent_id": sub_agent_id,
                "raw_data": p.get("raw_data", {}),
                "last_scraped_at": now,
            })
        count += 1

    # Update sub-agent balances
    await db.execute(
        "UPDATE sub_agents SET balance = ("
        "  SELECT COALESCE(SUM(p.balance), 0) FROM players p WHERE p.sub_agent_id = sub_agents.id"
        "), last_updated = datetime('now')"
    )
    await db.commit()
    return count


# ─── Bets ──────────────────────────────────────────────

async def upsert_bets(db, wagers: list):
    """Insert new bets, skip duplicates by ticket_id."""
    new_count = 0
    for w in wagers:
        ticket_id = w.get("ticket_id", "")
        if not ticket_id:
            continue
        cur = await db.execute("SELECT id FROM bets WHERE ticket_id = ?", (ticket_id,))
        if await cur.fetchone():
            # Update result if changed
            await db.execute(
                "UPDATE bets SET result = ? WHERE ticket_id = ?",
                (w.get("result", "pending"), ticket_id),
            )
            continue

        # Link to player
        player_db_id = None
        player_id = w.get("player_id", "")
        if player_id:
            p = await get_player_by_account_id(db, player_id)
            if p:
                player_db_id = p["id"]

        await db.execute(
            "INSERT INTO bets (ticket_id, player_id, player_db_id, placed_at, sport, "
            "description, bet_type, risk, win_amount, result, raw_data) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                ticket_id,
                player_id,
                player_db_id,
                w.get("placed_at", ""),
                w.get("sport", ""),
                w.get("description", ""),
                w.get("bet_type", ""),
                w.get("risk", 0),
                w.get("win_amount", 0),
                w.get("result", "pending"),
                json.dumps(w.get("raw_data", {})),
            ),
        )
        new_count += 1
    await db.commit()
    return new_count


async def get_bets(db, player_id: str = None, sport: str = None,
                   result: str = None, limit: int = 100, offset: int = 0):
    query = (
        "SELECT b.*, p.name as player_name, sa.name as sub_agent_name "
        "FROM bets b "
        "LEFT JOIN players p ON b.player_db_id = p.id "
        "LEFT JOIN sub_agents sa ON p.sub_agent_id = sa.id "
        "WHERE 1=1"
    )
    params = []
    if player_id:
        query += " AND b.player_id = ?"
        params.append(player_id)
    if sport:
        query += " AND b.sport = ?"
        params.append(sport)
    if result:
        query += " AND b.result = ?"
        params.append(result)
    query += " ORDER BY b.placed_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    cur = await db.execute(query, params)
    return [dict(r) for r in await cur.fetchall()]


async def get_bet_stats(db):
    cur = await db.execute(
        "SELECT "
        "COUNT(*) as total, "
        "SUM(CASE WHEN result='pending' THEN 1 ELSE 0 END) as pending, "
        "SUM(CASE WHEN result='win' THEN 1 ELSE 0 END) as wins, "
        "SUM(CASE WHEN result='loss' THEN 1 ELSE 0 END) as losses, "
        "SUM(risk) as total_risk, "
        "SUM(win_amount) as total_win_amount "
        "FROM bets"
    )
    return dict(await cur.fetchone())


async def get_bet_sports(db):
    cur = await db.execute("SELECT DISTINCT sport FROM bets WHERE sport != '' ORDER BY sport")
    return [r["sport"] for r in await cur.fetchall()]


# ─── Weekly Results ──────────────────────────────────────────────

async def upsert_weekly_result(db, data: dict):
    await db.execute(
        "INSERT INTO weekly_results (player_id, sub_agent_id, week_ending, won_lost, vig, net, scraped_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(player_id, sub_agent_id, week_ending) DO UPDATE SET "
        "won_lost = excluded.won_lost, vig = excluded.vig, net = excluded.net, scraped_at = excluded.scraped_at",
        (
            data.get("player_id"),
            data.get("sub_agent_id"),
            data["week_ending"],
            data.get("won_lost", 0),
            data.get("vig", 0),
            data.get("net", 0),
            datetime.utcnow().isoformat(),
        ),
    )
    await db.commit()


async def get_weekly_results(db, week_ending: str):
    cur = await db.execute(
        "SELECT wr.*, p.account_id as player_account, p.name as player_name, "
        "sa.name as sub_agent_name "
        "FROM weekly_results wr "
        "LEFT JOIN players p ON wr.player_id = p.id "
        "LEFT JOIN sub_agents sa ON wr.sub_agent_id = sa.id "
        "WHERE wr.week_ending = ? ORDER BY sa.name, p.name",
        (week_ending,),
    )
    return [dict(r) for r in await cur.fetchall()]


async def get_available_weeks(db):
    cur = await db.execute(
        "SELECT DISTINCT week_ending FROM weekly_results ORDER BY week_ending DESC"
    )
    return [r["week_ending"] for r in await cur.fetchall()]


async def get_player_history(db, player_id: int):
    cur = await db.execute(
        "SELECT * FROM weekly_results WHERE player_id = ? ORDER BY week_ending DESC",
        (player_id,),
    )
    return [dict(r) for r in await cur.fetchall()]


# ─── Settlements ──────────────────────────────────────────────

async def create_settlement(db, data: dict) -> int:
    cur = await db.execute(
        "INSERT INTO settlements (week_ending, counterparty_type, counterparty_id, "
        "counterparty_name, amount, direction, vig_amount, status, notes) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            data["week_ending"],
            data["counterparty_type"],
            data.get("counterparty_id"),
            data.get("counterparty_name", ""),
            data["amount"],
            data["direction"],
            data.get("vig_amount", 0),
            data.get("status", "pending"),
            data.get("notes", ""),
        ),
    )
    await db.commit()
    return cur.lastrowid


async def get_settlements(db, week_ending: str = None, status: str = None):
    query = "SELECT * FROM settlements WHERE 1=1"
    params = []
    if week_ending:
        query += " AND week_ending = ?"
        params.append(week_ending)
    if status:
        query += " AND status = ?"
        params.append(status)
    query += " ORDER BY created_at DESC"
    cur = await db.execute(query, params)
    return [dict(r) for r in await cur.fetchall()]


async def get_settlement(db, settlement_id: int):
    cur = await db.execute("SELECT * FROM settlements WHERE id = ?", (settlement_id,))
    row = await cur.fetchone()
    return dict(row) if row else None


async def update_settlement(db, settlement_id: int, data: dict):
    fields = []
    values = []
    allowed = ["status", "payment_method", "notes", "settled_at"]
    for key in allowed:
        if key in data:
            fields.append(f"{key} = ?")
            values.append(data[key])
    if not fields:
        return
    values.append(settlement_id)
    await db.execute(
        f"UPDATE settlements SET {', '.join(fields)} WHERE id = ?", values
    )
    await db.commit()


async def get_settlement_weeks(db):
    cur = await db.execute(
        "SELECT DISTINCT week_ending FROM settlements ORDER BY week_ending DESC"
    )
    return [r["week_ending"] for r in await cur.fetchall()]


# ─── Alerts ──────────────────────────────────────────────

async def log_alert(db, alert_type: str, message: str,
                    related_id: int = None, related_type: str = None,
                    sent_via_telegram: bool = False):
    await db.execute(
        "INSERT INTO alerts_log (alert_type, message, related_id, related_type, sent_via_telegram) "
        "VALUES (?, ?, ?, ?, ?)",
        (alert_type, message, related_id, related_type, 1 if sent_via_telegram else 0),
    )
    await db.commit()


async def get_alerts(db, limit: int = 50, alert_type: str = None):
    query = "SELECT * FROM alerts_log WHERE 1=1"
    params = []
    if alert_type:
        query += " AND alert_type = ?"
        params.append(alert_type)
    query += " ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)
    cur = await db.execute(query, params)
    return [dict(r) for r in await cur.fetchall()]


# ─── Scrape Log ──────────────────────────────────────────────

async def log_scrape(db, run_type: str, status: str, message: str = "",
                     records_affected: int = 0, duration: float = 0):
    await db.execute(
        "INSERT INTO scrape_log (run_type, status, message, records_affected, duration_seconds) "
        "VALUES (?, ?, ?, ?, ?)",
        (run_type, status, message, records_affected, duration),
    )
    await db.commit()


async def get_scrape_logs(db, limit: int = 20):
    cur = await db.execute(
        "SELECT * FROM scrape_log ORDER BY created_at DESC LIMIT ?", (limit,)
    )
    return [dict(r) for r in await cur.fetchall()]


async def get_last_scrape(db):
    cur = await db.execute(
        "SELECT * FROM scrape_log WHERE status = 'success' ORDER BY created_at DESC LIMIT 1"
    )
    row = await cur.fetchone()
    return dict(row) if row else None


# ─── Dashboard ──────────────────────────────────────────────

async def get_dashboard_summary(db):
    summary = {}

    cur = await db.execute("SELECT COUNT(*) as c FROM players WHERE status != 'inactive'")
    summary["total_players"] = (await cur.fetchone())["c"]

    cur = await db.execute("SELECT COUNT(*) as c FROM sub_agents WHERE status != 'inactive'")
    summary["total_sub_agents"] = (await cur.fetchone())["c"]

    cur = await db.execute("SELECT COUNT(*) as c FROM players WHERE status = 'flagged'")
    summary["flagged_players"] = (await cur.fetchone())["c"]

    cur = await db.execute("SELECT COALESCE(SUM(balance), 0) as s FROM players")
    summary["total_outstanding"] = (await cur.fetchone())["s"]

    cur = await db.execute("SELECT COALESCE(SUM(win_loss), 0) as s FROM players")
    summary["net_position"] = (await cur.fetchone())["s"]

    cur = await db.execute(
        "SELECT COALESCE(SUM(balance), 0) as s FROM players WHERE balance > 0"
    )
    summary["total_owed_to_me"] = (await cur.fetchone())["s"]

    cur = await db.execute(
        "SELECT COALESCE(SUM(balance), 0) as s FROM players WHERE balance < 0"
    )
    summary["total_i_owe"] = (await cur.fetchone())["s"]

    last_scrape = await get_last_scrape(db)
    summary["last_scrape"] = last_scrape["created_at"] if last_scrape else None

    return summary


# ─── User management ──────────────────────────────────────────────

async def get_user_by_username(db, username: str):
    cur = await db.execute("SELECT * FROM users WHERE username = ?", (username,))
    row = await cur.fetchone()
    return dict(row) if row else None


async def update_user_password(db, user_id: int, password_hash: str):
    await db.execute(
        "UPDATE users SET password_hash = ? WHERE id = ?",
        (password_hash, user_id),
    )
    await db.commit()


# ─── Live Bets ──────────────────────────────────────────────

async def upsert_live_bets(db, bets: list):
    """Replace all live bets with fresh scraped data."""
    await db.execute("DELETE FROM live_bets")
    count = 0
    now = datetime.utcnow().isoformat()
    for b in bets:
        bet_id = b.get("bet_id", "")
        if not bet_id:
            continue
        await db.execute(
            "INSERT OR REPLACE INTO live_bets "
            "(bet_id, player_name, player_account, sub_agent_name, description, "
            "amount, odds, potential_payout, time_placed, status, sport, bet_type, raw_data, scraped_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                bet_id,
                b.get("player_name", ""),
                b.get("player_account", ""),
                b.get("sub_agent_name", ""),
                b.get("description", ""),
                b.get("amount", 0),
                b.get("odds", ""),
                b.get("potential_payout", 0),
                b.get("time_placed", ""),
                b.get("status", "open"),
                b.get("sport", ""),
                b.get("bet_type", ""),
                json.dumps(b.get("raw_data", {})),
                now,
            ),
        )
        count += 1
    await db.commit()
    return count


async def get_live_bets(db, sort_by: str = "sub_agent_name", sort_dir: str = "asc"):
    allowed_sorts = ["sub_agent_name", "amount", "time_placed", "player_name", "potential_payout"]
    if sort_by not in allowed_sorts:
        sort_by = "sub_agent_name"
    direction = "DESC" if sort_dir.lower() == "desc" else "ASC"
    cur = await db.execute(
        f"SELECT * FROM live_bets ORDER BY {sort_by} {direction}, amount DESC"
    )
    return [dict(r) for r in await cur.fetchall()]


async def get_live_bets_summary(db):
    cur = await db.execute(
        "SELECT COUNT(*) as total_bets, "
        "COALESCE(SUM(amount), 0) as total_wagered, "
        "COALESCE(SUM(potential_payout), 0) as total_payout "
        "FROM live_bets WHERE status = 'open'"
    )
    row = await cur.fetchone()
    summary = dict(row)

    # Last refresh time
    cur2 = await db.execute(
        "SELECT scraped_at FROM live_bets ORDER BY scraped_at DESC LIMIT 1"
    )
    last = await cur2.fetchone()
    summary["last_refreshed"] = last["scraped_at"] if last else None

    return summary
