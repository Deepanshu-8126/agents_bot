import re
from typing import List

def matches_keywords(text: str, keywords: List[str]) -> bool:
    """Returns True if the text matches at least one of the active user keywords.
    If no keywords are configured, returns True (no restriction).
    """
    if not keywords:
        return True

    low_text = text.lower()
    for kw in keywords:
        clean_kw = kw.strip().lower()
        if not clean_kw:
            continue
        # Use boundary match for words
        pattern = rf"\b{re.escape(clean_kw)}\b"
        if re.search(pattern, low_text):
            return True
    return False

def extract_matching_keywords(text: str, keywords: List[str]) -> List[str]:
    """Returns the list of keywords that matched inside text."""
    low_text = text.lower()
    matches = []
    for kw in keywords:
        clean_kw = kw.strip().lower()
        if clean_kw and re.search(rf"\b{re.escape(clean_kw)}\b", low_text):
            matches.append(kw.strip())
    return matches
