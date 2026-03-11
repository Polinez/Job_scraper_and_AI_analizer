import os
import json
import platform
from pathlib import Path
from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

load_dotenv()

class AppConfig(BaseSettings):
    # Paths
    cv_path_win: str
    cv_path_mac: str
    
    # Search settings
    job_titles: List[str]
    model_name: str = "gemini-3-flash-preview"
    experience_levels: List[str] = []
    exclude_keywords: List[str] = []
    location: str = "Katowice"
    remote_only: bool = False
    max_days_old: int = 14
    
    # API Keys & Email (from .env)
    google_api_key: str = Field(alias="GOOGLE_API_KEY")
    sender_email: Optional[str] = Field(None, alias="SENDER_EMAIL")
    sender_password: Optional[str] = Field(None, alias="SENDER_PASSWORD")
    recipient_email: Optional[str] = Field(None, alias="RECIPIENT_EMAIL")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_file_encoding="utf-8")

    @property
    def cv_path(self) -> Path:
        current_os = platform.system()
        if current_os == "Darwin":
            return Path(self.cv_path_mac)
        return Path(self.cv_path_win)

def load_config(config_path: str = "config.json") -> AppConfig:
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Nie znaleziono pliku {config_path}!")
    
    with open(config_path, "r", encoding="utf-8") as f:
        config_data = json.load(f)
    
    return AppConfig(**config_data)
