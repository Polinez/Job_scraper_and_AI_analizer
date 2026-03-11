import time
import re
import random
from typing import List, Set, Tuple
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from urllib.parse import quote_plus

from src.scrapers.base import BaseScraper
from src.models import Job
from src.utils.logger import logger

class SeleniumScraper(BaseScraper):
    def __init__(self, seen_urls: Set[str] = None, headless: bool = True):
        super().__init__(seen_urls)
        self.headless = headless
        self.driver = None

    def _get_driver(self):
        options = Options()
        if self.headless:
            options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")
        # Udawanie zwykłej przeglądarki, aby uniknąć szybkich blokad
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        prefs = {"profile.managed_default_content_settings.images": 2}
        options.add_experimental_option("prefs", prefs)
        
        service = ChromeService(ChromeDriverManager().install())
        return webdriver.Chrome(service=service, options=options)

    def _scroll_page(self, loops=5):
        try:
            last_height = self.driver.execute_script("return document.body.scrollHeight")
            for _ in range(loops):
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(random.uniform(0.8, 1.5))
                new_height = self.driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    break
                last_height = new_height
        except Exception:
            pass

    def _parse_strict_query(self, search_str: str) -> Tuple[List[List[str]], List[str]]:
        excludes = re.findall(r'-(\w+)', search_str)
        excludes = [e.lower() for e in excludes]
        raw_groups = re.findall(r'\((.*?)\)', search_str)
        required_groups = []
        if raw_groups:
            for group in raw_groups:
                keywords = [k.strip().replace('"', '').replace("'", "").lower() for k in group.split(" OR ")]
                required_groups.append(keywords)
        else:
            clean_str = re.sub(r'-(\w+)', '', search_str)
            keywords = [w.lower() for w in clean_str.split() if w not in ["AND", "OR", "(", ")", ""]]
            if keywords:
                required_groups.append(keywords)
        return required_groups, excludes

    def _matches_strict_query(self, title: str, required_groups: list, excludes: list) -> bool:
        title_lower = title.lower()
        
        # 1. Sprawdzenie wykluczeń
        for bad_word in excludes:
            if bad_word in title_lower:
                return False
                
        # 2. Sprawdzenie grup wymaganych (każda grupa musi mieć min. jedno dopasowanie)
        for group in required_groups:
            match_found_in_group = False
            for keyword in group:
                # Używamy regex, aby szukać całych słów (np. "ai" nie dopasuje "trainee")
                # Jeśli słowo ma więcej niż 3 znaki, pozwalamy na substring (np. "python" w "python developer")
                # Jeśli słowo jest krótkie (np. "ai", "ml"), szukamy tylko jako osobne słowo
                if len(keyword) <= 3:
                    pattern = rf"\b{re.escape(keyword)}\b"
                else:
                    pattern = re.escape(keyword)
                
                if re.search(pattern, title_lower):
                    match_found_in_group = True
                    break
            
            if not match_found_in_group:
                return False
                
        return True

    def _is_junior_search(self, required_groups):
        junior_keywords = ["junior", "intern", "staż", "trainee", "młodszy", "assistant", "praktyka", "stażysta"]
        for group in required_groups:
            if any(k in junior_keywords for k in group):
                return True
        return False

    def _get_full_description(self, url: str, site: str) -> str:
        try:
            self.driver.get(url)
            time.sleep(random.uniform(1.5, 2.5))
            soup = BeautifulSoup(self.driver.page_source, "html.parser")
            
            if site == "LinkedIn":
                # LinkedIn Guest Mode - szukamy w konkretnych klasach publicznych
                desc_section = soup.select_one(".description__text, .show-more-less-html__markup, .jobs-description")
                if desc_section:
                    return desc_section.get_text(separator="\n", strip=True)
                if "authwall" in self.driver.current_url or "login" in self.driver.current_url:
                    return "Błąd: LinkedIn wyświetlił ekran logowania. Nie można pobrać opisu."
                return ""
            
            if site == "JustJoinIT":
                divs = soup.find_all("div")
                max_len = 0
                best_text = ""
                for div in divs:
                    text = div.get_text(separator="\n", strip=True)
                    if 200 < len(text) < 15000 and len(text) > max_len:
                        if "Sign in" in text: continue
                        max_len = len(text)
                        best_text = text
                return best_text
            
            elif site == "NoFluffJobs":
                desc = soup.find("section", id="posting-description") or \
                       soup.find("div", class_="common-posting-content-wrapper")
                return desc.get_text(separator="\n", strip=True) if desc else ""

            elif site == "BulldogJob":
                desc = soup.find("div", id="job-description") or soup.find("div", class_="text-sm")
                return desc.get_text(separator="\n", strip=True) if desc else ""

            elif site == "TheProtocol":
                desc = soup.find("section", {"data-test": "section-description"}) or soup.find("article")
                return desc.get_text(separator="\n", strip=True) if desc else ""

            elif site == "Pracuj.pl":
                sections = soup.find_all("div", attrs={"data-test": lambda x: x and x.startswith("section-")})
                if sections:
                    return "\n\n".join([s.get_text(separator="\n", strip=True) for s in sections])
                main_view = soup.find("div", {"id": "offer-view"}) or soup.find("div", class_="offer-view")
                return main_view.get_text(separator="\n", strip=True) if main_view else ""
            
            return ""
        except Exception as e:
            logger.warning(f"Błąd pobierania opisu ({site}): {e}")
            return ""

    def scrape(self, search_term: str, location: str, is_remote: bool, **kwargs) -> List[Job]:
        return []

