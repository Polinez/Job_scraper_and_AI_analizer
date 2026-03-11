import json
import os
from pathlib import Path
from src.config import load_config
from src.services.cv_service import CVService
from src.services.scraper_service import ScraperService
from src.services.ai_service import AIService
from src.services.notification_service import NotificationService
from src.utils.logger import logger

def build_search_query(config) -> str:
    titles = config.job_titles
    levels = config.experience_levels
    excludes = config.exclude_keywords

    titles_str = " OR ".join([f'"{t}"' for t in titles])
    query = f"({titles_str})"

    if levels:
        levels_str = " OR ".join([f'"{l}"' for l in levels])
        query += f" AND ({levels_str})"

    if excludes:
        excludes_str = " ".join([f"-{e}" for e in excludes])
        query += f" {excludes_str}"

    return query.strip()

def main():
    try:
        # 1. Load Configuration
        config = load_config()
        logger.info("Konfiguracja załadowana pomyślnie.")

        # 2. Extract CV Text
        cv_service = CVService()
        cv_text = cv_service.load_cv_text(config.cv_path)
        if not cv_text:
            logger.error("Nie udało się załadować tekstu z CV. Przerywam.")
            return

        # 3. Search for Jobs
        search_query = build_search_query(config)
        logger.info(f"Wyszukiwanie ofert dla zapytania: {search_query}")
        
        scraper_service = ScraperService()
        jobs = scraper_service.find_all_jobs(
            search_query=search_query,
            location=config.location,
            remote_only=config.remote_only,
            max_days_old=config.max_days_old
        )
        
        if not jobs:
            logger.info("Brak nowych ofert do przeanalizowania.")
            return

        # 4. Analyze Jobs with AI
        ai_service = AIService(api_key=config.google_api_key, model_name=config.model_name)
        analysis_results = []
        
        for job in jobs:
            result = ai_service.analyze_job(job, cv_text)
            if result:
                analysis_results.append(result)

        # 5. Save results & Notify
        if analysis_results:
            results_path = Path("Data/job_analysis_results.json")
            # Convert to dict for JSON serialization
            serializable_results = [r.model_dump() for r in analysis_results]
            for r in serializable_results:
                r['url'] = str(r['url']) # Convert HttpUrl to string
            
            # Load existing history if any
            if results_path.exists():
                with open(results_path, 'r', encoding='utf-8') as f:
                    try:
                        history = json.load(f)
                    except:
                        history = []
            else:
                history = []
            
            history.extend(serializable_results)
            
            with open(results_path, 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False, indent=4)
            
            logger.info(f"Zapisano {len(analysis_results)} wyników analizy AI.")
            
            # Send Email
            if config.sender_email:
                notifier = NotificationService(
                    sender_email=config.sender_email,
                    sender_password=config.sender_password,
                    recipient_email=config.recipient_email
                )
                notifier.send_summary_email(analysis_results)
        else:
            logger.info("Brak nowych unikalnych analiz do zapisania.")

    except Exception as e:
        logger.exception(f"Wystąpił krytyczny błąd podczas pracy aplikacji: {e}")

if __name__ == "__main__":
    main()
