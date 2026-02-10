import time
import os
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager


# --- KONFIGURACJA SELENIUM ---

def _get_driver():
    """Konfiguruje i zwraca sterownik Chrome w trybie headless."""
    options = Options()
    options.add_argument("--headless=new")  # Tryb bezokienkowy
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")

    # Blokowanie obrazków
    prefs = {"profile.managed_default_content_settings.images": 2}
    options.add_experimental_option("prefs", prefs)

    # Fix dla macOS (ręczne szukanie Chrome jeśli nie ma w PATH)
    possible_paths = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        os.path.expanduser("~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    ]
    for path in possible_paths:
        if os.path.exists(path):
            options.binary_location = path
            break

    return webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=options)


def _scroll_page(driver):
    """Przewija stronę listy do dołu."""
    last_height = driver.execute_script("return document.body.scrollHeight")
    # Limit scrollowania, żeby nie utknąć w nieskończoność (np. 15 razy)
    for _ in range(15):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1.0)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height


# --- POBIERANIE OPISÓW (NOWOŚĆ) ---

def _get_full_description(driver, url, site):
    """Wchodzi w link oferty i pobiera pełny opis."""
    try:
        driver.get(url)
        time.sleep(1.5)  # Czekamy na załadowanie treści oferty

        soup = BeautifulSoup(driver.page_source, "html.parser")
        description_text = ""

        if site == "JustJoinIT":
            # JJIT trzyma opis w sekcjach. Klasy są hashowane (losowe), więc szukamy po strukturze.
            # Szukamy głównego kontenera tekstowego.
            # Zazwyczaj jest to div, który jest rodzeństwem nagłówka z tytułem/zarobkami.
            # Najbezpieczniej pobrać tekst z sekcji, która ma najwięcej treści.

            # Próba znalezienia panelu z opisem (często ma specyficzne atrybuty lub jest po prostu dużym blokiem)
            # Metoda uniwersalna: pobierz tekst z divów wykluczając menu i stopkę

            # Szukamy konkretnych markerów w tekście, np. sekcji po "Tech Stack"
            # W JJIT opis jest często w divie class="css-..."

            # Pobieramy wszystkie divy i szukamy tego z największą ilością tekstu (heuristic)
            divs = soup.find_all("div")
            max_len = 0
            best_div = None

            for div in divs:
                # Ignorujemy małe elementy i te bardzo duże (cały body wrapper)
                text = div.get_text(separator="\n", strip=True)
                length = len(text)
                if 200 < length < 15000:  # Opis ma zazwyczaj od 500 do 10k znaków
                    # Dodatkowe sprawdzenie - czy to nie jest lista kafelków (częsty błąd)
                    if "Offers with salary" in text or "Sign in" in text:
                        continue
                    if length > max_len:
                        max_len = length
                        best_div = text

            description_text = best_div if best_div else "Nie udało się pobrać treści z JustJoinIT."

        elif site == "NoFluffJobs":
            # NFJ ma zazwyczaj sekcję z ID lub klasą
            # Szukamy <section id="posting-description"> lub <div class="posting-description">
            desc_section = soup.find("section", id="posting-description")
            if not desc_section:
                # Fallback, szukamy po klasie common-posting-content-wrapper
                desc_section = soup.find("div", class_="common-posting-content-wrapper")

            if desc_section:
                description_text = desc_section.get_text(separator="\n", strip=True)
            else:
                description_text = "Nie udało się pobrać treści z NoFluffJobs."

        return description_text

    except Exception as e:
        print(f"      ⚠️ Błąd pobierania opisu: {e}")
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
    for good_word in keywords:
        if good_word in title_lower: return True
    return False


# --- SCRAPERY ---

