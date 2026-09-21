from typing import List
from datetime import datetime, timezone
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from app.sources.base import JobSource
from app.models.job import NormalizedJob

class FreshersworldSource(JobSource):
    """Freshersworld adapter consuming public fresher feeds."""
    def __init__(self):
        super().__init__("freshersworld", "Freshersworld")

    def fetch_jobs(self) -> List[NormalizedJob]:
        normalized = []
        feeds = [
            "https://www.freshersworld.com/jobs/rss-feeds/it-jobs",
            "https://www.freshersworld.com/jobs/rss-feeds/b-tech-jobs"
        ]
        for f in feeds:
            try:
                res = self.http.get(f)
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
                            full_title = title_elem.text.strip()
                            parts = full_title.split(" in ")
                            title = parts[0]
                            loc = parts[1] if len(parts) > 1 else "India"

                            url_val = link_elem.text.strip() if link_elem is not None else ""
                            raw_desc = desc_elem.text if desc_elem is not None else title
                            desc = BeautifulSoup(raw_desc or "", "html.parser").get_text(" ").strip()

                            norm = self.build_normalized_job(
                                title=title,
                                company="Freshersworld Employer",
                                location=loc,
                                description=desc,
                                url=url_val,
                                posted_at=pub_elem.text if pub_elem is not None else datetime.now(timezone.utc).isoformat(),
                                experience="0-1 years (Fresher)"
                            )
                            normalized.append(norm)
                    except Exception:
                        pass
            except Exception as exc:
                print(f"[warn] FreshersworldSource: {exc}")
        return normalized
