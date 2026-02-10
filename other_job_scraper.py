import time
import os
import urllib.parse
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager


# --- KONFIGURACJA SELENIUM ---

def _get_driver():
    """Konfiguruje i zwraca sterownik Chrome w trybie headless."""
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")

    # Blokowanie obrazków
    prefs = {"profile.managed_default_content_settings.images": 2}
    options.add_experimental_option("prefs", prefs)

    service = ChromeService(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)


def _scroll_page(driver, loops=10):
    """Przewija stronę listy do dołu."""
    try:
        last_height = driver.execute_script("return document.body.scrollHeight")
        for _ in range(loops):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1.0)
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height
    except Exception:
        pass


# --- POBIERANIE OPISÓW ---

def _get_full_description(driver, url, site):
    """Wchodzi w link oferty i pobiera pełny opis."""
    try:
        driver.get(url)
        time.sleep(1.5)
        soup = BeautifulSoup(driver.page_source, "html.parser")
        description_text = ""

        if site == "JustJoinIT":
            # Szukanie największego bloku tekstu
            divs = soup.find_all("div")
            max_len = 0
            best_div = None
            for div in divs:
                text = div.get_text(separator="\n", strip=True)
                length = len(text)
                if 200 < length < 15000:
                    if "Offers with salary" in text or "Sign in" in text: continue
                    if length > max_len:
                        max_len = length
                        best_div = text
            description_text = best_div

        elif site == "NoFluffJobs":
            desc_section = soup.find("section", id="posting-description") or \
                           soup.find("div", class_="common-posting-content-wrapper")
            if desc_section:
                description_text = desc_section.get_text(separator="\n", strip=True)

        elif site == "BulldogJob":
            # BulldogJob trzyma opis w divie o id 'job-description' lub kontenerze tekstowym
            desc_section = soup.find("div", id="job-description")
            if not desc_section:
                # Fallback: szukamy dużej sekcji wewnątrz kontenera
                desc_section = soup.find("div", class_="text-sm")  # Częsta klasa w BDJ

            if desc_section:
                description_text = desc_section.get_text(separator="\n", strip=True)

        elif site == "TheProtocol":
            # TheProtocol ma sekcję opisową zazwyczaj w sekcji "root"
            # Szukamy sekcji z opisem (często section)
            desc_section = soup.find("section", {"data-test": "section-description"})
            if not desc_section:
                # Szukamy po prostu dużego tekstu
                article = soup.find("article")
                if article: desc_section = article

            if desc_section:
                description_text = desc_section.get_text(separator="\n", strip=True)

        return description_text if description_text else f"Brak opisu dla {site}."

    except Exception as e:
        print(f"      ⚠️ Błąd pobierania opisu ({site}): {e}")
        return ""


# --- FILTROWANIE ---

def _extract_keywords_from_search(search_str: str):
    clean_str = search_str.replace("(", "").replace(")", "").replace('"', "")
    words = clean_str.split()
    excludes = [w[1:].lower() for w in words if w.startswith("-")]
    keywords = [w.lower() for w in words if not w.startswith("-") and w not in ["OR", "AND", ""]]
    return keywords, excludes


def _matches_complex_query(title: str, keywords: list, excludes: list) -> bool:
    title_lower = title.lower()
    for bad_word in excludes:
        if bad_word in title_lower: return False

    # Jeśli brak słów kluczowych (puste), bierzemy wszystko co nie wykluczone
    if not keywords: return True

    for good_word in keywords:
        if good_word in title_lower: return True
    return False


# --- SCRAPERY PORTALI ---