class PolishSitesScraper:
    def __init__(self, driver):
        self.driver = driver

    def scrape_justjoinit(self, keywords, excludes, location, is_remote):
        results = []
        categories = ["python", "data"]  # Możesz dodać "analytics", "artificial-intelligence"

        for cat in categories:
            url = f"https://justjoin.it/all-locations/{cat}"
            if is_remote: url += "?workplaceType=remote"

            print(f"   🚀 [JustJoinIT] Skanowanie listy: '{cat}'...")
            try:
                self.driver.get(url)
                time.sleep(2)
                _scroll_page(self.driver)

                soup = BeautifulSoup(self.driver.page_source, "html.parser")

                # 1. Zbieramy kandydatów (tylko linki i tytuły)
                candidates = []
                offer_links = [a for a in soup.find_all("a", href=True) if "/job-offer/" in a['href']]

                for a_tag in offer_links:
                    title_tag = a_tag.find("h2") or a_tag.find("h3")
                    title = title_tag.text if title_tag else a_tag.text

                    if _matches_complex_query(title, keywords, excludes):
                        full_link = "https://justjoin.it" + a_tag['href']
                        candidates.append((title, full_link))

                # Usuwamy duplikaty kandydatów (JJIT ma wirtualny scroll i może dublować)
                candidates = list(set(candidates))
                print(f"      -> Znaleziono {len(candidates)} pasujących ofert. Pobieram opisy...")

                # 2. Wchodzimy w każdą ofertę po opis
                for title, link in candidates:
                    print(f"      -> Pobieranie: {title[:30]}...")
                    description = _get_full_description(self.driver, link, "JustJoinIT")

                    results.append({
                        "site": "JustJoinIT",
                        "title": title,
                        "company": "JJIT Listing",
                        "location": "Remote" if is_remote else location,
                        "job_url": link,
                        "is_remote": is_remote,
                        "description": description
                    })

            except Exception as e:
                print(f"   ❌ Błąd JustJoinIT ({cat}): {e}")

        return results

    def scrape_nofluffjobs(self, keywords, excludes, location, is_remote):
        results = []
        loc_url = location.lower() if not is_remote else "remote"
        categories = ["python", "data", "artificial-intelligence"]

        for cat in categories:
            url = f"https://nofluffjobs.com/pl/jobs/{loc_url}/{cat}"
            print(f"   🚀 [NoFluffJobs] Skanowanie listy: '{cat}'...")
            try:
                self.driver.get(url)
                time.sleep(2)
                _scroll_page(self.driver)

                soup = BeautifulSoup(self.driver.page_source, "html.parser")
                candidates = []
                links = soup.find_all("a", href=True)

                for link in links:
                    href = link['href']
                    if "/pl/job/" in href and "job-apply" not in href:
                        title_tag = link.find("h3")
                        if not title_tag: continue
                        title = title_tag.text.strip()

                        if _matches_complex_query(title, keywords, excludes):
                            full_link = "https://nofluffjobs.com" + href
                            candidates.append((title, full_link))

                candidates = list(set(candidates))
                print(f"      -> Znaleziono {len(candidates)} pasujących ofert. Pobieram opisy...")

                for title, link in candidates:
                    print(f"      -> Pobieranie: {title[:30]}...")
                    description = _get_full_description(self.driver, link, "NoFluffJobs")

                    results.append({
                        "site": "NoFluffJobs",
                        "title": title,
                        "company": "NFJ Listing",
                        "location": location,
                        "job_url": link,
                        "is_remote": is_remote,
                        "description": description
                    })

            except Exception as e:
                print(f"   ❌ Błąd NoFluffJobs ({cat}): {e}")

        return results


# --- FUNKCJA GŁÓWNA (EXPORT) ---

def scrape_other_sites(search_term: str, location: str, is_remote: bool) -> list[dict]:
    """
    Główna funkcja wywoływana z job_scraper.py.
    """
    print(f"\n🔍 [Selenium] Rozpoczynam skanowanie polskich portali (JustJoinIT, NoFluffJobs)...")

    keywords, excludes = _extract_keywords_from_search(search_term)
    print(f"   ℹ️  Filtry lokalne: Szukam={keywords[:3]}... Wykluczam={excludes}")

    all_offers = []
    driver = None

    try:
        driver = _get_driver()
        scraper = PolishSitesScraper(driver)

        # 1. Just Join IT
        all_offers.extend(scraper.scrape_justjoinit(keywords, excludes, location, is_remote))
        # 2. No Fluff Jobs
        all_offers.extend(scraper.scrape_nofluffjobs(keywords, excludes, location, is_remote))

    except Exception as e:
        print(f"❌ Krytyczny błąd Selenium: {e}")
    finally:
        if driver:
            driver.quit()

    print(f"✅ [Selenium] Znaleziono łącznie: {len(all_offers)} ofert z pełnymi opisami.")
    return all_offers