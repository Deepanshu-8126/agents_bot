import sqlite3
import os
from pathlib import Path
from app.config import settings

def get_connection(db_path: str = None) -> sqlite3.Connection:
    target_path = db_path or settings.DB_PATH
    conn = sqlite3.connect(target_path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(db_path: str = None):
    """Create all required tables with proper indexes."""
    conn = get_connection(db_path)
    cursor = conn.cursor()

    # 1. Jobs Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS jobs (
        job_id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        company TEXT NOT NULL,
        location TEXT,
        description TEXT,
        url TEXT NOT NULL,
        source TEXT NOT NULL,
        posted_at TEXT,
        experience TEXT,
        salary TEXT,
        skills_json TEXT,
        remote INTEGER DEFAULT 0,
        distance_km REAL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Index for fast lookup by source and created_at
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_source ON jobs(source);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at);")

    # 2. Job Sources Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS job_sources (
        source_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        is_enabled INTEGER DEFAULT 1,
        last_fetched_at TEXT,
        jobs_count INTEGER DEFAULT 0
    );
    """)

    # 3. User Preferences Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_preferences (
        chat_id TEXT PRIMARY KEY,
        city TEXT DEFAULT 'Haldwani',
        radius_km REAL DEFAULT 100.0,
        max_experience_years INTEGER DEFAULT 2,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 4. Keywords Table (Per-user positive filter)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS keywords (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id TEXT NOT NULL,
        keyword TEXT NOT NULL,
        UNIQUE(chat_id, keyword)
    );
    """)

    # 5. Excluded Keywords Table (Per-user negative filter)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS excluded_keywords (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id TEXT NOT NULL,
        keyword TEXT NOT NULL,
        UNIQUE(chat_id, keyword)
    );
    """)

    conn.commit()
    conn.close()
