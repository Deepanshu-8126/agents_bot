import json
from typing import List, Optional, Dict, Any
from app.models.job import NormalizedJob
from app.database.db import get_connection

class JobRepository:
    def __init__(self, db_path: str = None):
        self.db_path = db_path

    # --- Jobs Operations ---
    def insert_job(self, job: NormalizedJob) -> bool:
        """Insert a normalized job. Returns True if inserted, False if duplicate already exists."""
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("""
            INSERT INTO jobs (
                job_id, title, company, location, description, url,
                source, posted_at, experience, salary, skills_json,
                remote, distance_km
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                job.job_id, job.title, job.company, job.location, job.description,
                job.url, job.source, job.posted_at, job.experience, job.salary,
                json.dumps(job.skills), int(job.remote), job.distance_km
            ))
            conn.commit()
            return True
        except Exception:
            return False
        finally:
            conn.close()

    def job_exists(self, job_id: str) -> bool:
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM jobs WHERE job_id = ?", (job_id,))
        row = cursor.fetchone()
        conn.close()
        return row is not None

    def get_recent_jobs(self, limit: int = 50) -> List[NormalizedJob]:
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        conn.close()
        return [
            NormalizedJob(
                job_id=r["job_id"],
                title=r["title"],
                company=r["company"],
                location=r["location"],
                description=r["description"],
                url=r["url"],
                source=r["source"],
                posted_at=r["posted_at"],
                experience=r["experience"],
                salary=r["salary"],
                skills=json.loads(r["skills_json"] or "[]"),
                remote=bool(r["remote"]),
                distance_km=r["distance_km"]
            )
            for r in rows
        ]

    # --- User Preferences Operations ---
    def get_user_preference(self, chat_id: str) -> Dict[str, Any]:
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM user_preferences WHERE chat_id = ?", (str(chat_id),))
        row = cursor.fetchone()
        conn.close()
        if row:
            return dict(row)
        return {
            "chat_id": str(chat_id),
            "city": "Haldwani",
            "radius_km": 100.0,
            "max_experience_years": 2
        }

    def set_user_location(self, chat_id: str, city: str, radius_km: float = None):
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        pref = self.get_user_preference(chat_id)
        new_radius = radius_km if radius_km is not None else pref["radius_km"]
        cursor.execute("""
        INSERT INTO user_preferences (chat_id, city, radius_km, updated_at)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(chat_id) DO UPDATE SET
            city = excluded.city,
            radius_km = excluded.radius_km,
            updated_at = CURRENT_TIMESTAMP
        """, (str(chat_id), city.strip().title(), float(new_radius)))
        conn.commit()
        conn.close()

    def set_user_radius(self, chat_id: str, radius_km: float):
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        pref = self.get_user_preference(chat_id)
        cursor.execute("""
        INSERT INTO user_preferences (chat_id, city, radius_km, updated_at)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(chat_id) DO UPDATE SET
            radius_km = excluded.radius_km,
            updated_at = CURRENT_TIMESTAMP
        """, (str(chat_id), pref["city"], float(radius_km)))
        conn.commit()
        conn.close()

    # --- Keywords Operations ---
    def add_keyword(self, chat_id: str, keyword: str) -> bool:
        clean_kw = keyword.strip().lower()
        if not clean_kw:
            return False
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT OR IGNORE INTO keywords (chat_id, keyword) VALUES (?, ?)", (str(chat_id), clean_kw))
            conn.commit()
            return True
        finally:
            conn.close()

    def remove_keyword(self, chat_id: str, keyword: str) -> bool:
        clean_kw = keyword.strip().lower()
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM keywords WHERE chat_id = ? AND keyword = ?", (str(chat_id), clean_kw))
        affected = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return affected

    def get_keywords(self, chat_id: str) -> List[str]:
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT keyword FROM keywords WHERE chat_id = ? ORDER BY keyword ASC", (str(chat_id),))
        rows = cursor.fetchall()
        conn.close()
        return [r["keyword"] for r in rows]

    # --- Excluded Keywords Operations ---
    def add_exclude(self, chat_id: str, keyword: str) -> bool:
        clean_kw = keyword.strip().lower()
        if not clean_kw:
            return False
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT OR IGNORE INTO excluded_keywords (chat_id, keyword) VALUES (?, ?)", (str(chat_id), clean_kw))
            conn.commit()
            return True
        finally:
            conn.close()

    def remove_exclude(self, chat_id: str, keyword: str) -> bool:
        clean_kw = keyword.strip().lower()
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM excluded_keywords WHERE chat_id = ? AND keyword = ?", (str(chat_id), clean_kw))
        affected = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return affected

    def get_excludes(self, chat_id: str) -> List[str]:
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT keyword FROM excluded_keywords WHERE chat_id = ? ORDER BY keyword ASC", (str(chat_id),))
        rows = cursor.fetchall()
        conn.close()
        return [r["keyword"] for r in rows]

    # --- Sources Operations ---
    def register_source(self, source_id: str, name: str, is_enabled: bool = True):
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO job_sources (source_id, name, is_enabled)
        VALUES (?, ?, ?)
        ON CONFLICT(source_id) DO UPDATE SET name = excluded.name
        """, (source_id, name, int(is_enabled)))
        conn.commit()
        conn.close()

    def update_source_stats(self, source_id: str, count: int):
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
        UPDATE job_sources
        SET last_fetched_at = CURRENT_TIMESTAMP, jobs_count = jobs_count + ?
        WHERE source_id = ?
        """, (count, source_id))
        conn.commit()
        conn.close()

    def get_all_sources(self) -> List[Dict[str, Any]]:
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM job_sources ORDER BY name ASC")
        rows = cursor.fetchall()
        conn.close()
        return [dict(r) for r in rows]
