from typing import List
from datetime import datetime, timezone
from app.sources.base import JobSource
from app.models.job import NormalizedJob

class WellfoundSource(JobSource):
    """Wellfound (AngelList) public startup opportunities adapter."""
    def __init__(self):
        super().__init__("wellfound", "Wellfound")

    def fetch_jobs(self) -> List[NormalizedJob]:
        normalized = []
        # Consume public feed / API endpoints
        urls = [
            "https://wellfound.com/api/public/jobs/freshers",
            "https://wellfound.com/jobs"
        ]
        for u in urls:
            try:
                res = self.http.get(u)
                if res.status_code == 200 and "application/json" in res.headers.get("content-type", ""):
                    data = res.json()
                    for j in data.get("jobs", []):
                        norm = self.build_normalized_job(
                            title=j.get("title", ""),
                            company=j.get("startup_name", "Wellfound Startup"),
                            location=j.get("location", "Remote"),
                            description=j.get("description", ""),
                            url=j.get("url", "https://wellfound.com"),
                            posted_at=datetime.now(timezone.utc).isoformat(),
                            experience="0-1 years",
                            remote=True
                        )
                        normalized.append(norm)
            except Exception as exc:
                print(f"[warn] WellfoundSource: {exc}")
        return normalized
