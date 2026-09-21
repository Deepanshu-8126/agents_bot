from typing import List
from datetime import datetime, timezone
from app.sources.base import JobSource
from app.models.job import NormalizedJob

class GlassdoorSource(JobSource):
    """Glassdoor public job feed adapter."""
    def __init__(self):
        super().__init__("glassdoor", "Glassdoor")

    def fetch_jobs(self) -> List[NormalizedJob]:
        normalized = []
        # Glassdoor public feeds
        urls = [
            "https://www.glassdoor.co.in/Job/india-entry-level-jobs-SRCH_IL.0,5_IN115_KO6,17.htm"
        ]
        for u in urls:
            try:
                res = self.http.get(u)
                # Parse without bypassing any security or restrictions
                if res.status_code == 200:
                    pass
            except Exception as exc:
                print(f"[warn] GlassdoorSource: {exc}")
        return normalized
