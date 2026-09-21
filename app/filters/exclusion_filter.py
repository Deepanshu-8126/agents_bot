import re
from typing import List

DEFAULT_EXCLUSIONS = [
    "senior",
    "sr",
    "manager",
    "lead",
    "principal",
    "director",
    "head",
    "architect",
    "10+ years",
    "5+ years",
]

def should_exclude(title: str, description: str, user_exclusions: List[str] = None) -> bool:
    """Returns True if title or description triggers default or user-defined exclusion keywords."""
    combined_exclusions = list(DEFAULT_EXCLUSIONS)
    if user_exclusions:
        for exc in user_exclusions:
            clean_exc = exc.strip().lower()
            if clean_exc and clean_exc not in combined_exclusions:
                combined_exclusions.append(clean_exc)

    title_low = title.lower()
    desc_low = description.lower()

    for exc in combined_exclusions:
        pattern = rf"\b{re.escape(exc)}\b"
        if re.search(pattern, title_low):
            return True
        # Also check years of experience patterns
        if "year" in exc and re.search(pattern, desc_low):
            return True

    # Check common high-experience patterns in description
    if re.search(r"\b(?:[3-9]|\d{2,})\+?\s*(?:years?|yrs?)(?:\s+of)?\s+experience\b", desc_low):
        return True

    return False
