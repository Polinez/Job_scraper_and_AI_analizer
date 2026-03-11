from abc import ABC, abstractmethod
from typing import List, Set
from src.models import Job

class BaseScraper(ABC):
    def __init__(self, seen_urls: Set[str] = None):
        self.seen_urls = seen_urls or set()

    @abstractmethod
    def scrape(self, search_term: str, location: str, is_remote: bool, **kwargs) -> List[Job]:
        pass

    def is_seen(self, url: str) -> bool:
        return str(url) in self.seen_urls
