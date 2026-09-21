import math
import re
from typing import Optional, Tuple

# Comprehensive registry of coordinates for major Indian tech hubs & regional industrial clusters
CITY_COORDINATES = {
    # Uttarakhand & Kumaon
    "haldwani": (29.2183, 79.5130),
    "rudrapur": (28.9800, 79.4000),
    "pantnagar": (29.0270, 79.4890),
    "sidcul": (28.9800, 79.4000),
    "dehradun": (30.3165, 78.0322),
    "haridwar": (29.9457, 78.1642),
    "roorkee": (29.8543, 77.8880),
    "kashipur": (29.2110, 78.9610),
    "nainital": (29.3919, 79.4542),

    # NCR / North India
    "noida": (28.5355, 77.3910),
    "greater noida": (28.4744, 77.5040),
    "delhi": (28.6139, 77.2090),
    "new delhi": (28.6139, 77.2090),
    "gurugram": (28.4595, 77.0266),
    "gurgaon": (28.4595, 77.0266),
    "faridabad": (28.4089, 77.3178),
    "ghaziabad": (28.6692, 77.4538),
    "chandigarh": (30.7333, 76.7794),
    "mohali": (30.7046, 76.7179),
    "jaipur": (26.9124, 75.7873),
    "lucknow": (26.8467, 80.9462),
    "kanpur": (26.4499, 80.3319),
    "indore": (22.7196, 75.8577),

    # Major Tech Hubs (South & West India)
    "bengaluru": (12.9716, 77.5946),
    "bangalore": (12.9716, 77.5946),
    "hyderabad": (17.3850, 78.4867),
    "pune": (18.5204, 73.8567),
    "mumbai": (19.0760, 72.8777),
    "navi mumbai": (19.0330, 73.0297),
    "chennai": (13.0827, 80.2707),
    "kolkata": (22.5726, 88.3639),
    "ahmedabad": (23.0225, 72.5714),
    "kochi": (9.9312, 76.2673),
    "coimbatore": (11.0168, 76.9558),
}

CITY_ALIASES = {
    "delhi ncr": "delhi",
    "ncr": "delhi",
    "gurgaon": "gurugram",
    "bangalore": "bengaluru",
    "bombay": "mumbai",
    "calcutta": "kolkata",
}

def normalize_city_name(raw_name: str) -> str:
    """Normalize input string to canonical city key."""
    if not raw_name:
        return ""
    cleaned = re.sub(r"[^a-zA-Z\s]", " ", raw_name).strip().lower()
    cleaned = re.sub(r"\s+", " ", cleaned)
    for alias, canonical in CITY_ALIASES.items():
        if alias in cleaned:
            return canonical
    for city in CITY_COORDINATES:
        if re.search(rf"\b{re.escape(city)}\b", cleaned):
            return city
    return cleaned

def get_coordinates(city_name: str) -> Optional[Tuple[float, float]]:
    key = normalize_city_name(city_name)
    return CITY_COORDINATES.get(key)

def haversine_distance(coord1: Tuple[float, float], coord2: Tuple[float, float]) -> float:
    """Calculate great-circle distance in kilometers using the Haversine formula."""
    lat1, lon1 = math.radians(coord1[0]), math.radians(coord1[1])
    lat2, lon2 = math.radians(coord2[0]), math.radians(coord2[1])

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = math.sin(dlat / 2.0) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    radius_earth_km = 6371.0
    return radius_earth_km * c

def calculate_distance(city_a: str, city_b: str) -> Optional[float]:
    """Calculate distance between two city strings in km, or None if unknown."""
    coord_a = get_coordinates(city_a)
    coord_b = get_coordinates(city_b)
    if not coord_a or not coord_b:
        return None
    return haversine_distance(coord_a, coord_b)

def matches_location_radius(job_location: str, user_city: str, radius_km: float) -> Tuple[bool, Optional[float]]:
    """Determine if a job location is within radius of user's preferred city.
    Returns (matches, distance_km).
    Remote/WFH jobs always match with distance_km = None.
    """
    low_loc = job_location.lower()
    if any(term in low_loc for term in ("remote", "work from home", "wfh", "anywhere")):
        return True, None

    # Exact city match (0 km)
    norm_job_city = normalize_city_name(job_location)
    norm_user_city = normalize_city_name(user_city)
    if norm_job_city and norm_job_city == norm_user_city:
        return True, 0.0

    dist = calculate_distance(job_location, user_city)
    if dist is not None:
        return dist <= radius_km, dist

    # If coordinates are unavailable, allow India-wide if user city is unknown or broadly specified
    return False, None
