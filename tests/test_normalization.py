import unittest
from app.models.job import NormalizedJob

class TestJobNormalization(unittest.TestCase):
    def test_job_normalization_fields(self):
        job = NormalizedJob(
            job_id="test-sha256-id",
            title="Junior Data Analyst",
            company="Acme Corp",
            location="Noida",
            description="Looking for fresher python & sql analyst",
            url="https://example.com/job/123",
            source="Naukri",
            posted_at="2026-09-21T08:00:00Z",
            experience="0-1 years",
            salary="₹4,00,000",
            skills=["Python", "SQL"],
            remote=False,
            distance_km=215.4
        )

        d = job.to_dict()
        self.assertEqual(d["job_id"], "test-sha256-id")
        self.assertEqual(d["title"], "Junior Data Analyst")
        self.assertEqual(d["company"], "Acme Corp")
        self.assertEqual(d["location"], "Noida")
        self.assertEqual(d["experience"], "0-1 years")
        self.assertEqual(d["salary"], "₹4,00,000")
        self.assertEqual(d["skills"], ["Python", "SQL"])
        self.assertEqual(d["distance_km"], 215.4)

    def test_job_from_dict_and_telegram_formatting(self):
        data = {
            "job_id": "abc12345",
            "title": "Data Analyst",
            "company": "XYZ Corp",
            "location": "Noida",
            "description": "Analyze datasets",
            "url": "https://example.com/apply",
            "source": "Naukri",
            "posted_at": "2026-09-21T00:00:00Z",
            "experience": "0-2 years",
            "salary": "₹5,00,000",
            "skills": ["Python"],
            "distance_km": 215.0
        }
        job = NormalizedJob.from_dict(data)
        self.assertEqual(job.company, "XYZ Corp")
        formatted = job.format_telegram()
        self.assertIn("NEW JOB", formatted)
        self.assertIn("Data Analyst", formatted)
        self.assertIn("Company: XYZ Corp", formatted)
        self.assertIn("Location: Noida", formatted)
        self.assertIn("Distance: 215 km", formatted)
        self.assertIn("Source: Naukri", formatted)
        self.assertIn("https://example.com/apply", formatted)

if __name__ == "__main__":
    unittest.main()
