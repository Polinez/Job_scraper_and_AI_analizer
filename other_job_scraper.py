import time
import re
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from urllib.parse import quote_plus


# --- KONFIGURACJA SELENIUM ---

def _get_driver():
    """Konfiguruje i zwraca sterownik Chrome w trybie headless."""
    options = Options()
    options.add_argument("--headless=new")  # Włącz dla wydajności (zakomentuj dla podglądu)
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


# --- LOGIKA FILTROWANIA (STRICT MODE) ---

def _parse_strict_query(search_str: str):
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


def _matches_strict_query(title: str, required_groups: list, excludes: list) -> bool:
    title_lower = title.lower()

    for bad_word in excludes:
        if bad_word in title_lower: return False

    for group in required_groups:
        match_found_in_group = False
        for keyword in group:
            if keyword in title_lower:
                match_found_in_group = True
                break
        if not match_found_in_group: return False

    return True


# --- POMOCNIK: CZY SZUKAMY JUNIORA? ---
def _is_junior_search(required_groups):
    junior_keywords = ["junior", "intern", "staż", "trainee", "młodszy", "assistant", "praktyka"]
    for group in required_groups:
        if any(k in junior_keywords for k in group):
            return True
    return False


# --- POBIERANIE OPISÓW ---

def _get_full_description(driver, url, site):
    try:
        if site == "LinkedIn":
            return "Opis dostępny bezpośrednio na LinkedIn (Guest Mode)."

        driver.get(url)
        time.sleep(1.0)
        soup = BeautifulSoup(driver.page_source, "html.parser")
        description_text = ""

        if site == "JustJoinIT":
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
            desc_section = soup.find("div", id="job-description") or soup.find("div", class_="text-sm")
            if desc_section:
                description_text = desc_section.get_text(separator="\n", strip=True)

        elif site == "TheProtocol":
            desc_section = soup.find("section", {"data-test": "section-description"}) or soup.find("article")
            if desc_section:
                description_text = desc_section.get_text(separator="\n", strip=True)

        elif site == "Pracuj.pl":
            sections = soup.find_all("div", attrs={"data-test": lambda x: x and x.startswith("section-")})
            full_text = []
            for sec in sections:
                full_text.append(sec.get_text(separator="\n", strip=True))

            if full_text:
                description_text = "\n\n".join(full_text)
            else:
                main_div = soup.find("div", {"id": "offer-view"}) or soup.find("div", class_="offer-view")
                if main_div:
                    description_text = main_div.get_text(separator="\n", strip=True)

        return description_text if description_text else f"Brak opisu dla {site}."

    except Exception as e:
        print(f"      ⚠️ Błąd pobierania opisu ({site}): {e}")
        return ""


# --- SCRAPERY ---