class PolishSitesScraper:
    def __init__(self, driver):
        self.driver = driver

    def scrape_justjoinit(self, keywords, excludes, location, is_remote):
        results = []
        categories = ["python", "data", "artificial-intelligence"]

        for cat in categories:
            url = f"https://justjoin.it/all-locations/{cat}"
            if is_remote: url += "?workplaceType=remote"

            print(f"   🚀 [JustJoinIT] Skanowanie: '{cat}'...")
            try:
                self.driver.get(url)
                time.sleep(2)
                _scroll_page(self.driver)
                soup = BeautifulSoup(self.driver.page_source, "html.parser")

                candidates = []
                for a_tag in soup.find_all("a", href=True):
                    if "/job-offer/" in a_tag['href']:
                        title_tag = a_tag.find("h2") or a_tag.find("h3")
                        title = title_tag.text if title_tag else a_tag.text
                        if _matches_complex_query(title, keywords, excludes):
                            candidates.append((title, "https://justjoin.it" + a_tag['href']))

                candidates = list(set(candidates))
                print(f"      -> Znaleziono {len(candidates)} ofert.")

                for title, link in candidates:
                    results.append({
                        "site": "JustJoinIT",
                        "title": title,
                        "company": "JJIT Listing",
                        "location": "Remote" if is_remote else location,
                        "job_url": link,
                        "description": _get_full_description(self.driver, link, "JustJoinIT")
                    })
            except Exception as e:
                print(f"   ❌ Błąd JJIT: {e}")
        return results

    def scrape_nofluffjobs(self, keywords, excludes, location, is_remote):
        results = []
        loc_url = location.lower() if not is_remote else "remote"
        categories = ["python", "data", "artificial-intelligence"]

        for cat in categories:
            url = f"https://nofluffjobs.com/pl/jobs/{loc_url}/{cat}"
            print(f"   🚀 [NoFluffJobs] Skanowanie: '{cat}'...")
            try:
                self.driver.get(url)
                time.sleep(2)
                _scroll_page(self.driver)
                soup = BeautifulSoup(self.driver.page_source, "html.parser")

                candidates = []
                for link in soup.find_all("a", href=True):
                    if "/pl/job/" in link['href'] and "job-apply" not in link['href']:
                        title_tag = link.find("h3")
                        if title_tag:
                            title = title_tag.text.strip()
                            if _matches_complex_query(title, keywords, excludes):
                                candidates.append((title, "https://nofluffjobs.com" + link['href']))

                candidates = list(set(candidates))
                print(f"      -> Znaleziono {len(candidates)} ofert.")

                for title, link in candidates:
                    results.append({
                        "site": "NoFluffJobs",
                        "title": title,
                        "company": "NFJ Listing",
                        "location": location,
                        "job_url": link,
                        "description": _get_full_description(self.driver, link, "NoFluffJobs")
                    })
            except Exception as e:
                print(f"   ❌ Błąd NFJ: {e}")
        return results

    def scrape_bulldogjob(self, keywords, excludes, location, is_remote):
        # BulldogJob ma strukturę: https://bulldogjob.pl/companies/jobs/s/skills,Python,Java
        results = []

        # Przygotowanie słów kluczowych do URL (Bulldog wymaga przecinków)
        valid_keywords = [k for k in keywords if len(k) > 1]  # Pomiń "R" lub "C" jeśli są za krótkie
        if not valid_keywords:
            valid_keywords = ["Python", "Data"]  # Domyślne jeśli brak

        skills_path = ",".join(valid_keywords)

        # Filtry lokalizacji
        loc_param = ""
        if is_remote:
            loc_param = "/remote,true"
        elif location:
            loc_param = f"/city,{location}"

        url = f"https://bulldogjob.pl/companies/jobs/s/skills,{skills_path}{loc_param}"

        print(f"   🚀 [BulldogJob] Skanowanie: {valid_keywords}...")

        try:
            self.driver.get(url)
            time.sleep(2)
            _scroll_page(self.driver, loops=5)  # Bulldog szybko ładuje wszystko
            soup = BeautifulSoup(self.driver.page_source, "html.parser")

            candidates = []
            # Analiza struktury z pliku bulldogjob.py użytkownika deenuu1:
            # class_="JobListItem_item__M79JI"

            # Uwaga: Klasy CSS w React (np. __M79JI) mogą się zmieniać.
            # Lepiej szukać po href zawierającym "/companies/jobs/"
            for a_tag in soup.find_all("a", href=True):
                if "/companies/jobs/" in a_tag['href'] and not "page," in a_tag['href']:
                    # Szukanie tytułu
                    title_tag = a_tag.find("h3")
                    if title_tag:
                        title = title_tag.text.strip()
                        # Dodatkowa weryfikacja (Bulldog czasem wrzuca promowane niezwiązane)
                        if _matches_complex_query(title, keywords, excludes):
                            candidates.append((title, a_tag['href']))

            # Bulldog ma linki relatywne lub absolutne, upewnijmy się
            clean_candidates = []
            for t, l in candidates:
                # Czasami link jest tylko fragmentem
                full_link = l if l.startswith("http") else "https://bulldogjob.pl" + l
                clean_candidates.append((t, full_link))

            clean_candidates = list(set(clean_candidates))
            print(f"      -> Znaleziono {len(clean_candidates)} ofert.")

            for title, link in clean_candidates:
                results.append({
                    "site": "BulldogJob",
                    "title": title,
                    "company": "BulldogJob Listing",
                    "location": "Remote" if is_remote else location,
                    "job_url": link,
                    "description": _get_full_description(self.driver, link, "BulldogJob")
                })

        except Exception as e:
            print(f"   ❌ Błąd BulldogJob: {e}")

        return results

    def scrape_theprotocol(self, keywords, excludes, location, is_remote):
        # TheProtocol: https://theprotocol.it/filtry/python;t/warszawa;wp
        results = []

        search_query = keywords[0] if keywords else "python"
        url = f"https://theprotocol.it/filtry/{search_query};t"

        if is_remote:
            url += "/remote;wm"
        elif location:
            url += f"/{location};wp"

        print(f"   🚀 [TheProtocol] Skanowanie: '{search_query}'...")

        try:
            self.driver.get(url)
            time.sleep(2)
            _scroll_page(self.driver)
            soup = BeautifulSoup(self.driver.page_source, "html.parser")

            candidates = []
            # Szukamy linków ofert
            for a_tag in soup.find_all("a", href=True):
                if "/szczegoly/praca/" in a_tag['href']:
                    title_tag = a_tag.find("h2")
                    if title_tag:
                        title = title_tag.text.strip()
                        if _matches_complex_query(title, keywords, excludes):
                            full_link = "https://theprotocol.it" + a_tag['href']
                            candidates.append((title, full_link))

            candidates = list(set(candidates))
            print(f"      -> Znaleziono {len(candidates)} ofert.")

            for title, link in candidates:
                results.append({
                    "site": "TheProtocol",
                    "title": title,
                    "company": "TheProtocol Listing",
                    "location": location,
                    "job_url": link,
                    "description": _get_full_description(self.driver, link, "TheProtocol")
                })

        except Exception as e:
            print(f"   ❌ Błąd TheProtocol: {e}")

        return results


