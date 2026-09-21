import unittest
from app.filters.experience_filter import parse_experience, qualifies_experience

class TestExperienceFilter(unittest.TestCase):
    def test_parse_experience_strings(self):
        self.assertEqual(parse_experience("Looking for candidates with 0-2 years experience"), "0-2 years")
        self.assertEqual(parse_experience("Entry level fresher position"), "0-1 years (Fresher)")
        self.assertEqual(parse_experience("Requires 5 years experience"), "5 years")

    def test_qualifies_experience(self):
        self.assertTrue(qualifies_experience("0-1 years", max_allowed_years=2))
        self.assertTrue(qualifies_experience("0-2 years", max_allowed_years=2))
        self.assertTrue(qualifies_experience("Fresher / Entry level", max_allowed_years=2))
        self.assertFalse(qualifies_experience("3-5 years", max_allowed_years=2))
        self.assertFalse(qualifies_experience("5 years", max_allowed_years=2))

if __name__ == "__main__":
    unittest.main()
