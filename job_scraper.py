#https://github.com/speedyapply/JobSpy?tab=readme-ov-file
from jobspy import scrape_jobs

def find_jobs(serch)->list[dict]:

    site_names = ["Indeed", "LinkedIn"]

    jobs = scrape_jobs(
        site_name=site_names,
        search_term=serch,
        location="Katowice",
        distance=10,
        is_remote=False,
        results_wanted=100,
        hours_old=24,
        country_indeed='Poland',
        linkedin_fetch_description=True,
        description_format="markdown",
    )
    print(f"Found {len(jobs)} jobs")


    print(jobs["description"])

    if not jobs.empty:
        file_name = "jobs_for_ai.json"
        # Saves to CSV
        # jobs.to_csv(file_name, quoting=csv.QUOTE_NONNUMERIC, escapechar="\\", index=False)
        # print(f"Zapisano dane do '{file_name}.csv'")

        # Saves to JSON
        jobs.to_json(file_name, orient="records", indent=4, force_ascii=False)
        print(f"Zapisano dane do '{file_name}'.")
        return jobs.to_dict(orient="records")

    else:
        print("Nie znaleziono ofert. Spróbuj zmienić parametry wyszukiwania.")
        return []
