import unittest
import os
import tempfile
from datetime import datetime, timezone
from app.database.db import init_db
from app.database.repository import JobRepository
from app.models.job import NormalizedJob
from app.filters.deduplication import generate_job_fingerprint

class TestDatabaseAndRepository(unittest.TestCase):
    def setUp(self):
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp(suffix=".db")
        init_db(self.temp_db_path)
        self.repo = JobRepository(self.temp_db_path)

    def tearDown(self):
        os.close(self.temp_db_fd)
        if os.path.exists(self.temp_db_path):
            os.remove(self.temp_db_path)

    def test_insert_and_deduplicate_job(self):
        title = "Junior Python Engineer"
        company = "TechCorp Solutions"
        location = "Noida, India"
        url = "https://boards.greenhouse.io/techcorp/jobs/12345"
        job_id = generate_job_fingerprint(title, company, location, url)

        job = NormalizedJob(
            job_id=job_id,
            title=title,
            company=company,
            location=location,
            source="ats_greenhouse",
            url=url,
            experience="0-2 years",
            posted_at=datetime.now(timezone.utc).isoformat(),
            description="Developing backend APIs with FastAPI.",
            salary="6-8 LPA",
            skills=["python", "fastapi"]
        )
        
        # First insertion should succeed
        inserted = self.repo.insert_job(job)
        self.assertTrue(inserted)
        
        # Second insertion with the exact same fingerprint should return False (duplicate)
        duplicate = self.repo.insert_job(job)
        self.assertFalse(duplicate)

    def test_user_preferences_location_and_radius(self):
        chat_id = "test_user_123"
        prefs = self.repo.get_user_preference(chat_id)
        self.assertEqual(prefs["city"], "Haldwani")
        self.assertEqual(prefs["radius_km"], 100.0)

        # Update location
        self.repo.set_user_location(chat_id, "Noida")
        # Update radius
        self.repo.set_user_radius(chat_id, 50.0)

        updated_prefs = self.repo.get_user_preference(chat_id)
        self.assertEqual(updated_prefs["city"], "Noida")
        self.assertEqual(updated_prefs["radius_km"], 50.0)

    def test_keywords_management(self):
        chat_id = "test_user_456"
        # Add custom keyword
        added = self.repo.add_keyword(chat_id, "fastapi")
        self.assertTrue(added)
        self.assertIn("fastapi", self.repo.get_keywords(chat_id))

        # Re-adding existing should maintain presence
        self.repo.add_keyword(chat_id, "fastapi")
        self.assertEqual(self.repo.get_keywords(chat_id).count("fastapi"), 1)

        # Remove keyword
        removed = self.repo.remove_keyword(chat_id, "fastapi")
        self.assertTrue(removed)
        self.assertNotIn("fastapi", self.repo.get_keywords(chat_id))

    def test_exclusions_management(self):
        chat_id = "test_user_789"
        # Add custom exclusion
        added = self.repo.add_exclude(chat_id, "telecalling")
        self.assertTrue(added)
        self.assertIn("telecalling", self.repo.get_excludes(chat_id))

        # Remove exclusion
        removed = self.repo.remove_exclude(chat_id, "telecalling")
        self.assertTrue(removed)
        self.assertNotIn("telecalling", self.repo.get_excludes(chat_id))

if __name__ == "__main__":
    unittest.main()
