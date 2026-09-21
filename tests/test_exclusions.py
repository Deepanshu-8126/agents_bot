import unittest
from app.filters.exclusion_filter import should_exclude

class TestExclusionFilter(unittest.TestCase):
    def test_default_senior_exclusions(self):
        self.assertTrue(should_exclude("Senior Data Analyst", "Analyze trends"))
        self.assertTrue(should_exclude("Engineering Manager", "Lead team of 10"))
        self.assertTrue(should_exclude("Lead BI Architect", "Build pipeline"))
        self.assertTrue(should_exclude("Director of Data", "Head department"))

    def test_years_of_experience_exclusion(self):
        self.assertTrue(should_exclude("Data Analyst", "Requires 10+ years of professional industry experience"))
        self.assertTrue(should_exclude("Software Developer", "Requires 5+ years experience"))

    def test_fresher_allowed(self):
        self.assertFalse(should_exclude("Junior Data Analyst", "Fresher graduate with 0-1 years"))
        self.assertFalse(should_exclude("Data Science Intern", "College students welcome"))

    def test_custom_user_exclusion(self):
        self.assertTrue(should_exclude("Sales Executive", "Selling products", user_exclusions=["sales"]))

if __name__ == "__main__":
    unittest.main()
