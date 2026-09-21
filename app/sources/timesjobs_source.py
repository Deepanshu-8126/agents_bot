from typing import List
from datetime import datetime, timezone
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from app.sources.base import JobSource
from app.models.job import NormalizedJob

class TimesJobsSource(JobSource):
    """TimesJobs public RSS feed adapter."""
    def __init__(self):
        super().__init__("timesjobs", "TimesJobs")

    def fetch_jobs(self) -> List[NormalizedJob]:
        normalized = []
        rss_urls = [
            "https://www.timesjobs.com/candidate/rss.html?category=it-software",
            "https://www.timesjobs.com/candidate/rss.html?category=analytics"
        ]
        for url in rss_urls:
            try:
                res = self.http.get(url)
                if res.status_code == 200:
                    try:
                        root = ET.fromstring(res.text)
                        for item in root.findall(".//item"):
                            title_elem = item.find("title")
                            link_elem = item.find("link")
                            desc_elem = item.find("description")
                            pub_elem = item.find("pubDate")

                            if title_elem is None or not title_elem.text:
                                continue
                            title = title_elem.text.strip()
                            url_val = link_elem.text.strip() if link_elem is not None else ""
                            raw_desc = desc_elem.text if desc_elem is not None else title
                            desc = BeautifulSoup(raw_desc or "", "html.parser").get_text(" ").strip()

                            norm = self.build_normalized_job(
                                title=title,
                                company="TimesJobs Partner",
                                location="India",
                                description=desc,
                                url=url_val,
                                posted_at=pub_elem.text if pub_elem is not None else datetime.now(timezone.utc).isoformat(),
                                experience="0-1 years"
                            )
                            normalized.append(norm)
                    except Exception:
                        pass
            except Exception as exc:
                print(f"[warn] TimesJobsSource: {exc}")
        return normalized
