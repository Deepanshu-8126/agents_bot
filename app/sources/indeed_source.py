from typing import List
from datetime import datetime, timezone
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from app.sources.base import JobSource
from app.models.job import NormalizedJob

class IndeedSource(JobSource):
    """Indeed adapter consuming official public RSS job feeds."""
    def __init__(self):
        super().__init__("indeed", "Indeed")

    def fetch_jobs(self) -> List[NormalizedJob]:
        normalized = []
        rss_feeds = [
            "https://in.indeed.com/rss?q=data+analyst+fresher&l=India",
            "https://in.indeed.com/rss?q=software+developer+entry+level&l=India",
            "https://in.indeed.com/rss?q=video+editor+fresher&l=India"
        ]
        for feed in rss_feeds:
            try:
                res = self.http.get(feed)
                if res.status_code != 200:
                    continue
                root = ET.fromstring(res.text)
                for item in root.findall(".//item"):
                    title_elem = item.find("title")
                    link_elem = item.find("link")
                    desc_elem = item.find("description")
                    pub_elem = item.find("pubDate")
                    source_elem = item.find("source")

                    if title_elem is None or not title_elem.text:
                        continue
                    full_title = title_elem.text.strip()
                    # Indeed titles are often "Job Title - Company - Location"
                    parts = full_title.split(" - ")
                    title = parts[0]
                    company = parts[1] if len(parts) > 1 else (source_elem.text if source_elem is not None else "Indeed Employer")
                    location = parts[2] if len(parts) > 2 else "India"

                    raw_desc = desc_elem.text if desc_elem is not None else title
                    desc = BeautifulSoup(raw_desc or "", "html.parser").get_text(" ").strip()
                    url = link_elem.text.strip() if link_elem is not None else ""

                    norm = self.build_normalized_job(
                        title=title,
                        company=company,
                        location=location,
                        description=desc,
                        url=url,
                        posted_at=pub_elem.text if pub_elem is not None else datetime.now(timezone.utc).isoformat(),
                        experience="0-1 years",
                        remote="remote" in location.lower() or "remote" in desc.lower()
                    )
                    normalized.append(norm)
            except Exception as exc:
                print(f"[warn] IndeedSource: {exc}")
        return normalized