class PolishSitesScraper(SeleniumScraper):
    def scrape_all(self, search_term: str, location: str, is_remote: bool) -> List[Job]:
        self.driver = self._get_driver()
        all_jobs = []
        try:
            required_groups, excludes = self._parse_strict_query(search_term)
            logger.info(f"Rozpoczynam pełne skanowanie Selenium...")
            
            # Najpierw zbieramy linki, potem pobieramy opisy (aby nie trzymać drivera zbyt długo w jednym miejscu)
            all_jobs.extend(self._scrape_linkedin(required_groups, excludes, location, is_remote))
            all_jobs.extend(self._scrape_justjoinit(required_groups, excludes, location, is_remote))
            all_jobs.extend(self._scrape_nofluffjobs(required_groups, excludes, location, is_remote))
            all_jobs.extend(self._scrape_bulldogjob(required_groups, excludes, location, is_remote))
            all_jobs.extend(self._scrape_theprotocol(required_groups, excludes, location, is_remote))
            all_jobs.extend(self._scrape_pracujpl(required_groups, excludes, location, is_remote))
            
        finally:
            if self.driver:
                self.driver.quit()
        return all_jobs

    def _scrape_linkedin(self, required_groups, excludes, location, is_remote) -> List[Job]:
        results = []
        tech_keywords = required_groups[0] if required_groups else ["Data"]
        geo_id = "90009829" if "Katowice" in location else "105072130"
        
        for kw in tech_keywords:
            base = "https://www.linkedin.com/jobs/search/?"
            params = [
                f"keywords={quote_plus(kw)}",
                f"geoId={geo_id}",
                "f_TPR=r2592000",
                "f_E=1%2C2",
                "f_F=it",
                "refresh=true"
            ]
            if is_remote: params.append("f_WT=2")
            url = base + "&".join(params)

            try:
                logger.info(f"Skanowanie LinkedIn Custom ({kw}): {url}")
                self.driver.get(url); time.sleep(3)
                self._scroll_page(loops=3) # Krótszy scroll, aby uniknąć blokad
                soup = BeautifulSoup(self.driver.page_source, "html.parser")
                count_before = len(results)
                
                job_cards = soup.find_all("div", class_="base-card") or soup.find_all("li", class_="result-card")
                for card in job_cards:
                    a_tag = card.find("a", class_="base-card__full-link") or card.find("a", class_="result-card__full-card-link")
                    if not a_tag: continue
                    link = a_tag['href'].split('?')[0]
                    if self.is_seen(link): continue
                    
                    title_tag = card.find("h3", class_="base-search-card__title") or card.find("h3", class_="result-card__title")
                    title = title_tag.get_text(strip=True) if title_tag else "Unknown"
                    
                    if self._matches_strict_query(title, required_groups, excludes):
                        company_tag = card.find("h4", class_="base-search-card__subtitle") or card.find("h4", class_="result-card__subtitle")
                        company = company_tag.get_text(strip=True) if company_tag else "Unknown"
                        
                        # Próba pobrania opisu (LinkedIn może blokować po kilku próbach)
                        logger.info(f"   ...pobieranie opisu: {title} ({company})")
                        description = self._get_full_description(link, "LinkedIn")
                        
                        # Jeśli opis jest pusty (blokada), spróbujmy wrócić do wyników wyszukiwania
                        if not description or "Błąd" in description:
                            logger.warning(f"      ! Nie udało się pobrać opisu dla {title}")
                            # Wróć na stronę wyników, aby kontynuować pętlę
                            self.driver.get(url); time.sleep(1)
                        
                        results.append(Job(
                            title=title, company=company, location=location, 
                            job_url=link, site="LinkedIn", description=description
                        ))
                        
                logger.info(f"   ---> Znaleziono: {len(results) - count_before} ofert dla '{kw}'")
            except Exception as e: 
                logger.error(f"Błąd LinkedIn Custom ({kw}): {e}")
                # Na wypadek błędu spróbujmy odświeżyć drivera
        return results

    def _get_tech_categories(self, required_groups):
        tech_keywords = required_groups[0] if required_groups else []
        cats = set()
        for kw in tech_keywords:
            kw = kw.lower()
            if "python" in kw: cats.add("python")
            if any(x in kw for x in ["data", "sql", "anal"]): cats.add("data")
            if any(x in kw for x in ["ai", "learning", "ml"]): cats.add("ai")
            if "java" in kw: cats.add("java")
            if "devops" in kw: cats.add("devops")
        return cats or {"data", "python", "ai"}

    def _scrape_justjoinit(self, required_groups, excludes, location, is_remote) -> List[Job]:
        results = []
        is_junior = self._is_junior_search(required_groups)
        categories = self._get_tech_categories(required_groups)
        for cat in categories:
            path_loc = "all-locations" if (not location or is_remote) else location.lower()
            url = f"https://justjoin.it/job-offers/{path_loc}/{cat}"
            if is_junior: url += "?experience-level=junior"
            try:
                logger.info(f"Skanowanie JustJoinIT ({cat}): {url}")
                self.driver.get(url); time.sleep(2); self._scroll_page()
                soup = BeautifulSoup(self.driver.page_source, "html.parser")
                count_before = len(results)
                for a_tag in soup.find_all("a", href=True):
                    if "/job-offer/" in a_tag['href']:
                        full_link = "https://justjoin.it" + a_tag['href']
                        if self.is_seen(full_link): continue
                        title_tag = a_tag.find("h2") or a_tag.find("span")
                        title = title_tag.get_text(strip=True) if title_tag else a_tag.get_text(strip=True)
                        title = title.split("\n")[0].split("PLN")[0].strip()
                        if self._matches_strict_query(title, required_groups, excludes):
                            results.append(Job(title=title, company="JJIT Listing", location=location,
                                             job_url=full_link, site="JustJoinIT", description=self._get_full_description(full_link, "JustJoinIT")))
                logger.info(f"   ---> Znaleziono: {len(results) - count_before} ofert")
            except Exception as e: logger.error(f"Błąd JJIT ({cat}): {e}")
        return results

    def _scrape_nofluffjobs(self, required_groups, excludes, location, is_remote) -> List[Job]:
        results = []
        is_junior = self._is_junior_search(required_groups)
        categories = self._get_tech_categories(required_groups)
        nfj_map = {"python": "python", "data": "data", "ai": "artificial-intelligence", "java": "java", "devops": "devops"}
        for cat in categories:
            nfj_cat = nfj_map.get(cat, "data")
            mid_path = "remote" if is_remote else (location.lower() if location else "")
            url = f"https://nofluffjobs.com/pl/{mid_path}/{nfj_cat}" if mid_path else f"https://nofluffjobs.com/pl/{nfj_cat}"
            if is_junior: url += "?criteria=seniority%3Dtrainee,junior"
            try:
                logger.info(f"Skanowanie NoFluffJobs ({nfj_cat}): {url}")
                self.driver.get(url); time.sleep(2); self._scroll_page()
                soup = BeautifulSoup(self.driver.page_source, "html.parser")
                count_before = len(results)
                for link_tag in soup.find_all("a", href=True):
                    if "/pl/job/" in link_tag['href'] and "job-apply" not in link_tag['href']:
                        full_link = "https://nofluffjobs.com" + link_tag['href']
                        if self.is_seen(full_link): continue
                        title_tag = link_tag.find("h3")
                        if title_tag and self._matches_strict_query(title_tag.get_text(strip=True), required_groups, excludes):
                            results.append(Job(title=title_tag.get_text(strip=True), company="NFJ Listing", location=location,
                                             job_url=full_link, site="NoFluffJobs", description=self._get_full_description(full_link, "NoFluffJobs")))
                logger.info(f"   ---> Znaleziono: {len(results) - count_before} ofert")
            except Exception as e: logger.error(f"Błąd NFJ ({nfj_cat}): {e}")
        return results

    def _scrape_bulldogjob(self, required_groups, excludes, location, is_remote) -> List[Job]:
        results = []
        is_junior = self._is_junior_search(required_groups)
        url_parts = []
        if is_remote: url_parts.append("remote,true")
        elif location: url_parts.append(f"city,{location}")
        if is_junior: url_parts.append("experienceLevel,intern,junior")
        full_url = f"https://bulldogjob.pl/companies/jobs/s/{'/'.join(url_parts)}"
        try:
            logger.info(f"Skanowanie BulldogJob: {full_url}")
            self.driver.get(full_url); time.sleep(2); self._scroll_page()
            soup = BeautifulSoup(self.driver.page_source, "html.parser")
            for a_tag in soup.find_all("a", href=True):
                if "/companies/jobs/" in a_tag['href'] and "page," not in a_tag['href']:
                    full_link = a_tag['href'] if a_tag['href'].startswith("http") else "https://bulldogjob.pl" + a_tag['href']
                    if self.is_seen(full_link): continue
                    title_tag = a_tag.find("h3")
                    if title_tag and self._matches_strict_query(title_tag.get_text(strip=True), required_groups, excludes):
                        results.append(Job(title=title_tag.get_text(strip=True), company="BulldogJob", location=location,
                                         job_url=full_link, site="BulldogJob", description=self._get_full_description(full_link, "BulldogJob")))
            logger.info(f"   ---> Znaleziono: {len(results)} ofert")
        except Exception as e: logger.error(f"Błąd BulldogJob: {e}")
        return results

    def _scrape_theprotocol(self, required_groups, excludes, location, is_remote) -> List[Job]:
        results = []
        is_junior = self._is_junior_search(required_groups)
        categories = self._get_tech_categories(required_groups)
        tp_map = {"python": "python", "data": "big-data", "ai": "ai-ml", "java": "java", "devops": "devops"}
        for cat in categories:
            tp_cat = tp_map.get(cat, "big-data")
            url_segments = [f"{tp_cat};sp"]
            if is_junior: url_segments.append("trainee,assistant,junior;p")
            if is_remote: url_segments.append("remote;wm")
            elif location: url_segments.append(f"{location.lower()};wp")
            full_url = "https://theprotocol.it/filtry/" + "/".join(url_segments)
            try:
                logger.info(f"Skanowanie TheProtocol ({tp_cat}): {full_url}")
                self.driver.get(full_url); time.sleep(2); self._scroll_page()
                soup = BeautifulSoup(self.driver.page_source, "html.parser")
                count_before = len(results)
                for a_tag in soup.find_all("a", href=True):
                    if "/szczegoly/praca/" in a_tag['href']:
                        full_link = "https://theprotocol.it" + a_tag['href']
                        if self.is_seen(full_link): continue
                        title_tag = a_tag.find("h2")
                        if title_tag and self._matches_strict_query(title_tag.get_text(strip=True), required_groups, excludes):
                            results.append(Job(title=title_tag.get_text(strip=True), company="TheProtocol", location=location,
                                             job_url=full_link, site="TheProtocol", description=self._get_full_description(full_link, "TheProtocol")))
                logger.info(f"   ---> Znaleziono: {len(results) - count_before} ofert")
            except Exception as e: logger.error(f"Błąd TheProtocol ({tp_cat}): {e}")
        return results

    def _scrape_pracujpl(self, required_groups, excludes, location, is_remote) -> List[Job]:
        results = []
        is_junior = self._is_junior_search(required_groups)
        base_url = "https://it.pracuj.pl/praca"
        path_loc = "praca%20zdalna;wm,home-office" if is_remote else (f"{location.lower()};wp" if location else "")
        params = ["rd=0"]
        if is_junior: params.append("et=1%2C3%2C17")
        url = f"{base_url}/{path_loc}"
        if params: url += "?" + "&".join(params)
        try:
            logger.info(f"Skanowanie Pracuj.pl: {url}")
            self.driver.get(url); time.sleep(2); self._scroll_page()
            soup = BeautifulSoup(self.driver.page_source, "html.parser")
            offer_items = soup.find_all("div", attrs={"data-test": "offer-item"})
            for item in offer_items:
                link_tag = item.find("a", attrs={"data-test": "link-offer"})
                title_tag = item.find("h2", attrs={"data-test": "offer-title"})
                if link_tag and title_tag:
                    full_link = link_tag['href'].split('?')[0]
                    if self.is_seen(full_link): continue
                    title = title_tag.get_text(strip=True)
                    if self._matches_strict_query(title, required_groups, excludes):
                        results.append(Job(title=title, company="Pracuj.pl Listing", location=location,
                                         job_url=full_link, site="Pracuj.pl", description=self._get_full_description(full_link, "Pracuj.pl")))
            logger.info(f"   ---> Znaleziono: {len(results)} ofert")
        except Exception as e: logger.error(f"Błąd Pracuj.pl: {e}")
        return results
