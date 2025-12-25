"""
TheProtocol.it job offer scraper.
Extracts only job-specific content using strict data-test selectors.
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


class TheProtocolScraper(BaseScraper):
    """Scraper for TheProtocol.it job offers."""
    
    URL_PATTERN = r"theprotocol\.it/szczegoly/praca/"
    SOURCE = "theprotocol"
    
    # JavaScript to extract content using data-test attributes
    EXTRACTION_SCRIPT = """
    return (function() {
        const data = {};
        
        // Helper to get text from data-test
        function getTestText(testId) {
            const el = document.querySelector(`[data-test="${testId}"]`);
            return el ? el.innerText.trim() : null;
        }
        
        // --- 1. Basic Metadata ---
        data.title = getTestText('text-offerTitle') || document.querySelector('h1')?.innerText?.trim() || '';
        
        // Company (remove "Firma: " prefix if present)
        let company = getTestText('text-offerEmployer') || 
                      document.querySelector('a[data-test="anchor-company-link"]')?.innerText.trim();
        if (company) {
            company = company.replace(/^(Firma|Company):\\s*/i, '');
        }
        data.company = company || "Unknown Company";
        
        // Salary
        data.salary = getTestText('text-salary-value');
        
        // --- 2. Details Metadata ---
        // Location
        data.location = getTestText('text-primaryLocation');
        
        // Work Mode
        // "content-workModes" usually contains chips
        const modeEl = document.querySelector('[data-test="content-workModes"]');
        if (modeEl) {
            data.workMode = modeEl.innerText.replace(/\\n/g, ', ').trim();
        }
        
        // Experience / Seniority
        const expEl = document.querySelector('[data-test="content-positionLevels"]');
        if (expEl) {
            data.experienceLevel = expEl.innerText.replace(/\\n/g, ', ').trim();
        }
        
        // Employment Type
        const typeEl = document.querySelector('[data-test="text-contractName"]');
        if (typeEl) {
           data.employmentType = typeEl.innerText.trim();
        }
        
        // --- 3. Structured Description ---
        // We will build the description from specific sections to ensure everything is captured
        const sections = [
            { id: 'section-technologies', label: 'TECHNOLOGIES' },
            { id: 'section-about-project', label: 'ABOUT THE PROJECT' },
            { id: 'section-responsibilities', label: 'RESPONSIBILITIES' },
            { id: 'section-requirements', label: 'REQUIREMENTS' },
            { id: 'section-offered', label: 'WHAT WE OFFER' },
            { id: 'section-benefits', label: 'BENEFITS' },
            { id: 'section-training-space', label: 'TRAINING & DEVELOPMENT' },
            { id: 'section-about-us-description', label: 'ABOUT COMPANY' }
        ];
        
        const descParts = [];
        
        sections.forEach(sec => {
            const el = document.querySelector(`[data-test="${sec.id}"]`);
            if (el && el.innerText.trim().length > 0) {
                // Formatting: Add label unless it's already in the text (often header is there)
                // But safer to just dump the text as TheProtocol usually formats it well
                let text = el.innerText.trim();
                
                // If it's technologies, make it single line if possible? No, keep it structured.
                descParts.push(text);
            }
        });
        
        if (descParts.length > 0) {
            data.description = descParts.join('\\n\\n');
        } else {
            // Fallback: entire body text minus known nav/footer junk?
            // Strict approach: return empty if strict sections failed. 
            // But let's check one big container if sections fail.
            const mainContent = document.querySelector('#offerHeader') // Usually there isn't one main container...
            // Fallback to text scanning if data-test failed (unlikely)
            data.description = ""; 
        }
        
        return data;
    })();
    """
    
    def scrape(self, driver: WebDriver, url: str) -> JobOffer:
        """Scrape job offer from TheProtocol.it."""
        driver.get(url)
        wait_for_page_load(driver)
        random_delay(2, 4)
        
        # Handle cookie consent
        self._handle_cookies(driver)
        random_delay(1, 2)
        
        # Expand "Show more" buttons
        self._expand_sections(driver)
        random_delay(1, 1.5)
        
        offer = self._create_base_offer(url)
        
        try:
            data = driver.execute_script(self.EXTRACTION_SCRIPT)
            
            if data and isinstance(data, dict):
                offer.title = data.get('title', '') or "Unknown Title"
                offer.company = data.get('company', '') or "Unknown Company"
                offer.salary = data.get('salary', '') or None
                offer.location = data.get('location', '') or None
                offer.work_mode = data.get('workMode', '') or None
                offer.experience_level = data.get('experienceLevel', '') or None
                offer.employment_type = data.get('employmentType', '') or None
                offer.description = data.get('description', '') or ""
            else:
                raise ValueError("JavaScript returned invalid data")
                
        except Exception as e:
            print(f"Warning: JavaScript extraction failed: {e}")
            title_elem = safe_find_element(driver, By.TAG_NAME, "h1")
            offer.title = safe_get_text(title_elem, "Unknown Title")
        
        return offer
    
    def _handle_cookies(self, driver: WebDriver) -> None:
        """Handle cookie consent popup."""
        try:
            cookie_btn = safe_find_element(
                driver, By.CSS_SELECTOR,
                "button[id*='accept'], #onetrust-accept-btn-handler",
                timeout=5
            )
            if cookie_btn:
                click_element_safely(driver, cookie_btn)
                random_delay(0.5, 1)
        except Exception:
            pass
            
    def _expand_sections(self, driver: WebDriver) -> None:
        """Click 'read more' buttons to expand text."""
        try:
            # TheProtocol often has 'więcej' or 'more' buttons
            # data-test="button-toggle" is strict if available
            script = """
            const btns = document.querySelectorAll('button[data-test="button-toggle"], button');
            btns.forEach(b => {
                if(b.innerText.toLowerCase().includes('więcej') || b.innerText.toLowerCase().includes('more')) {
                    b.click();
                }
            });
            """
            driver.execute_script(script)
        except Exception:
            pass
