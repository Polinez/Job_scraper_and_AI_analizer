import os
import json
import platform
from job_analizer_llm import analyze_jobs_with_ai
from job_scraper import find_jobs
from cv_to_text import load_cv_text

# check os used
current_os = platform.system()

# Load configuration from JSON file
config_path = "config.json"
if not os.path.exists(config_path):
    raise FileNotFoundError(f"Nie znaleziono pliku {config_path}! Skopiuj szablon i ustaw swoje dane.")

with open(config_path, "r", encoding="utf-8") as f:
    config = json.load(f)

# Download CV path and other settings from config
if current_os == "Darwin": # macOS
    cv_path = config.get("cv_path_mac")
elif current_os == "Windows": # PC
    cv_path = config.get("cv_path_win")
else:
    raise OSError(f"Nieobsługiwany system operacyjny: {current_os}")
location = config.get("location", "")
remote_only = config.get("remote_only", False)
max_days_old = config.get("max_days_old", 2)

# Check if CV file exists
if not os.path.exists(cv_path):
    raise FileNotFoundError(f"Nie znaleziono pliku CV pod ścieżką: {cv_path}. Sprawdź plik config.json!")

cv_text = load_cv_text(cv_path)

# Build search query based on config
def build_search_query(config_data):
    titles = config_data.get("job_titles", [])
    levels = config_data.get("experience_levels", [])
    excludes = config_data.get("exclude_keywords", [])

    # Connect job titles with OR and wrap in parentheses
    titles_str = " OR ".join([f'"{t}"' for t in titles])
    query = f"({titles_str})"

    # Add experience levels with OR and wrap in parentheses, then connect with AND
    if levels:
        levels_str = " OR ".join([f'"{l}"' for l in levels])
        query += f" AND ({levels_str})"

    # Add excluded keywords with NOT
    if excludes:
        excludes_str = " ".join([f"-{e}" for e in excludes])
        query += f" {excludes_str}"

    return query.strip()

# Build the search query from config and find jobs
search_query = build_search_query(config)
print(f"Wygenerowane zapytanie: {search_query}")

jobs_list = find_jobs(
    search=search_query,
    location=location,
    h_old=24 * max_days_old,
    remote=remote_only,
    filter_history=True
)

# Analyze found jobs with AI and get results
print(f"Znaleziono {len(jobs_list)} ofert. Trwa analiza AI...")
# list_of_dict = analyze_jobs_with_ai(jobs_list, cv_text)
print("Analiza zakończona pomyślnie!")

