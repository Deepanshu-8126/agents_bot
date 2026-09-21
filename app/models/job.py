from dataclasses import dataclass, field, asdict
from typing import List, Optional
import json

@dataclass
class NormalizedJob:
    job_id: str
    title: str
    company: str
    location: str
    description: str
    url: str
    source: str
    posted_at: str
    experience: str = "0-1 years"
    salary: str = "Not Disclosed"
    skills: List[str] = field(default_factory=list)
    remote: bool = False
    distance_km: Optional[float] = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "NormalizedJob":
        skills = data.get("skills", [])
        if isinstance(skills, str):
            try:
                skills = json.loads(skills)
            except Exception:
                skills = [s.strip() for s in skills.split(",") if s.strip()]
        return cls(
            job_id=str(data.get("job_id", "")),
            title=str(data.get("title", "")).strip(),
            company=str(data.get("company", "")).strip(),
            location=str(data.get("location", "")).strip(),
            description=str(data.get("description", "")).strip(),
            url=str(data.get("url", "")).strip(),
            source=str(data.get("source", "Unknown")).strip(),
            posted_at=str(data.get("posted_at", "")).strip(),
            experience=str(data.get("experience", "0-1 years")).strip(),
            salary=str(data.get("salary", "Not Disclosed")).strip(),
            skills=skills if isinstance(skills, list) else [],
            remote=bool(data.get("remote", False)),
            distance_km=float(data["distance_km"]) if data.get("distance_km") is not None else None,
        )

    def format_telegram(self) -> str:
        """Format matching exact user specification."""
        lines = [
            "NEW JOB\n",
            f"*{self.title}*",
            f"Company: {self.company}",
            f"Location: {self.location}",
        ]
        if self.distance_km is not None and not self.remote:
            lines.append(f"Distance: {round(self.distance_km)} km")
        elif self.remote:
            lines.append("Work Mode: Remote / WFH")

        if self.experience:
            lines.append(f"Experience: {self.experience}")
        lines.append(f"Source: {self.source}")
        lines.append("\nApply:")
        lines.append(f"{self.url}")
        return "\n".join(lines)
