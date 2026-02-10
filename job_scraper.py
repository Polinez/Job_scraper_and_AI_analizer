#https://github.com/speedyapply/JobSpy?tab=readme-ov-file
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
            print(f"   ---> Znaleziono: {count}")
            return jobs_df.to_dict(orient="records")
        else:
            print(f"   ---> Brak wyników.")
            return []

    except Exception as e:
        print(f"❌ Błąd podczas skrapowania ({location}, remote={is_remote}): {e}")
        return []


def _process_job_list(all_jobs: list) -> pd.DataFrame:
    if not all_jobs:
        return pd.DataFrame()

    df = pd.DataFrame(all_jobs)

    # Remove duplicates within the current batch (if any)
    if 'job_url' in df.columns:
        df = df.drop_duplicates(subset=['job_url'])

    return df

def find_jobs(search:str, location:str = "Katowice", h_old:int = 24, remote:bool = False, filter_history:bool = True
              )->list[dict]:


    # load history of seen URLs
    seen_urls = _load_history_urls()
    all_jobs_list = []

    #Selenium (JustJoinIT, NoFluffJobs, BulldogJob, TheProtocol)
    urls_to_skip = seen_urls if filter_history else None

    selenium_jobs = scrape_other_sites(search, location, remote, urls_to_skip)
    all_jobs_list.extend(selenium_jobs)

    # search for local jobs
    local_jobs = _perform_scrape(
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
    all_jobs_list.extend(local_jobs)


    # search for remote jobs (if enabled)
    if remote:
        remote_jobs = _perform_scrape(
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
        all_jobs_list.extend(remote_jobs)

    # preprocess the combined job list into a DataFrame
    df_current = _process_job_list(all_jobs_list)

    if df_current.empty:
        print("⚠️ Nie znaleziono żadnych ofert w obu krokach.")
        return []

    print(f"\n✅ Łącznie pobrano unikalnych ofert (w tej sesji): {len(df_current)}")

    # filert, truly_new_jobs_df->
    # whats new in current batch compared to history, this is what we will save to history and pass to AI
    # ~ = Not
    truly_new_jobs_df = df_current[~df_current['job_url'].isin(seen_urls)]

    # final_output_df -> return to user
    if filter_history:
        final_output_df = truly_new_jobs_df
        print(f"♻️  Filtr historii WŁĄCZONY. Ukryto {len(df_current) - len(final_output_df)} znanych ofert.")
    else:
        final_output_df = df_current
        print(f"👀 Filtr historii WYŁĄCZONY. Zwracam wszystkie {len(final_output_df)} ofert.")

    # save files
    _save_ai_input(final_output_df)
    _update_history(truly_new_jobs_df)

    return final_output_df.to_dict(orient="records")