class PolishSitesScraper:
    def __init__(self, driver, seen_urls=None):
        self.driver = driver
        self.seen_urls = seen_urls if seen_urls else set()
        # STATYSTYKI SESJI
        self.stats = {
            "processed": 0,  # Łącznie znalezione linki na stronach
            "filtered_history": 0,  # Odrzucone bo już są w historii
            "added": 0  # Nowe, które przeszły Strict Query
        }

    def _is_seen(self, url):
        self.stats["processed"] += 1
        if url in self.seen_urls:
            self.stats["filtered_history"] += 1
            return True
        return False

    # --- 0. LinkedIn Helper Methods ---
    def _build_linkedin_url(self, keywords, location, is_remote):
        # geoId: 90009829 to "Katowice Metropolitan Area"
        # f_PP: 103855053 to doprecyzowanie lokalizacji (z Twojego linku)
        geo_id = "90009829" if "Katowice" in location else "105072130"

        # Filtry LinkedIn:
        # f_TPR=r2592000 -> Ostatni miesiąc (30 dni)
        # f_E=1,2 -> Internship (1), Entry level (2)
        # f_F=it -> Funkcja: Technologie informatyczne (STRICT IT)
        base = "https://www.linkedin.com/jobs/search/?"
        params = [
            f"keywords={quote_plus(keywords)}",
            f"geoId={geo_id}",
            "f_TPR=r2592000",
            "f_E=1%2C2",
            "f_F=it",
            "origin=JOB_SEARCH_PAGE_JOB_FILTER",
            "refresh=true"
        ]

        # Dodanie parametru precyzującego lokalizację dla Katowic
        if "Katowice" in location:
            params.append("f_PP=103855053")

        if is_remote:
            params.append("f_WT=2")

        return base + "&".join(params)

    # 1. LinkedIn Custom Scraper
    def scrape_linkedin(self, keywords, location, is_remote, required_groups, excludes):
        results = []
        url = self._build_linkedin_url(keywords, location, is_remote)

        print(f"   🚀 [LinkedIn] Skanowanie: {url}")

        try:
            self.driver.get(url)
            time.sleep(3)  # Czekamy na załadowanie

            # Próba zamknięcia pop-upa logowania
            try:
                close_btn = self.driver.find_element("css selector",
                                                     "button[data-tracking-control-name='public_jobs_contextual-sign-in-modal_modal_dismiss']")
                close_btn.click()
                time.sleep(1)
            except:
                pass

            _scroll_page(self.driver, loops=8)

            soup = BeautifulSoup(self.driver.page_source, "html.parser")

            # Wyszukiwanie kart w Guest Mode
            job_cards = soup.find_all("div", class_="base-card")
            if not job_cards:
                job_cards = soup.find_all("li", class_="result-card")

            print(f"      -> Znaleziono kart na liście (Raw): {len(job_cards)}")

            for card in job_cards:
                try:
                    a_tag = card.find("a", class_="base-card__full-link") or card.find("a",
                                                                                       class_="result-card__full-card-link")
                    if not a_tag: continue

                    link = a_tag['href'].split('?')[0]

                    # Sprawdzanie historii z licznikiem
                    if self._is_seen(link): continue

                    title_tag = card.find("h3", class_="base-search-card__title") or card.find("h3",
                                                                                               class_="result-card__title")
                    company_tag = card.find("h4", class_="base-search-card__subtitle") or card.find("h4",
                                                                                                    class_="result-card__subtitle")
                    loc_tag = card.find("span", class_="job-search-card__location") or card.find("span",
                                                                                                 class_="result-card__location")

                    title = title_tag.text.strip() if title_tag else "Nieznane"
                    company = company_tag.text.strip() if company_tag else "Nieznana"
                    loc = loc_tag.text.strip() if loc_tag else location

                    if _matches_strict_query(title, required_groups, excludes):
                        results.append({
                            "site": "LinkedIn",
                            "title": title,
                            "company": company,
                            "location": loc,
                            "job_url": link,
                            "description": "Guest Mode - opis niedostępny bez logowania"
                        })
                        self.stats["added"] += 1
                        self.seen_urls.add(link)

                except Exception:
                    continue

        except Exception as e:
            print(f"   ❌ Błąd LinkedIn: {e}")

        return results

    # 2. Just Join IT
    def scrape_justjoinit(self, required_groups, excludes, location, is_remote):
        results = []
        tech_keywords = required_groups[0] if required_groups else ["python", "data"]
        is_junior = _is_junior_search(required_groups)

        categories_to_check = set()
        for kw in tech_keywords:
            kw = kw.lower()
            if "python" in kw: categories_to_check.add("python")
            if any(x in kw for x in ["data", "sql", "analytics"]): categories_to_check.add("data")
            if "java" in kw: categories_to_check.add("java")
            if "net" in kw: categories_to_check.add("net")
            if any(x in kw for x in ["ai", "learning", "ml", "nlp", "llm"]): categories_to_check.add("ai")

        if not categories_to_check: categories_to_check = {"data", "python", "ai"}

        for cat in categories_to_check:
            base_url = "https://justjoin.it/job-offers"
            path_loc = "all-locations" if (not location or is_remote) else location.lower()
            url = f"{base_url}/{path_loc}/{cat}"

            params = []
            if is_remote: params.append("workplaceType=remote")
            if is_junior: params.append("experience-level=junior")
            if not is_remote and location: params.append("radius=0")
            params.append("orderBy=DESC")
            params.append("sortBy=published")

            if params: url += "?" + "&".join(params)

            print(f"   🚀 [JustJoinIT] Skanowanie: {url}")
            try:
                self.driver.get(url)
                time.sleep(2)
                _scroll_page(self.driver)
                soup = BeautifulSoup(self.driver.page_source, "html.parser")
                candidates = []
                for a_tag in soup.find_all("a", href=True):
                    if "/job-offer/" in a_tag['href']:
                        full_link = "https://justjoin.it" + a_tag['href']

                        # Sprawdzanie historii
                        if self._is_seen(full_link): continue

                        title = a_tag.text
                        if _matches_strict_query(title, required_groups, excludes):
                            candidates.append((title, full_link))

                candidates = list(set(candidates))
                print(f"      -> Znaleziono: {len(candidates)}")

                for title, link in candidates:
                    results.append({
                        "site": "JustJoinIT",
                        "title": title,
                        "company": "JJIT Listing",
                        "location": "Remote" if is_remote else location,
                        "job_url": link,
                        "description": _get_full_description(self.driver, link, "JustJoinIT")
                    })
                    self.stats["added"] += 1
            except Exception as e:
                print(f"   ❌ Błąd JJIT ({cat}): {e}")
        return results

    # 3. No Fluff Jobs
    def scrape_nofluffjobs(self, required_groups, excludes, location, is_remote):
        results = []
        is_junior = _is_junior_search(required_groups)

        tech_keywords = required_groups[0] if required_groups else ["python"]
        categories_to_check = set()

        for kw in tech_keywords:
            kw = kw.lower()
            if "python" in kw: categories_to_check.add("python")
            if "data" in kw: categories_to_check.add("data")
            if any(x in kw for x in ["ai", "learning", "ml"]): categories_to_check.add("artificial-intelligence")
            if "back" in kw: categories_to_check.add("backend")

        if not categories_to_check: categories_to_check = {"data", "artificial-intelligence"}

        for cat in categories_to_check:
            base_url = "https://nofluffjobs.com/pl"
            mid_path = "remote" if is_remote else (location.lower() if location else "")

            url = f"{base_url}/{mid_path}/{cat}" if mid_path else f"{base_url}/{cat}"
            if is_junior: url += "?criteria=seniority%3Dtrainee,junior"

            print(f"   🚀 [NoFluffJobs] Skanowanie: {url}")
            try:
                self.driver.get(url)
                time.sleep(2)
                _scroll_page(self.driver)
                soup = BeautifulSoup(self.driver.page_source, "html.parser")

                candidates = []
                for link_tag in soup.find_all("a", href=True):
                    if "/pl/job/" in link_tag['href'] and "job-apply" not in link_tag['href']:
                        full_link = "https://nofluffjobs.com" + link_tag['href']

                        # Sprawdzanie historii
                        if self._is_seen(full_link): continue

                        title_tag = link_tag.find("h3")
                        if title_tag:
                            title = title_tag.text.strip()
                            if _matches_strict_query(title, required_groups, excludes):
                                candidates.append((title, full_link))

                candidates = list(set(candidates))
                print(f"      -> Znaleziono: {len(candidates)}")

                for title, link in candidates:
                    results.append({
                        "site": "NoFluffJobs",
                        "title": title,
                        "company": "NFJ Listing",
                        "location": location,
                        "job_url": link,
                        "description": _get_full_description(self.driver, link, "NoFluffJobs")
                    })
                    self.stats["added"] += 1
            except Exception as e:
                print(f"   ❌ Błąd NFJ: {e}")
        return results

    # 4. BulldogJob
    def scrape_bulldogjob(self, required_groups, excludes, location, is_remote):
        results = []
        is_junior = _is_junior_search(required_groups)

        tech_group = required_groups[0] if required_groups else []
        roles = []
        for t in tech_group:
            t = t.lower()
            if "data" in t or "sql" in t:
                roles.append("data")
            elif "ai" in t or "learning" in t:
                roles.append("ai")
            elif "python" in t or "java" in t:
                roles.append("backend")

        roles = list(set(roles))
        if not roles: roles = ["data", "backend", "ai"]

        base_url = "https://bulldogjob.pl/companies/jobs/s"
        url_parts = []

        if is_remote:
            url_parts.append("remote,true")
        elif location:
            url_parts.append(f"city,{location}")

        if roles: url_parts.append(f"role,{','.join(roles)}")
        if is_junior: url_parts.append("experienceLevel,intern,junior")

        full_url = f"{base_url}/{'/'.join(url_parts)}"

        print(f"   🚀 [BulldogJob] Skanowanie: {full_url}")
        try:
            self.driver.get(full_url)
            time.sleep(2)
            _scroll_page(self.driver, loops=5)
            soup = BeautifulSoup(self.driver.page_source, "html.parser")

            candidates = []
            for a_tag in soup.find_all("a", href=True):
                if "/companies/jobs/" in a_tag['href'] and "page," not in a_tag['href']:
                    raw_link = a_tag['href']
                    full_link = raw_link if raw_link.startswith("http") else "https://bulldogjob.pl" + raw_link

                    # Sprawdzanie historii
                    if self._is_seen(full_link): continue

                    title_tag = a_tag.find("h3")
                    if title_tag:
                        title = title_tag.text.strip()
                        if _matches_strict_query(title, required_groups, excludes):
                            candidates.append((title, full_link))

            candidates = list(set(candidates))
            print(f"      -> Znaleziono: {len(candidates)}")

            for title, link in candidates:
                results.append({
                    "site": "BulldogJob",
                    "title": title,
                    "company": "BulldogJob",
                    "location": "Remote" if is_remote else location,
                    "job_url": link,
                    "description": _get_full_description(self.driver, link, "BulldogJob")
                })
                self.stats["added"] += 1
        except Exception as e:
            print(f"   ❌ Błąd BulldogJob: {e}")
        return results

    # 5. TheProtocol
    def scrape_theprotocol(self, required_groups, excludes, location, is_remote):
        results = []
        is_junior = _is_junior_search(required_groups)

        tech_keywords = required_groups[0] if required_groups else ["python"]
        categories_slugs = set()
        for t in tech_keywords:
            t = t.lower()
            if "python" in t:
                categories_slugs.add("python")
            elif "data" in t:
                categories_slugs.add("big-data")
            elif "ai" in t or "learning" in t:
                categories_slugs.add("ai-ml")
            elif "java" in t:
                categories_slugs.add("java")
            elif "backend" in t:
                categories_slugs.add("backend")

        if not categories_slugs: categories_slugs = {"python", "ai-ml"}

        for tech_slug in categories_slugs:
            url_segments = [f"{tech_slug};sp"]
            if is_junior: url_segments.append("trainee,assistant,junior;p")

            if is_remote:
                url_segments.append("remote;wm")
            elif location:
                url_segments.append(f"{location.lower()};wp")

            full_url = "https://theprotocol.it/filtry/" + "/".join(url_segments)

            print(f"   🚀 [TheProtocol] Skanowanie: {full_url}")
            try:
                self.driver.get(full_url)
                time.sleep(2)
                _scroll_page(self.driver)
                soup = BeautifulSoup(self.driver.page_source, "html.parser")

                candidates = []
                for a_tag in soup.find_all("a", href=True):
                    if "/szczegoly/praca/" in a_tag['href']:
                        full_link = "https://theprotocol.it" + a_tag['href']

                        # Sprawdzanie historii
                        if self._is_seen(full_link): continue

                        title_tag = a_tag.find("h2")
                        if title_tag:
                            title = title_tag.text.strip()
                            if _matches_strict_query(title, required_groups, excludes):
                                candidates.append((title, full_link))

                candidates = list(set(candidates))
                print(f"      -> Znaleziono: {len(candidates)}")

                for title, link in candidates:
                    results.append({
                        "site": "TheProtocol",
                        "title": title,
                        "company": "TheProtocol",
                        "location": location,
                        "job_url": link,
                        "description": _get_full_description(self.driver, link, "TheProtocol")
                    })
                    self.stats["added"] += 1
            except Exception as e:
                print(f"   ❌ Błąd TheProtocol: {e}")
        return results

    # 6. Pracuj.pl
    def scrape_pracujpl(self, required_groups, excludes, location, is_remote):
        results = []
        is_junior = _is_junior_search(required_groups)

        tech_keywords = required_groups[0] if required_groups else []
        its_codes = set()
        for t in tech_keywords:
            t = t.lower()
            if "ai" in t or "learning" in t: its_codes.add("ai-ml")
            if "python" in t or "java" in t: its_codes.add("backend")
            if "data" in t or "anal" in t:
                its_codes.add("data-analytics-and-bi")
                its_codes.add("big-data-science")

        if not its_codes:
            its_codes = {"ai-ml", "backend", "data-analytics-and-bi", "big-data-science"}

        its_param = "%2C".join(its_codes)
        base_url = "https://it.pracuj.pl/praca"
        path_loc = "praca%20zdalna;wm,home-office" if is_remote else (f"{location.lower()};wp" if location else "")

        params = ["rd=0"]
        if is_junior: params.append("et=1%2C3%2C17")
        if its_param: params.append(f"its={its_param}")
        if not is_remote: params.append("wm=full-office%2Chybrid")

        full_url = f"{base_url}/{path_loc}"
        if params: full_url += "?" + "&".join(params)

        print(f"   🚀 [Pracuj.pl] Skanowanie: {full_url}")

        try:
            self.driver.get(full_url)
            time.sleep(2)
            _scroll_page(self.driver, loops=5)
            soup = BeautifulSoup(self.driver.page_source, "html.parser")

            candidates = []
            offer_items = soup.find_all("div", attrs={"data-test": "offer-item"})
            if not offer_items: offer_items = soup.find_all("div", class_="offer-view")

            for item in offer_items:
                link_tag = item.find("a", attrs={"data-test": "link-offer"})
                title_tag = item.find("h2", attrs={"data-test": "offer-title"})

                if link_tag and title_tag:
                    raw_link = link_tag['href']
                    full_link = raw_link if raw_link.startswith("http") else "https://it.pracuj.pl" + raw_link

                    # Sprawdzanie historii
                    if self._is_seen(full_link): continue

                    title = title_tag.text.strip()
                    if _matches_strict_query(title, required_groups, excludes):
                        candidates.append((title, full_link))

            candidates = list(set(candidates))
            print(f"      -> Znaleziono: {len(candidates)}")

            for title, link in candidates:
                results.append({
                    "site": "Pracuj.pl",
                    "title": title,
                    "company": "Pracuj.pl Listing",
                    "location": "Remote" if is_remote else location,
                    "job_url": link,
                    "description": _get_full_description(self.driver, link, "Pracuj.pl")
                })
                self.stats["added"] += 1
        except Exception as e:
            print(f"   ❌ Błąd Pracuj.pl: {e}")

        return results


