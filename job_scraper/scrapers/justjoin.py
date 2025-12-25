"""
JustJoin.it job offer scraper.
Extracts job data from JustJoin.it using strict DOM selectors and stable markers.
"""

from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.by import By

from .base import BaseScraper
from ..models import JobOffer
from ..utils import (
    safe_find_element,
    safe_get_text,
    random_delay,
    wait_for_page_load,
    click_element_safely,
)


class JustJoinScraper(BaseScraper):
    """Scraper for JustJoin.it job offers."""
    
    URL_PATTERN = r"justjoin\.it/job-offer/"
    SOURCE = "justjoin"
    
    # JavaScript for strict DOM-based extraction
    EXTRACTION_SCRIPT = """
    return (function() {
        var data = {};
        
        // --- Helper: Find text by icon ---
        function getTextByIcon(iconId) {
            // Use single quotes and concatenation to avoid backtick issues in Python string
            var icon = document.querySelector('svg[data-testid="' + iconId + '"]');
            if (icon) {
                var parent = icon.parentElement;
                if (parent) return parent.innerText.trim();
            }
            return null;
        }

        // --- Title ---
        var h1 = document.querySelector('h1');
        data.title = h1 ? h1.innerText.trim() : '';
        
        // --- Company ---
        var company = getTextByIcon('ApartmentRoundedIcon');
        if (!company) {
            var compLink = document.querySelector('a[href*="companies="]');
            if (compLink) company = compLink.innerText.trim();
        }
        data.company = company || '';

        // --- Salary ---
        // Regex: digit followed by space/digit/dash, ending with currency.
        // We use new RegExp to be safer with escaping in Python string
        // Pattern: (\\d[\\d\\s]*-(?:\\s*\\d[\\d\\s]*)?)\\s*(PLN|EUR|USD)
        // In Python string, backslash needs to be double escaped so JS sees double backslash for regex d?
        // Actually: \\d -> \d in JS string. new RegExp('\\d') matches digit.
        var salaryMatch = document.body.innerText.match(/(\\d[\\d\\s]*-(?:\\s*\\d[\\d\\s]*)?)\\s*(PLN|EUR|USD)/i);
        if (salaryMatch) {
             data.salary = salaryMatch[0].trim();
        }

        // --- Location ---
        var location = getTextByIcon('LocationOnOutlinedIcon');
        data.location = location; // Can be null, fallback in Python

        // --- Metadata Chips (Seniority, Mode, Type) ---
        // Scan all small text elements
        var allDivs = document.querySelectorAll('div, span');
        var headerChips = [];
        var modeChips = [];
        var typeChips = [];
        
        for (var i = 0; i < allDivs.length; i++) {
            var el = allDivs[i];
            var txt = el.innerText;
            if (txt.length > 20) continue;
            
            if (['Junior', 'Mid', 'Senior', 'C-level'].indexOf(txt) !== -1) headerChips.push(txt);
            if (['Remote', 'Hybrid', 'Office'].indexOf(txt) !== -1) modeChips.push(txt);
            if (['B2B', 'Permanent', 'Mandate contract'].indexOf(txt) !== -1) typeChips.push(txt);
        }

        if (headerChips.length > 0) data.experienceLevel = headerChips[0];
        if (modeChips.length > 0) data.workMode = modeChips[0];
        if (typeChips.length > 0) data.employmentType = typeChips[0];
        
        // --- Description & Tech Stack ---
        function getSectionContent(headerText) {
            var headers = document.querySelectorAll('h1, h2, h3, h4, h5, h6, div');
            for (var i = 0; i < headers.length; i++) {
                var h = headers[i];
                if (h.innerText.trim().toUpperCase() === headerText) {
                    var next = h.nextElementSibling;
                    if (next) return next.innerText.trim();
                }
            }
            return null;
        }

        var desc = getSectionContent('JOB DESCRIPTION') || '';
        
        // Tech Stack
        var techHeaderStub = null;
        var headers = document.querySelectorAll('h1, h2, h3, h4, h5, h6, div');
        for (var i = 0; i < headers.length; i++) {
             if (headers[i].innerText.trim().toUpperCase() === 'TECH STACK') {
                 techHeaderStub = headers[i];
                 break;
             }
        }
            
        var techText = "";
        if (techHeaderStub) {
            var container = techHeaderStub.nextElementSibling;
            if (container) {
                var rawStack = container.innerText.trim();
                // Split by newline and filter
                var parts = rawStack.split('\\n');
                var filtered = [];
                for (var j=0; j<parts.length; j++) {
                    var p = parts[j];
                    if (p.length > 1 && ['Junior', 'Mid', 'Senior'].indexOf(p) === -1) {
                        filtered.push(p);
                    }
                }
                if (filtered.length > 0) {
                    techText = "Tech Stack: " + filtered.join(', ');
                }
            }
        }

        if (desc && techText) {
            desc = desc + "\\n\\n" + techText;
        } else if (techText) {
            desc = techText;
        }

        data.description = desc;
        
        return data;
    })();
    """
    
    def scrape(self, driver: WebDriver, url: str) -> JobOffer:
        """Scrape job offer from JustJoin.it."""
        driver.get(url)
        wait_for_page_load(driver)
        random_delay(2, 3)
        
        # Cookie consent
        self._handle_cookies(driver)
        
        offer = self._create_base_offer(url)
        
        try:
            data = driver.execute_script(self.EXTRACTION_SCRIPT)
            
            if data:
                offer.title = data.get('title') or "Unknown Title"
                offer.company = data.get('company') or "Unknown Company"
                offer.salary = data.get('salary')
                offer.location = data.get('location')
                offer.work_mode = data.get('workMode')
                offer.experience_level = data.get('experienceLevel')
                offer.employment_type = data.get('employmentType')
                offer.description = data.get('description') or ""
                
                # Fallback implementation for Location if DOM failed (JustJoin URL is very reliable)
                if not offer.location:
                    # justjoin.it/job-offer/company-title-city-category
                    # Extract city from URL parts
                    try:
                        # e.g. p-p-solutions-...-warszawa-data
                        # last part is category (data), previous is city?
                        # It's usually: company-title-CITY-category
                        slug = url.split('/')[-1]
                        parts = slug.split('-')
                        if len(parts) > 2:
                            # Heuristic: City is usually the second to last part if category is last
                            # strict check against known cities list is better, but simple fallback:
                            # Just capitalize the one before 'data'/'devops' etc?
                            # Actually, just taking the part before the last dash is often good enough for a fallback.
                            # But strictness...
                            # Let's try to match known big Polish cities strictly.
                            candidate = parts[-2]
                            known_cities = ['warszawa', 'krakow', 'wroclaw', 'poznan', 'trojmiasto', 'gdansk', 'gdynia', 'sopot', 'katowice', 'lodz', 'lublin', 'szczecin', 'bialystok', 'rzeszow']
                            if candidate.lower() in known_cities:
                                offer.location = candidate.capitalize()
                            else:
                                # Check 3rd to last (sometimes city is 2 words?)
                                # Strict approach: If not in known list, leave null.
                                pass
                    except:
                        pass
        except Exception as e:
            print(f"Warning: JustJoin extraction error: {e}")
            title_elem = safe_find_element(driver, By.TAG_NAME, "h1")
            offer.title = safe_get_text(title_elem, "Unknown Title")
            
        return offer

    def _handle_cookies(self, driver: WebDriver) -> None:
        """Handle JustJoin cookie banner."""
        try:
            # "Akceptuj wszystkie" or similar
            btn = safe_find_element(driver, By.XPATH, "//button[contains(text(), 'Accept') or contains(text(), 'Akceptuj')]")
            if btn:
                click_element_safely(driver, btn)
        except:
            pass
