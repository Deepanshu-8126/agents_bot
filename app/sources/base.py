from abc import ABC, abstractmethod
from typing import List
from datetime import datetime, timezone
import httpx
from app.models.job import NormalizedJob
from app.filters.deduplication import generate_job_fingerprint

class JobSource(ABC):
    def __init__(self, source_id: str, name: str):
        self.source_id = source_id
        self.name = name
        try:
            self.http = httpx.Client(http2=True, follow_redirects=True, timeout=25, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                "Accept": "application/json,application/xml,text/xml,text/html;q=0.9"
            })
        except Exception:
            self.http = httpx.Client(follow_redirects=True, timeout=25, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                "Accept": "application/json,application/xml,text/xml,text/html;q=0.9"
            })

    def build_normalized_job(
        self,
        title: str,
        company: str,
        location: str,
        description: str,
        url: str,
        posted_at: str = None,
        experience: str = "0-1 years",
        salary: str = "Not Disclosed",
        skills: List[str] = None,
        remote: bool = False
    ) -> NormalizedJob:
        clean_title = title.strip()
        clean_company = company.strip()
        clean_location = location.strip()
        clean_url = url.strip()

        job_id = generate_job_fingerprint(clean_title, clean_company, clean_location, clean_url)
        posted_iso = posted_at or datetime.now(timezone.utc).isoformat()

        return NormalizedJob(
            job_id=job_id,
            title=clean_title,
            company=clean_company,
            location=clean_location,
            description=description.strip(),
            url=clean_url,
            source=self.name,
            posted_at=posted_iso,
            experience=experience,
            salary=salary,
            skills=skills or [],
            remote=remote
        )

    @abstractmethod
    def fetch_jobs(self) -> List[NormalizedJob]:
        """Fetch and return list of normalized jobs."""
        pass