# --- MAIN ---

def scrape_other_sites(search_term: str, location: str, is_remote: bool, seen_urls: set = None) -> list[dict]:
    print(f"\n🔍 [Selenium] Rozpoczynam PRECYZYJNE skanowanie polskich portali + LinkedIn...")

    required_groups, excludes = _parse_strict_query(search_term)

    is_jun = _is_junior_search(required_groups)
    mode_info = "JUNIOR/INTERN" if is_jun else "WSZYSTKIE POZIOMY"

    print(f"   ℹ️  TRYB: {mode_info} | GRUPY: {[g[:3] for g in required_groups]} | WYKLUCZENIA: {excludes}")

    # --- Przygotowanie frazy dla LinkedIn ---
    # Bierzemy pierwszą grupę słów kluczowych lub ogólne "Data"
    li_keywords = " ".join(required_groups[0]) if required_groups else "Data"
    if len(li_keywords) > 50: li_keywords = required_groups[0][0]  # skracanie jeśli za długie

    all_offers = []
    driver = None

    try:
        driver = _get_driver()
        scraper = PolishSitesScraper(driver, seen_urls)

        # 1. LinkedIn Custom Scraper (tylko jeśli szukamy w Katowicach/Polsce lub zdalnie)
        if "Katowice" in location or not location or is_remote:
            all_offers.extend(scraper.scrape_linkedin(li_keywords, location, is_remote, required_groups, excludes))

        # 2. Reszta polskich stron
        all_offers.extend(scraper.scrape_justjoinit(required_groups, excludes, location, is_remote))
        all_offers.extend(scraper.scrape_nofluffjobs(required_groups, excludes, location, is_remote))
        all_offers.extend(scraper.scrape_bulldogjob(required_groups, excludes, location, is_remote))
        all_offers.extend(scraper.scrape_theprotocol(required_groups, excludes, location, is_remote))
        all_offers.extend(scraper.scrape_pracujpl(required_groups, excludes, location, is_remote))

        # --- RAPORT KOŃCOWY SELENIUM ---
        print("\n📊 --- STATYSTYKI SELENIUM ---")
        print(f"   👁️  Przejrzano linków na stronach: {scraper.stats['processed']}")
        print(f"   🗑️  Odrzucono (już w historii): {scraper.stats['filtered_history']}")
        print(f"   ✅  Nowe i dopasowane: {scraper.stats['added']}")
        print("-------------------------------")

    except Exception as e:
        print(f"❌ Krytyczny błąd Selenium: {e}")
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass

    return all_offers