import unittest
from app.location.distance import (
    normalize_city_name,
    get_coordinates,
    calculate_distance,
    matches_location_radius,
)

class TestLocationIntelligence(unittest.TestCase):
    def test_city_normalization(self):
        self.assertEqual(normalize_city_name("Gurgaon"), "gurugram")
        self.assertEqual(normalize_city_name("Delhi NCR"), "delhi")
        self.assertEqual(normalize_city_name("Haldwani"), "haldwani")
        self.assertEqual(normalize_city_name("Rudrapur SIDCUL"), "rudrapur")

    def test_coordinate_resolution(self):
        coord_haldwani = get_coordinates("Haldwani")
        self.assertIsNotNone(coord_haldwani)
        coord_noida = get_coordinates("Noida")
        self.assertIsNotNone(coord_noida)

    def test_haversine_distance_calculation(self):
        # Distance between Haldwani and Rudrapur is ~30 km
        dist = calculate_distance("Haldwani", "Rudrapur")
        self.assertIsNotNone(dist)
        self.assertTrue(20 <= dist <= 40, f"Distance between Haldwani and Rudrapur should be ~30 km, got {dist}")

        # Distance between Haldwani and Noida is ~210-230 km
        dist_noida = calculate_distance("Haldwani", "Noida")
        self.assertIsNotNone(dist_noida)
        self.assertTrue(190 <= dist_noida <= 250, f"Distance between Haldwani and Noida should be ~215 km, got {dist_noida}")

    def test_matches_location_radius(self):
        # Rudrapur within 50 km of Haldwani
        match, dist = matches_location_radius("Rudrapur", "Haldwani", radius_km=50)
        self.assertTrue(match)
        self.assertIsNotNone(dist)

        # Noida is NOT within 100 km of Haldwani
        match_far, dist_far = matches_location_radius("Noida", "Haldwani", radius_km=100)
        self.assertFalse(match_far)
        self.assertIsNotNone(dist_far)

        # Remote jobs always match
        match_remote, dist_remote = matches_location_radius("Remote / Work from home", "Haldwani", radius_km=50)
        self.assertTrue(match_remote)
        self.assertIsNone(dist_remote)

if __name__ == "__main__":
    unittest.main()
