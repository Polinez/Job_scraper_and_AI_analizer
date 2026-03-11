from typing import List, Optional
from pydantic import BaseModel, Field, HttpUrl

class Job(BaseModel):
    title: str
    company: str
    location: str
    job_url: HttpUrl
    site: str
    description: Optional[str] = None
    posted_at: Optional[str] = None

class AnalysisResult(BaseModel):
    match_score: int = Field(description="Ocena dopasowania oferty do CV w skali 0-100")
    missing_skills: List[str] = Field(description="Lista brakujących umiejętności w języku polskim")
    advice: str = Field(description="Krótka porada dotycząca oferty w języku polskim, max 3 zdania")

class JobAnalysis(BaseModel):
    company: str
    title: str
    url: HttpUrl
    location: Optional[str] = None
    analysis: AnalysisResult
