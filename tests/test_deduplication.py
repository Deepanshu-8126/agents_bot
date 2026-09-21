import unittest
from app.filters.deduplication import generate_job_fingerprint, is_same_cross_source_job, canonical_url

class TestDeduplication(unittest.TestCase):
    def test_deterministic_sha256_hash(self):
        h1 = generate_job_fingerprint("Data Analyst", "Razorpay", "Noida", "https://example.com/job?utm_source=feed")
        h2 = generate_job_fingerprint("data analyst", "razorpay", "noida", "https://example.com/job")
        self.assertEqual(h1, h2, "Fingerprint should normalize casing, whitespace, and tracking URLs deterministically")

    def test_canonical_url(self):
        clean = canonical_url("https://in.indeed.com/viewjob?jk=12345&utm_source=publisher#target")
        self.assertEqual(clean, "https://in.indeed.com/viewjob")

    def test_cross_source_duplicate_detection(self):
        is_dup = is_same_cross_source_job(
            "Junior Data Analyst - Fresher", "Razorpay Software Pvt Ltd",
            "Junior Data Analyst", "Razorpay"
        )
        self.assertTrue(is_dup, "Cross-source identical roles from same company should be detected")

if __name__ == "__main__":
    unittest.main()
