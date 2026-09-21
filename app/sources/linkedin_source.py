from typing import List
from datetime import datetime, timezone
import os
from app.sources.base import JobSource
from app.models.job import NormalizedJob

class LinkedInSource(JobSource):
    """LinkedIn official job alerts / user-provided alert feeds adapter."""
    def __init__(self):
        super().__init__("linkedin", "LinkedIn")

    def fetch_jobs(self) -> List[NormalizedJob]:
        normalized = []
        # Support user-provided feed URL or public alert webhooks
        custom_feed = os.getenv("LINKEDIN_ALERT_FEED_URL", "").strip()
        if custom_feed:
            try:
                res = self.http.get(custom_feed)
                if res.status_code == 200:
                    data = res.json()
                    for item in data.get("jobs", []):
                        norm = self.build_normalized_job(
                            title=item.get("title", ""),
                            company=item.get("company", "LinkedIn Partner"),
                            location=item.get("location", "India"),
                            description=item.get("description", ""),
                            url=item.get("url", "https://linkedin.com"),
                            posted_at=datetime.now(timezone.utc).isoformat(),
                            experience=item.get("experience", "0-1 years")
                        )
                        normalized.append(norm)
            except Exception as exc:
                print(f"[warn] LinkedInSource: {exc}")
        return normalized
