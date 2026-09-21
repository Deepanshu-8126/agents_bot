import unittest
from app.filters.keyword_filter import matches_keywords, extract_matching_keywords

class TestKeywordFilter(unittest.TestCase):
    def test_single_and_multi_keyword_matching(self):
        text = "We are seeking a junior python developer with SQL knowledge"
        self.assertTrue(matches_keywords(text, ["python"]))
        self.assertTrue(matches_keywords(text, ["sql", "power bi"]))
        self.assertFalse(matches_keywords(text, ["react", "flutter"]))

    def test_empty_keywords_allows_all(self):
        self.assertTrue(matches_keywords("Any job title", []))

    def test_extract_matching_keywords(self):
        text = "Data Analyst position requiring Python, Excel, and SQL dashboard skills"
        matched = extract_matching_keywords(text, ["python", "excel", "react"])
        self.assertEqual(sorted(matched), ["excel", "python"])

if __name__ == "__main__":
    unittest.main()
