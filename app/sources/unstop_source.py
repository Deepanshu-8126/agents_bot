from typing import List
from datetime import datetime, timezone
from app.sources.base import JobSource
from app.models.job import NormalizedJob

class UnstopSource(JobSource):
    def __init__(self):
        super().__init__("unstop", "Unstop")

    def fetch_jobs(self) -> List[NormalizedJob]:
        normalized = []
        endpoints = [
            "https://unstop.com/api/public/opportunity/search-result?opportunity=jobs&sort=recent&per_page=25",
            "https://unstop.com/api/public/opportunity/search-result?opportunity=internships&sort=recent&per_page=25"
        ]
        seen_ids = set()
        for endpoint in endpoints:
            try:
                res = self.http.get(endpoint)
                if res.status_code != 200:
                    continue
                data = res.json().get("data", {}).get("data", [])
                for item in data:
                    oid = item.get("id")
                    if not oid or oid in seen_ids:
                        continue
                    seen_ids.add(oid)

                    title = item.get("title", "").strip()
                    org = item.get("organisation", {}) or {}
                    company = (org.get("name") or "Unstop Employer").strip()

                    job_detail = item.get("jobDetail", {}) or {}
                    locs = job_detail.get("locations", [])
                    location = ", ".join(locs) if locs else "India"
                    is_remote = job_detail.get("type") == "work_from_home" or "remote" in location.lower()

                    url = item.get("seo_url") or item.get("short_url") or f"https://unstop.com/jobs/{oid}"
                    desc = title

                    posted_str = item.get("approved_date") or (item.get("regnRequirements", {}) or {}).get("start_regn_dt")

                    norm_job = self.build_normalized_job(
                        title=title,
                        company=company,
                        location=location,
                        description=desc,
                        url=url,
                        posted_at=posted_str or datetime.now(timezone.utc).isoformat(),
                        experience="0-2 years",
                        remote=is_remote
                    )
                    normalized.append(norm_job)
            except Exception as exc:
                print(f"[warn] UnstopSource: {exc}")
        return normalized
