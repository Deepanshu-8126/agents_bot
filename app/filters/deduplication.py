import hashlib
import re
from urllib.parse import urlparse, urlunparse

def canonical_url(url: str) -> str:
    """Normalize URL by stripping tracking queries and fragments."""
    if not url:
        return ""
    try:
        parsed = urlparse(url.strip())
        # Keep path clean, remove query tracking like utm_source
        return urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path.rstrip("/"), "", "", ""))
    except Exception:
        return url.strip().lower()

def normalize_text_token(text: str) -> str:
    """Lowercase and strip non-alphanumeric characters for deterministic fingerprinting."""
    if not text:
        return ""
    cleaned = re.sub(r"[^a-zA-Z0-9\s]", "", str(text).lower())
    return re.sub(r"\s+", " ", cleaned).strip()

def generate_job_fingerprint(title: str, company: str, location: str, url: str) -> str:
    """Generate deterministic SHA-256 hash identifying the job uniquely across sources."""
    norm_title = normalize_text_token(title)
    norm_company = normalize_text_token(company)
    norm_location = normalize_text_token(location)
    clean_url = canonical_url(url)

    raw_payload = f"{norm_title}|{norm_company}|{norm_location}|{clean_url}"
    return hashlib.sha256(raw_payload.encode("utf-8")).hexdigest()

def clean_company_name(name: str) -> str:
    norm = normalize_text_token(name)
    # Remove common corporate suffixes
    suffixes = [r"\bpvt\b", r"\bltd\b", r"\bprivate\b", r"\blimited\b", r"\binc\b", r"\bllc\b", r"\btechnologies\b", r"\bsolutions\b", r"\bsoftware\b"]
    for s in suffixes:
        norm = re.sub(s, "", norm)
    return re.sub(r"\s+", " ", norm).strip()

def is_same_cross_source_job(title_a: str, company_a: str, title_b: str, company_b: str) -> bool:
    """Check if two listings represent the same role across different job portals."""
    norm_t_a = normalize_text_token(title_a)
    norm_t_b = normalize_text_token(title_b)
    
    clean_c_a = clean_company_name(company_a)
    clean_c_b = clean_company_name(company_b)

    company_match = (
        (clean_c_a and clean_c_b) and
        (clean_c_a == clean_c_b or clean_c_a in clean_c_b or clean_c_b in clean_c_a)
    )

    if company_match:
        if norm_t_a and norm_t_b and (norm_t_a == norm_t_b or norm_t_a in norm_t_b or norm_t_b in norm_t_a):
            return True
    return False
