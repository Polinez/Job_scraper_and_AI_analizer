import os
import time

from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv
import json

from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field
from typing import List, Any

load_dotenv()
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')


class JobAnalysis(BaseModel):
    match_score: int = Field(description="Ocena dopasowania oferty do CV w skali 0-100")
    missing_skills: List[str] = Field(description="Lista brakujących umiejętności w języku polskim")
    advice: str = Field(description="Krótka porada dotycząca oferty w języku polskim, max 3 zdania")

def analyze_jobs_with_ai(jobs_list:list[dict], cv_text:str) -> list[Any] | None:
    CHAR_LIMIT = 8000

    llm = ChatGoogleGenerativeAI(
        model="gemini-3-flash-preview",
        api_key=GOOGLE_API_KEY,
        temperature=0,
        max_retries=2,
    )

    #use structured output
    structured_llm = llm.with_structured_output(JobAnalysis)

    # Using Polish language to prompt because its better based od scientific research.
    template = """
    Jesteś ekspertem HR. Przeanalizuj ofertę pod kątem mojego CV.

    OFERTA:
    {description}

    MOJE CV:
    {cv}
    """

    prompt = ChatPromptTemplate.from_template(template)
    chain = prompt | structured_llm # returns object of type JobAnalysis

    analysis_results = []
    print(f"\n Rozpoczynam analize {len(jobs_list)} ofert...\n")

    for index, job in enumerate(jobs_list):
        # Download job description
        raw_description = job.get('description', '')
        if not raw_description:
            continue

        print(f"[{index + 1}] Analizowanie: {job.get('title')}...")

        #
        desc_len = len(raw_description)

        if desc_len > CHAR_LIMIT:
            # Calculate how many characters are over the limit
            over_limit = desc_len - CHAR_LIMIT
            print(f"   ✂️  UWAGA: Opis przycięty! Oryginał: {desc_len} znaków (ucięto {over_limit}).")
            final_description = raw_description[:CHAR_LIMIT]
        else:
            final_description = raw_description

        max_retries = 5
        attempt = 0
        success = False

        while attempt < max_retries and not success:
            try:

                response = chain.invoke({
                    "description": final_description,
                    "cv": cv_text
                })

                ai_data_dict = response.dict()

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
                file_path = os.path.join("Data", "job_analysis_results.json")
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(analysis_results, f, ensure_ascii=False, indent=4)

                success = True


            except Exception as e:
                attempt += 1
                error_msg = str(e)
                print(f"   ❌ Błąd (Próba {attempt}/{max_retries}): {e}")
                if "429" in error_msg:
                    print("   ⏳ Limit zapytań! Czekam 65 sekund...")
                    time.sleep(65)
                elif "503" in error_msg or "502" in error_msg or "overloaded" in error_msg.lower():
                    wait_time = 20 * attempt
                    print(f"   🚧 Serwer przeciążony. Czekam {wait_time} sekund...")
                    time.sleep(wait_time)
                else:
                    print("   ⚠️ Inny błąd. Czekam 10 sekund i próbuję ponownie...")
                    time.sleep(10)
            if not success:
                print(f"   ⛔ POMINIĘTO: Nie udało się przeanalizować oferty mimo {max_retries} prób.")
            print("   💤 Czekam 15 sekund przed kolejną ofertą...")
            time.sleep(15)

        return analysis_results