# --- FUNKCJA GŁÓWNA ---

def scrape_other_sites(search_term: str, location: str, is_remote: bool) -> list[dict]:
    """
    Główna funkcja wywoływana z job_scraper.py.
    """
    print(f"\n🔍 [Selenium] Rozpoczynam skanowanie polskich portali...")

    keywords, excludes = _extract_keywords_from_search(search_term)
    print(f"   ℹ️  Filtry: Szukam={keywords}... Wykluczam={excludes}")

    all_offers = []
    driver = None

    try:
        driver = _get_driver()
        scraper = PolishSitesScraper(driver)

        # 1. Just Join IT
        all_offers.extend(scraper.scrape_justjoinit(keywords, excludes, location, is_remote))
        # 2. No Fluff Jobs
        all_offers.extend(scraper.scrape_nofluffjobs(keywords, excludes, location, is_remote))
        # 3. BulldogJob
        all_offers.extend(scraper.scrape_bulldogjob(keywords, excludes, location, is_remote))
        # 4. TheProtocol (Grupa Pracuj)
        all_offers.extend(scraper.scrape_theprotocol(keywords, excludes, location, is_remote))

    except Exception as e:
        print(f"❌ Krytyczny błąd Selenium: {e}")
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass

    print(f"✅ [Selenium] Znaleziono łącznie: {len(all_offers)} ofert z pełnymi opisami.")
    return all_offers