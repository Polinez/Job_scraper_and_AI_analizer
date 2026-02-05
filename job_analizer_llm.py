import os
import re

from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv
import json

# load_dotenv()
# GEMINI_API = os.getenv('GEMINI_API')

def clean_json_string(json_str: str) -> str:
    """
    Deletes markdown symbols (```json ... ```) offen added by LLMs
    """
    cleaned = re.sub(r'^```json\s*', '', json_str, flags=re.MULTILINE)
    cleaned = re.sub(r'^```\s*', '', cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r'\s*```$', '', cleaned, flags=re.MULTILINE)
    return cleaned.strip()

def analyze_jobs_with_ai(jobs_list:list[dict], cv_text:str) -> list[dict]:

    llm = ChatOllama(
        model="llama3",
        temperature=0,
        format="json",
    )

    # Using Polish language to prompt because its better based od scientific research.
    template = """
    Jesteś ekspertem HR. Przeanalizuj ofertę pod kątem mojego CV.

    OFERTA:
    {description}

    MOJE CV:
    {cv}

    Wymagam odpowiedzi w CZYSTYM formacie JSON, zgodnym z poniższym schematem.
    Nie dodawaj żadnych wstępów ani znaczników markdown.
    
    Pamiętaj aby podawać wszystkie odpowiedzi w języku polskim.
    
    {{
        "match_score": 0-100 (jako liczba integer),
        "missing_skills": ["umiejętność 1", "umiejętność 2"],
        "advice": "krótka porada max 3 zdania"
    }}
    """

    prompt = ChatPromptTemplate.from_template(template)
    chain = prompt | llm

    analysis_results = []
    print(f"\n Starting analyzing {len(jobs_list)} offers...\n")

    for index, job in enumerate(jobs_list):
        if not job.get('description'): continue

        print(f"[{index + 1}] Analyzing: {job.get('title')}...")


        try:
            response = chain.invoke({
                "description": job.get('description')[:8000],
                "cv": cv_text
            })

            # cleaning response from markdown if any
            content_text = response.content
            cleaned_json_text = clean_json_string(content_text)

            #convert to dict
            ai_data_dict = json.loads(cleaned_json_text)

            result = {
                "company": job.get('company', 'Nieznana firma'),
                "title": job.get('title', 'Nieznane stanowisko'),
                "url": job.get('job_url'),
                "location": job.get('location'),
                "analysis": ai_data_dict
            }

            analysis_results.append(result)

            # Print summary
            score = ai_data_dict.get('match_score', 0)
            print(f"   ---> Ocena: {score}/100 | Porada: {ai_data_dict.get('advice')}")

            # Save to json file
            with open("job_analysis_results.json", "w", encoding="utf-8") as f:
                json.dump(analysis_results, f, ensure_ascii=False, indent=4)


        except json.JSONDecodeError:
            print(f"   ❌ Błąd: AI nie zwróciło poprawnego JSON-a. Treść: {response.content[:50]}...")
        except Exception as e:
            print(f"   ❌ Błąd ogólny: {e}")

    return analysis_results