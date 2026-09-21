from typing import List
from datetime import datetime, timezone
from app.sources.base import JobSource
from app.models.job import NormalizedJob

class FounditSource(JobSource):
    """Foundit (formerly Monster India) public career opportunities adapter."""
    def __init__(self):
        super().__init__("foundit", "Foundit")

    def fetch_jobs(self) -> List[NormalizedJob]:
        normalized = []
        endpoints = [
            "https://www.foundit.in/web/en/search?query=data+analyst&experienceRanges=0~1",
            "https://api.foundit.in/job-search/v1/search?query=fresher&limit=15"
        ]
        for url in endpoints:
            try:
                res = self.http.get(url)
                if res.status_code == 200 and "application/json" in res.headers.get("content-type", ""):
                    data = res.json()
                    for item in data.get("jobs", []):
                        title = item.get("title", "")
                        comp = item.get("company", {}).get("name", "Foundit Partner")
                        loc = item.get("locations", ["India"])[0]
                        link = item.get("redirectUrl") or f"https://www.foundit.in/job/{item.get('id', '')}"
                        norm = self.build_normalized_job(
                            title=title,
                            company=comp,
                            location=loc,
                            description=item.get("summary", title),
                            url=link,
                            posted_at=datetime.now(timezone.utc).isoformat(),
                            experience="0-1 years"
                        )
                        normalized.append(norm)
            except Exception as exc:
                print(f"[warn] FounditSource: {exc}")
        return normalized
