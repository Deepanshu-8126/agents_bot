from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from app.models.job import NormalizedJob
from app.database.repository import JobRepository
from app.sources import get_registered_sources, JobSource
from app.filters.deduplication import is_same_cross_source_job
from app.filters.exclusion_filter import should_exclude
from app.filters.keyword_filter import matches_keywords
from app.filters.experience_filter import qualifies_experience
from app.location.distance import matches_location_radius, calculate_distance

class JobHunterService:
    def __init__(self, repo: JobRepository = None, sources: List[JobSource] = None):
        self.repo = repo or JobRepository()
        self.sources = sources or get_registered_sources()

        # Register sources in database
        for s in self.sources:
            self.repo.register_source(s.source_id, s.name)

    def fetch_all_raw_jobs(self) -> List[NormalizedJob]:
        """Query all active adapters and return combined raw normalized jobs."""
        all_jobs = []
        for src in self.sources:
            try:
                jobs = src.fetch_jobs()
                self.repo.update_source_stats(src.source_id, len(jobs))
                all_jobs.extend(jobs)
            except Exception as exc:
                print(f"[warn] Source {src.name} failed: {exc}")
        return all_jobs



    def discover_and_filter(self, chat_id: str, raw_jobs: List[NormalizedJob] = None) -> List[NormalizedJob]:
        """Fetch, deduplicate against database, filter by user keywords, location radius, and experience."""
        pref = self.repo.get_user_preference(chat_id)
        city = pref.get("city", "Haldwani")
        radius_km = float(pref.get("radius_km", 100.0))
        max_exp = int(pref.get("max_experience_years", 2))

        keywords = self.repo.get_keywords(chat_id)
        excludes = self.repo.get_excludes(chat_id)

        candidates = raw_jobs if raw_jobs is not None else self.fetch_all_raw_jobs()
        filtered_jobs: List[NormalizedJob] = []
        seen_cross_source = []

        for j in candidates:
            # 1. Exclusion filter (senior, manager, 10+ yrs, or user exclusions)
            if should_exclude(j.title, j.description, excludes):
                continue

            # 2. Experience filter (0-2 years, fresher)
            if not qualifies_experience(j.experience, max_exp):
                continue

            # 3. Keyword filter
            searchable_text = f"{j.title} {j.description} {' '.join(j.skills)}"
            if keywords and not matches_keywords(searchable_text, keywords):
                continue

            # 4. Location & Distance filter
            matches_loc, dist = matches_location_radius(j.location, city, radius_km)
            if not matches_loc:
                continue
            j.distance_km = dist

            # 5. Cross-source duplicate detection
            duplicate = False
            for seen_t, seen_c in seen_cross_source:
                if is_same_cross_source_job(j.title, j.company, seen_t, seen_c):
                    duplicate = True
                    break
            if duplicate:
                continue
            seen_cross_source.append((j.title, j.company))

            # 6. Database duplicate check & persistence
            self.repo.insert_job(j)
            filtered_jobs.append(j)

        # Sort: Local/closest first, then Remote, then newest
        filtered_jobs.sort(key=lambda x: (
            x.distance_km is None, # Numerical distance first
            x.distance_km if x.distance_km is not None else 9999,
            x.posted_at or ""
        ))
        return filtered_jobs
