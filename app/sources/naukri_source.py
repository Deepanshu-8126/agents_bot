from typing import List
from datetime import datetime, timezone
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from app.sources.base import JobSource
from app.models.job import NormalizedJob

class NaukriSource(JobSource):
    """Naukri adapter querying public XML/RSS and job alert feeds."""
    def __init__(self):
        super().__init__("naukri", "Naukri")

    def fetch_jobs(self) -> List[NormalizedJob]:
        normalized = []
        # Public RSS & career alert endpoints
        feeds = [
            "https://www.naukri.com/jobapi/v3/search?noOfResults=20&keyword=data+analyst&experience=0",
            "https://www.naukri.com/jobapi/v3/search?noOfResults=20&keyword=fresher+software+engineer&experience=0",
        ]
        headers = {
            "appid": "109",
            "systemid": "naukri",
            "clientid": "d3wt17vis",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        }
        for endpoint in feeds:
            try:
                res = self.http.get(endpoint, headers=headers)
                if res.status_code == 200:
                    data = res.json()
                    job_details = data.get("jobDetails", [])
                    for item in job_details:
                        title = item.get("title", "").strip()
                        company = item.get("companyName", "Naukri Employer").strip()
                        place = item.get("placeholders", [])
                        loc = place[2].get("label", "India") if len(place) > 2 else "India"
                        exp = place[0].get("label", "0-1 years") if len(place) > 0 else "0-1 years"
                        sal = place[1].get("label", "Not Disclosed") if len(place) > 1 else "Not Disclosed"
                        url = item.get("jdURL", "")
                        if not url.startswith("http"):
                            url = f"https://www.naukri.com{url}"

                        norm = self.build_normalized_job(
                            title=title,
                            company=company,
                            location=loc,
                            description=item.get("jobDescription", title),
                            url=url,
                            posted_at=datetime.now(timezone.utc).isoformat(),
                            experience=exp,
                            salary=sal,
                            remote="remote" in loc.lower() or "wfh" in loc.lower()
                        )
                        normalized.append(norm)
            except Exception as exc:
                print(f"[warn] NaukriSource: {exc}")
        return normalized
