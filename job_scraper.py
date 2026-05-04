#job scraper documentation:
# https://github.com/speedyapply/JobSpy?tab=readme-ov-file
import pandas as pd
import os
import requests
from jobspy import scrape_jobs
from other_job_scraper import scrape_other_sites

DATA_FOLDER_PATH = "Data"
HISTORY_FILE_PATH = os.path.join(DATA_FOLDER_PATH, "all_jobs_history.json")
AI_INPUT_FILE_PATH = os.path.join(DATA_FOLDER_PATH, "jobs_for_ai.json")
SITE_NAMES = ["Indeed", "LinkedIn"]


def _load_history_urls() -> set:
    # check if data folder exists, if not create it
    os.makedirs(DATA_FOLDER_PATH, exist_ok=True)

    seen_urls = set()

    # Load history of seen URLs to avoid duplicates
    if os.path.exists(HISTORY_FILE_PATH):
        try:
            df_history = pd.read_json(HISTORY_FILE_PATH)
            if not df_history.empty and 'job_url' in df_history.columns:
                seen_urls = set(df_history['job_url'].tolist())
            print(f"📚 Załadowano historię: {len(seen_urls)} ofert.")
        except ValueError:
            print("⚠️ Plik historii uszkodzony lub pusty, tworzę nowy.")

    return seen_urls


def _save_ai_input(df: pd.DataFrame):
    if not df.empty:
        df.to_json(AI_INPUT_FILE_PATH, orient="records", indent=4, force_ascii=False)
        print(f"💾 Zapisano plik roboczy '{AI_INPUT_FILE_PATH}'")
    else:
        # Clean AI input file if no new jobs to process
        with open(AI_INPUT_FILE_PATH, 'w') as f:
            f.write("[]")
        print("🏁 Brak ofert do przetworzenia (plik wyczyszczony).")


def _update_history(new_jobs_df: pd.DataFrame):
    if new_jobs_df.empty:
        print("📚 Archiwum aktualne (brak nowych unikalnych ofert do dopisania).")
        return

    if os.path.exists(HISTORY_FILE_PATH):
        try:
            df_old = pd.read_json(HISTORY_FILE_PATH)
            df_updated = pd.concat([df_old, new_jobs_df], ignore_index=True)
        except ValueError:
            df_updated = new_jobs_df
    else:
        df_updated = new_jobs_df

    df_updated.to_json(HISTORY_FILE_PATH, orient="records", indent=4, force_ascii=False)
    print(f"📚 Zaktualizowano archiwum '{HISTORY_FILE_PATH}' (+{len(new_jobs_df)} nowych).")


def _perform_scrape(site_name, search_term, location, distance,
                    is_remote, results_wanted, hours_old, country_indeed,
                    linkedin_fetch_description, description_format) -> list[dict]:
    try:
        jobs_df = scrape_jobs(
            site_name=site_name,
            search_term=search_term,
            location=location,
            distance=distance,
            is_remote=is_remote,
            results_wanted=results_wanted,
            hours_old=hours_old,
            country_indeed=country_indeed,
            linkedin_fetch_description=linkedin_fetch_description,
            description_format=description_format
        )

        if not jobs_df.empty:
            count = len(jobs_df)
            # Zmieniono komunikat na bardziej opisowy dla JobSpy
            print(f"   ---> JobSpy znalazł: {count} ({location}, remote={is_remote})")
            return jobs_df.to_dict(orient="records")
        else:
            print(f"   ---> JobSpy: Brak wyników dla ({location}).")
            return []

    except Exception as e:
        print(f"❌ Błąd podczas skrapowania API ({location}, remote={is_remote}): {e}")
        return []


def _process_job_list(all_jobs: list) -> pd.DataFrame:
    if not all_jobs:
        return pd.DataFrame()

    df = pd.DataFrame(all_jobs)

    # Remove duplicates within the current batch (if any)
    if 'job_url' in df.columns:
        df = df.drop_duplicates(subset=['job_url'])

    # Advanced duplicate removal based on title and company name
    if 'title' in df.columns and 'company' in df.columns:
        df['title_norm'] = df['title'].astype(str).str.lower().str.strip()
        df['company_norm'] = df['company'].astype(str).str.lower().str.strip()

        # We remove duplicates, keeping only the first occurrence of each pair (title + company)
        df = df.drop_duplicates(subset=['title_norm', 'company_norm'], keep='first')

        # We remove auxiliary columns so they don't clutter the final data
        df = df.drop(columns=['title_norm', 'company_norm'])

    return df


def find_jobs(search: str, location: str = "Katowice", h_old: int = 24, remote: bool = False,filter_history: bool = True) -> list[dict]:
    # Load history of seen URLs to avoid duplicates across both Selenium and API scrapes
    seen_urls = _load_history_urls()

    # SELENIUM (JustJoinIT, NoFluffJobs, LinkedIn Manual )
    urls_to_skip_for_selenium = seen_urls.copy() if filter_history else set()
    selenium_jobs = scrape_other_sites(search, location, remote, urls_to_skip_for_selenium)

    # API (JobSpy - Indeed, LinkedIn API) ---
    print(f"\n📡 [API] Uruchamiam JobSpy...")

    # Local
    jobspy_local = _perform_scrape(
        site_name=SITE_NAMES,
        search_term=search,
        location=location,
        distance=0,
        is_remote=False,
        results_wanted=50,
        hours_old=h_old,
        country_indeed='Poland',
        linkedin_fetch_description=True,
        description_format="markdown")

    # Remote
    jobspy_remote = []
    if remote:
        jobspy_remote = _perform_scrape(
            site_name=SITE_NAMES,
            search_term=search,
            location="Poland",
            distance=0,
            is_remote=True,
            results_wanted=50,
            hours_old=h_old,
            country_indeed='Poland',
            linkedin_fetch_description=True,
            description_format="markdown")

    # Combine local and remote results for JobSpy before filtering
    raw_jobspy_list = jobspy_local + jobspy_remote
    raw_jobspy_count = len(raw_jobspy_list)

    # filter jobspy results based on history (if enabled) and also add to seen_urls to avoid duplicates with Selenium results
    new_jobspy_list = []
    jobspy_filtered_out = 0

    for job in raw_jobspy_list:
        if filter_history and job['job_url'] in seen_urls:
            jobspy_filtered_out += 1
        else:
            new_jobspy_list.append(job)
            seen_urls.add(job['job_url'])

    #  COMBINE AND RAPORT
    all_final_list = selenium_jobs + new_jobspy_list
    df_current = _process_job_list(all_final_list)

    print("\n📝 === PODSUMOWANIE SESJI ===")

    # Raport API
    print(f"API (JobSpy):")
    print(f"   -> Znaleziono łącznie: {raw_jobspy_count}")
    if filter_history:
        print(f"   -> Odrzucono (historia): {jobspy_filtered_out}")
    print(f"   -> Nowe unikalne: {len(new_jobspy_list)}")

    # Selenium
    print(f"Selenium (Custom Scrapers):")
    print(f"   -> Nowe unikalne (dopisane): {len(selenium_jobs)}")

    total_new = len(df_current)
    print(f"\n✅ ŁĄCZNIE NOWYCH OFERT: {total_new}")
    print("==============================\n")

    # save files
    if not df_current.empty:
        _save_ai_input(df_current)
        _update_history(df_current)
    else:
        _save_ai_input(pd.DataFrame())
        print("📚 Archiwum aktualne (brak nowych ofert).")

    return df_current.to_dict(orient="records")