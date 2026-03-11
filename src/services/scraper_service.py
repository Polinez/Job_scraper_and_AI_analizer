import os
import json
import pandas as pd
from typing import List, Set
from src.scrapers.jobspy_scraper import JobSpyScraper
from src.scrapers.selenium_scraper import PolishSitesScraper
from src.models import Job
from src.utils.logger import logger

class ScraperService:
    def __init__(self, data_folder: str = "Data"):
        self.data_folder = data_folder
        self.history_file = os.path.join(data_folder, "all_jobs_history.json")
        os.makedirs(data_folder, exist_ok=True)
        self.seen_urls = self._load_history()

    def _load_history(self) -> Set[str]:
        if os.path.exists(self.history_file):
            try:
                df = pd.read_json(self.history_file)
                if not df.empty and 'job_url' in df.columns:
                    return set(df['job_url'].astype(str).tolist())
            except Exception as e:
                logger.warning(f"Błąd ładowania historii: {e}")
        return set()

    def _deduplicate_jobs(self, jobs: List[Job]) -> List[Job]:
        if not jobs:
            return []
        
        df = pd.DataFrame([j.model_dump() for j in jobs])
        df['job_url'] = df['job_url'].astype(str)
        df['title_norm'] = df['title'].str.lower().str.strip()
        df['company_norm'] = df['company'].str.lower().str.strip()
        
        # Keep only the last occurrence of (Title + Company)
        df.drop_duplicates(subset=['title_norm', 'company_norm', 'location'], keep='last', inplace=True)
        
        # Convert back to Job objects
        clean_data = df.to_dict(orient="records")
        return [Job(**j) for j in clean_data]

    def _update_history(self, new_jobs: List[Job]):
        if not new_jobs:
            return
        
        new_data = [job.model_dump() for job in new_jobs]
        for job in new_data:
            job['job_url'] = str(job['job_url'])
            job['title_norm'] = job['title'].lower().strip()
            job['company_norm'] = job['company'].lower().strip()
            
        if os.path.exists(self.history_file):
            try:
                df_old = pd.read_json(self.history_file)
                if not df_old.empty:
                    df_old['title_norm'] = df_old['title'].str.lower().str.strip()
                    df_old['company_norm'] = df_old['company'].str.lower().str.strip()
                df_updated = pd.concat([df_old, pd.DataFrame(new_data)], ignore_index=True)
            except Exception:
                df_updated = pd.DataFrame(new_data)
        else:
            df_updated = pd.DataFrame(new_data)
            
        df_updated.drop_duplicates(subset=['job_url'], keep='last', inplace=True)
        df_updated.drop_duplicates(subset=['title_norm', 'company_norm', 'location'], keep='last', inplace=True)
        
        if 'title_norm' in df_updated.columns: del df_updated['title_norm']
        if 'company_norm' in df_updated.columns: del df_updated['company_norm']
        
        df_updated.to_json(self.history_file, orient="records", indent=4, force_ascii=False)

    def find_all_jobs(self, search_query: str, location: str, remote_only: bool, max_days_old: int) -> List[Job]:
        # 1. JobSpy
        jobspy = JobSpyScraper(self.seen_urls)
        js_jobs = jobspy.scrape(search_query, location, remote_only, hours_old=24 * max_days_old)
        
        # 2. Selenium
        selenium_scraper = PolishSitesScraper(self.seen_urls)
        sel_jobs = selenium_scraper.scrape_all(search_query, location, remote_only)
        
        combined_jobs = js_jobs + sel_jobs
        
        # Final deduplication by Title + Company before returning
        unique_new_jobs = self._deduplicate_jobs(combined_jobs)
        
        if unique_new_jobs:
            self._update_history(unique_new_jobs)
            for job in unique_new_jobs:
                self.seen_urls.add(str(job.job_url))
            logger.info(f"Koniec skanowania. Znaleziono {len(unique_new_jobs)} całkowicie nowych, unikalnych ofert.")
                
        return unique_new_jobs
