"""
Database setup script.
"""
import sqlite3
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def init_db():
    db_path = ROOT_DIR / "data" / "trading.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS agents (
            id TEXT PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            initial_bankroll REAL NOT NULL,
            current_bankroll REAL NOT NULL,
            survival_mode TEXT NOT NULL,
            is_alive INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS bets (
            id TEXT PRIMARY KEY,
            agent_name TEXT NOT NULL,
            market TEXT NOT NULL,
            event TEXT NOT NULL,
            selection TEXT NOT NULL,
            odds REAL NOT NULL,
            stake REAL NOT NULL,
            status TEXT NOT NULL,
            pnl REAL DEFAULT 0.0,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()
    print(f" SQLite database initialized at {db_path}")


if __name__ == "__main__":
    init_db()
