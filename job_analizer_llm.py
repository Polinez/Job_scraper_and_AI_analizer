import os
import time

from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv
import json

from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field
from typing import List, Any, cast

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

load_dotenv()
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')


def _send_summary_email(analysis_results: list[dict]):
    # Pobieranie danych z .env
    sender = os.getenv("SENDER_EMAIL")
    password = os.getenv("SENDER_PASSWORD")
    recipient = os.getenv("RECIPIENT_EMAIL")

    if not all([sender, password, recipient]):
        print("❌ Błąd: Brak konfiguracji e-mail w .env")
        return

    # Generowanie bloków ofert w HTML
    job_blocks = []
    for item in analysis_results:
        analysis = item.get('analysis', {})
        score = analysis.get('match_score', 0)
        color = "#28a745" if score >= 70 else "#ffc107" if score >= 45 else "#dc3545"

        block = f"""
            <div style="margin-bottom: 20px; padding: 10px; border-left: 5px solid {color}; background-color: #f9f9f9;">
                <h3 style="margin: 0;">{item.get('title')} - <span style="color: #666;">{item.get('company')}</span></h3>
                <p style="margin: 5px 0;"><b>Dopasowanie:</b> <span style="color: {color}; font-size: 1.2em;">{score}/100</span></p>
                <p style="margin: 5px 0;"><b>Rekomendacja:</b> {analysis.get('advice')}</p>
                <a href="{item.get('url')}" style="color: #007bff;">Otwórz ofertę →</a>
            </div>"""
        job_blocks.append(block)

    # Składanie pełnego dokumentu HTML
    html_body = f"""
        <html>
            <body style="font-family: Arial, sans-serif; color: #333;">
                <h2 style="color: #2d5a27;">Wyniki analizy ofert pracy ({len(analysis_results)})</h2>
                <hr>
                {"".join(job_blocks)}
            </body>
        </html>"""

    # Przygotowanie i wysyłka wiadomości
    msg = MIMEMultipart()
    msg['From'], msg['To'], msg[
        'Subject'] = sender, recipient, f"Raport ofert - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    msg.attach(MIMEText(html_body, 'html'))

    try:
        # Użycie 'with' automatycznie zamyka połączenie (quit)
        with smtplib.SMTP("smtp.mail.yahoo.com", 587) as server:
            server.starttls()
            server.login(sender, password)
            server.send_message(msg)
        print("✅ E-mail wysłany pomyślnie!")
    except Exception as e:
        print(f"❌ Błąd wysyłki: {e}")


def _load_analysis_history(file_path: str) -> list:
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except (json.JSONDecodeError, ValueError):
            print("⚠️ Plik historii uszkodzony. Tworzę nową historię.")
    return []

class JobAnalysis(BaseModel):
    match_score: int = Field(description="Ocena dopasowania oferty do CV w skali 0-100")
    missing_skills: List[str] = Field(description="Lista brakujących umiejętności w języku polskim")
    advice: str = Field(description="Krótka porada dotycząca oferty w języku polskim, max 3 zdania")

def analyze_jobs_with_ai(jobs_list:list[dict], cv_text:str) -> list[Any] | None:
    CHAR_LIMIT = 8000

    AI_response_history_path = os.path.join("Data", "job_analysis_results.json")

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

    analysis_results = _load_analysis_history(AI_response_history_path)
    print(f"\n📚 Załadowano historię analiz AI: {len(analysis_results)} pozycji.")

    seen_urls = {item.get('url') for item in analysis_results if item.get('url')}

    print(f"\n🚀 Rozpoczynam analizę {len(jobs_list)} ofert...\n")

    for index, job in enumerate(jobs_list):

        job_url = job.get('job_url')
        job_title = job.get('title', 'Nieznane stanowisko')

        # Check duplication based on job URL
        if job_url in seen_urls:
            print(f"[{index + 1}] ⏭️  Pominięto (już w historii): {job_title}")
            continue

        # Download job description
        raw_description = job.get('description', '')
        if not raw_description:
            print(f"[{index + 1}] ⚠️ Brak opisu dla: {job_title}")
            continue

        print(f"[{index + 1}] 🤖 Analizowanie: {job_title}...")

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

                # add to results and seen urls
                analysis_results.append(result)
                seen_urls.add(job_url)

                # Print summary
                score = ai_data_dict.get('match_score', 0)
                print(f"   ---> Ocena: {score}/100 | Porada: {ai_data_dict.get('advice')}")

                # Save to json file
                with open(AI_response_history_path, "w", encoding="utf-8") as f:
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

    if analysis_results:
        _send_summary_email(analysis_results)

    return analysis_results