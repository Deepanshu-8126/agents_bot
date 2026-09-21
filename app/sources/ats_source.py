from typing import List
import re
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from app.sources.base import JobSource
from app.models.job import NormalizedJob
import job_alert as legacy_core
import local_alert as legacy_local

class CompanyATSSource(JobSource):
    def __init__(self):
        super().__init__("company_ats", "Company ATS")

    def fetch_jobs(self) -> List[NormalizedJob]:
        normalized = []
        try:
            # 1. Official Greenhouse, Lever, Ashby, Accenture, IndiGo
            raw_jobs = legacy_core.ats_jobs() + legacy_core.accenture_jobs() + legacy_core.indigo_jobs()
            # 2. Regional ATS: Tata Motors, Mahindra, Reckitt, Perfetti, Britannia, Nestle
            raw_local = legacy_local.successfactors_jobs() + legacy_local.britannia_jobs() + legacy_local.nestle_jobs()

            for j in raw_jobs:
                norm_job = self.build_normalized_job(
                    title=j.get("title", ""),
                    company=j.get("company", ""),
                    location=j.get("location", "India"),
                    description=j.get("desc", ""),
                    url=j.get("url", ""),
                    posted_at=str(j.get("posted", "")),
                    experience="0-1 years",
                    remote=bool(j.get("remote", False))
                )
                normalized.append(norm_job)

            for j in raw_local:
                norm_job = self.build_normalized_job(
                    title=j.get("title", ""),
                    company=j.get("company", ""),
                    location=j.get("location", "Uttarakhand"),
                    description=j.get("desc", ""),
                    url=j.get("url", ""),
                    posted_at=str(j.get("posted", "")),
                    experience="0-1 years",
                    skills=[s.strip() for s in j.get("skills", "").split(",") if s.strip()]
                )
                normalized.append(norm_job)
        except Exception as exc:
            print(f"[warn] ATS Source error: {exc}")

        return normalized
