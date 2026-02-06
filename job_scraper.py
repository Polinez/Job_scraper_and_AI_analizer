#https://github.com/speedyapply/JobSpy?tab=readme-ov-file
import pandas as pd
import csv
import os
from jobspy import scrape_jobs

def find_jobs(serch)->list[dict]:

    site_names = ["Indeed", "LinkedIn"]

    all_jobs = []

    jobs_local = scrape_jobs(
        site_name=site_names,
        search_term=serch,
        location="Katowice",
        distance=10,
        is_remote=False,
        results_wanted=50,
        hours_old=336,
        country_indeed='Poland',
        linkedin_fetch_description=True,
        description_format="markdown",
    )
    print(f"   ---> Znaleziono lokalnie: {len(jobs_local)}")
    if not jobs_local.empty:
        all_jobs.extend(jobs_local.to_dict(orient="records"))

    jobs_remote = scrape_jobs(
        site_name=site_names,
        search_term=serch,
        location="Poland",
        is_remote=True,
        results_wanted=50,
        hours_old=168,
        country_indeed='Poland',
        linkedin_fetch_description=True,
        description_format="markdown",
    )
    print(f"   ---> Znaleziono zdalnie: {len(jobs_remote)}")
    if not jobs_remote.empty:
        all_jobs.extend(jobs_remote.to_dict(orient="records"))

    print(f"\n✅ Łącznie znaleziono unikalnych ofert: {len(all_jobs)}")

    if all_jobs:
        # To DataFrame to convert to json
        df_all = pd.DataFrame(all_jobs)

        # Remove duplicates
        df_all = df_all.drop_duplicates(subset=['job_url'])

        # Save to json file
        file_name = "jobs_for_ai.json"
        df_all.to_json(file_name, orient="records", indent=4, force_ascii=False)
        print(f"💾 Zapisano wyniki do '{file_name}'")

        return df_all.to_dict(orient="records")
    else:
        print("⚠️ Nie znaleziono żadnych ofert w obu krokach.")
        return []
