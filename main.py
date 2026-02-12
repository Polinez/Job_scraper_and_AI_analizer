import os
from job_analizer_llm import analyze_jobs_with_ai
from job_scraper import find_jobs
from cv_to_text import load_cv_text


#job scraper documentation:
# https://github.com/speedyapply/JobSpy?tab=readme-ov-file

# Loading CV text
my_cv_eng_path_mac = os.path.join("/", "Users", "sebastian", "Desktop", "praca", "SebastianWandzel.pdf")
my_cv_eng_path_pc = os.path.join("C:\\", "Users", "Sebastian", "Desktop", "SynologyDrive", "praca" , "SebastianWandzel.pdf")

# "C:\Users\Sebastian\Desktop\SynologyDrive\praca\SebastianWandzelPOL.pdf"
# my_cv_pol_path = os.path.join("/", "Users", "sebastian", "Desktop", "praca", "SebastianWandzelPOL.pdf")
cv_text =load_cv_text(my_cv_eng_path_pc)

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
                      h_old=168*2, # 2 weeks
                      remote=False,
                      filter_history=False
                      )

# getting cv analizeed to evry job role
list_of_dict = analyze_jobs_with_ai(jobs_list,cv_text)

#TODO: Add RUG system like here https://github.com/gopiashokan/AI-Resume-Analyzer-and-LinkedIn-Scraper-using-Generative-AI




