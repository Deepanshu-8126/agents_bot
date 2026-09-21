from typing import List
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from datetime import datetime, timezone
from app.sources.base import JobSource
from app.models.job import NormalizedJob

class InternshalaSource(JobSource):
    def __init__(self):
        super().__init__("internshala", "Internshala")

    def fetch_jobs(self) -> List[NormalizedJob]:
        normalized = []
        urls = [
            "https://internshala.com/internships/data-science,web-development,python-django,video-making-editing-internship/",
            "https://internshala.com/jobs/data-science,web-development,python-django,video-making-editing-jobs/"
        ]
        for target in urls:
            try:
                resp = self.http.get(target)
                if resp.status_code != 200:
                    continue
                soup = BeautifulSoup(resp.text, "html.parser")
                cards = soup.select("div.individual_internship")
                for card in cards:
                    title_elem = card.select_one("a.job-title-href") or card.select_one("h2.job-internship-name a")
                    if not title_elem:
                        continue
                    title = " ".join(title_elem.get_text().split())
                    href = title_elem.get("href", "")
                    url = urljoin("https://internshala.com", href)

                    comp_elem = card.select_one(".company-name") or card.select_one(".company_name")
                    company = " ".join(comp_elem.get_text().split()) if comp_elem else "Internshala Employer"

                    loc_elem = card.select_one(".locations")
                    location = " ".join(loc_elem.get_text().split()) if loc_elem else "India"
                    is_remote = "work from home" in location.lower() or "remote" in location.lower()

                    stipend_elem = card.select_one(".stipend")
                    salary = " ".join(stipend_elem.get_text().split()) if stipend_elem else "Unspecified"

                    desc_elem = card.select_one(".about_job .text")
                    desc = " ".join(desc_elem.get_text().split()) if desc_elem else title

                    norm_job = self.build_normalized_job(
                        title=title,
                        company=company,
                        location=location,
                        description=desc,
                        url=url,
                        posted_at=datetime.now(timezone.utc).isoformat(),
                        experience="0-1 years (Fresher)",
                        salary=salary,
                        remote=is_remote
                    )
                    normalized.append(norm_job)
            except Exception as exc:
                print(f"[warn] InternshalaSource: {exc}")
        return normalized
