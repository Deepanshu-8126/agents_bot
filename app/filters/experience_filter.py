import re

FRESHER_PATTERNS = re.compile(
    r"\b(?:fresher|fresh graduate|recent graduate|new grad(?:uate)?|entry[- ]level|intern(?:ship)?|trainee|apprentice|junior|0\s*(?:years?|yrs?))\b",
    re.I
)

RANGE_PATTERN = re.compile(
    r"\b(\d+)\s*(?:-|–|to)\s*(\d+)\s*(?:years?|yrs?)\b",
    re.I
)

SINGLE_YEAR_PATTERN = re.compile(
    r"\b(\d+)\+?\s*(?:years?|yrs?)\b",
    re.I
)

def parse_experience(text: str) -> str:
    """Extract standard experience string from job title or description."""
    if not text:
        return "0-1 years"

    low = text.lower()
    if match := RANGE_PATTERN.search(low):
        min_yr, max_yr = int(match.group(1)), int(match.group(2))
        return f"{min_yr}-{max_yr} years"

    if match := SINGLE_YEAR_PATTERN.search(low):
        yr = int(match.group(1))
        if yr <= 1:
            return "0-1 years"
        return f"{yr} years"

    if FRESHER_PATTERNS.search(low):
        return "0-1 years (Fresher)"

    return "0-1 years"

def qualifies_experience(experience_str: str, max_allowed_years: int = 2) -> bool:
    """Returns True if the experience requirement is within max_allowed_years."""
    if not experience_str:
        return True

    low = experience_str.lower()
    if any(term in low for term in ("fresher", "intern", "entry", "trainee", "junior")):
        return True

    if match := RANGE_PATTERN.search(low):
        min_yr = int(match.group(1))
        return min_yr <= max_allowed_years

    if match := SINGLE_YEAR_PATTERN.search(low):
        yr = int(match.group(1))
        return yr <= max_allowed_years

    return True
