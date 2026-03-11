import time
import json
from typing import List, Optional
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from src.models import AnalysisResult, Job, JobAnalysis
from src.utils.logger import logger

class AIService:
    def __init__(self, api_key: str, model_name: str = "gemini-1.5-flash"):
        self.llm = ChatGoogleGenerativeAI(
            model=model_name,
            api_key=api_key,
            temperature=0,
            max_retries=2,
        )
        self.structured_llm = self.llm.with_structured_output(AnalysisResult)
        self.prompt_template = ChatPromptTemplate.from_template("""
            Jesteś ekspertem HR. Przeanalizuj ofertę pracy pod kątem mojego CV.
            
            OFERTA PRACY:
            {description}
            
            MOJE CV:
            {cv}
        """)
        self.chain = self.prompt_template | self.structured_llm

    def analyze_job(self, job: Job, cv_text: str) -> Optional[JobAnalysis]:
        if not job.description:
            logger.warning(f"Brak opisu dla oferty: {job.title}")
            return None

        # Character limit for prompt
        char_limit = 8000
        description = job.description[:char_limit] if len(job.description) > char_limit else job.description

        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"Analizowanie oferty przez AI: {job.title} ({job.company})...")
                response = self.chain.invoke({
                    "description": description,
                    "cv": cv_text
                })
                
                # If response is already an AnalysisResult object
                analysis_result = response if isinstance(response, AnalysisResult) else AnalysisResult(**response)
                ai_data_dict = analysis_result.model_dump()

                return JobAnalysis(
                    company=job.company,
                    title=job.title,
                    url=job.job_url,
                    location=job.location,
                    analysis=analysis_result
                )

            except Exception as e:
                logger.warning(f"Błąd AI (Próba {attempt}/{max_retries}): {e}")
                if "429" in str(e):
                    time.sleep(65)
                else:
                    time.sleep(10 * attempt)
        
        logger.error(f"Nie udało się przeanalizować oferty po {max_retries} próbach: {job.title}")
        return None
