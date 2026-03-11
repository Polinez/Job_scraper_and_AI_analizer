from typing import List, Set
import pandas as pd
from jobspy import scrape_jobs
from src.scrapers.base import BaseScraper
from src.models import Job
from src.utils.logger import logger

class JobSpyScraper(BaseScraper):
    def __init__(self, seen_urls: Set[str] = None):
        super().__init__(seen_urls)
        self.site_names = ["Indeed", "LinkedIn"]

    def scrape(self, search_term: str, location: str, is_remote: bool, hours_old: int = 48) -> List[Job]:
        logger.info(f"Uruchamiam JobSpy dla: {search_term}")
        
        try:
            # Import SeleniumScraper logic for filtering
            from src.scrapers.selenium_scraper import SeleniumScraper
            filter_engine = SeleniumScraper()
            required_groups, excludes = filter_engine._parse_strict_query(search_term)

            jobs_df = scrape_jobs(
                site_name=self.site_names,
                search_term=search_term,
                location=location,
                distance=0,
                is_remote=is_remote,
                results_wanted=50,
                hours_old=hours_old,
                country_indeed='Poland',
                linkedin_fetch_description=True,
                description_format="markdown"
            )

            if jobs_df.empty:
                return []

            results = []
            for _, row in jobs_df.iterrows():
                url = row.get('job_url')
                if self.is_seen(url):
                    continue
                
                title = row.get('title', 'Unknown')
                # APLIKUJEMY FILTR TYTUŁU
                if not filter_engine._matches_strict_query(title, required_groups, excludes):
                    continue

                try:
                    job = Job(
                        title=title,
                        company=row.get('company', 'Unknown'),
                        location=row.get('location', location),
                        job_url=url,
                        site=row.get('site', 'JobSpy'),
                        description=row.get('description'),
                        posted_at=str(row.get('date_posted', ''))
                    )
                    results.append(job)
                except Exception:
                    continue

            logger.info(f"JobSpy znalazł {len(results)} nowych ofert po filtracji.")
            return results

        except Exception as e:
            logger.error(f"Krytyczny błąd JobSpy: {e}")
            return []
