import os
import platform
from job_analizer_llm import analyze_jobs_with_ai
from job_scraper import find_jobs
from cv_to_text import load_cv_text


#job scraper documentation:
# https://github.com/speedyapply/JobSpy?tab=readme-ov-file

# check os used
current_os = platform.system()

if current_os == "Darwin": # macOS
    cv_path = os.path.join("/", "Users", "sebastian", "Desktop", "praca", "SebastianWandzel.pdf")
elif current_os == "Windows": # PC
    # "C:\Users\Sebastian\Desktop\SynologyDrive\praca\SebastianWandzelPOL.pdf"
    cv_path = os.path.join("C:\\", "Users", "Sebastian", "Desktop", "SynologyDrive", "praca" , "SebastianWandzel.pdf")
else:
    raise OSError(f"Nieobsługiwany system operacyjny: {current_os}")

cv_text =load_cv_text(cv_path)

# Finding job offers and returning to list of dicts
search = """
("Data Scientist" OR "Data Engineer" OR "Machine Learning" OR "Deep Learning" OR "NLP" OR "Artificial Intelligence" OR "GenAI" OR "Big Data" OR "Python Developer")
AND
("Junior" OR "Intern" OR "Staż" OR "Trainee" OR "Młodszy" OR "Praktyka" OR "Asystent" OR "Graduate")
-Senior -B2B
"""
search = search.replace("\n", " ").strip()
jobs_list = find_jobs(search=search,
                      location="Katowice",
                      h_old=24*2, # 2 days
                      remote=False,
                      filter_history=True
                      )

# getting cv analizeed to evry job role
list_of_dict = analyze_jobs_with_ai(jobs_list,cv_text)

#TODO: Add RUG system like here https://github.com/gopiashokan/AI-Resume-Analyzer-and-LinkedIn-Scraper-using-Generative-AI




