import os
from job_analizer_llm import analyze_jobs_with_ai
from job_scraper import find_jobs
from cv_to_text import load_cv_text


#job scraper documentation:
# https://github.com/speedyapply/JobSpy?tab=readme-ov-file

# Loading CV text
my_cv_eng_path = os.path.join("CVs", "SebastianWandzel.pdf")
# my_cv_pol_path = os.path.join("CVs", "SebastianWandzelPOL.pdf")
cv_text =load_cv_text(my_cv_eng_path)

# Finding job offers and returning to list of dicts
search = """
("Data Scientist" OR "Data Engineer" OR "Machine Learning" OR "Deep Learning" OR "NLP" OR "Artificial Intelligence" OR "GenAI" OR "Big Data" OR "Python Developer")
("Junior" OR "Intern" OR "Staż" OR "Trainee" OR "Młodszy" OR "Praktyka" OR "Asystent" OR "Graduate")
-Senior -B2B
"""
search = search.replace("\n", " ").strip()
jobs_list = find_jobs(search)

# getting cv analizeed to evry job role
list_of_dict = analyze_jobs_with_ai(jobs_list,cv_text)




