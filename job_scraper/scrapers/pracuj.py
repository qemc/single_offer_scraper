"""
Pracuj.pl job offer scraper.
Extracts only job-specific content, excluding navigation and similar offers.
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


class PracujScraper(BaseScraper):
    """Scraper for Pracuj.pl job offers."""
    
    URL_PATTERN = r"pracuj\.pl/praca/"
    SOURCE = "pracuj"
    
    # JavaScript to extract only job-specific content
    EXTRACTION_SCRIPT = """
    return (function() {
        const data = {};
        
        // Title
        const titleEl = document.querySelector('[data-test="text-positionName"]') ||
                       document.querySelector('h1');
        data.title = titleEl?.innerText?.trim() || '';
        
        // Company
        const companyEl = document.querySelector('[data-test="text-employerName"]');
        let company = companyEl?.innerText?.trim() || '';
        company = company.replace(/(?:O firmie|About the company)$/i, '').trim();
        data.company = company;
        
        // Salary
        const salaryEl = document.querySelector('[data-test="section-salary"]');
        if (salaryEl) {
            const text = salaryEl.innerText;
            const match = text.match(/([\\d\\s,–-]+\\s*(?:zł|PLN)[^\\n]*)/i);
            data.salary = match ? match[1].trim() : '';
        }
        
        // Location - Specific Data Attribute Only (and strict labelled fallback)
        // User provided: sections-benefit-workplaces, text-address
        const locEl = document.querySelector('[data-test="text-workplaceAddress"]') ||
                      document.querySelector('[data-test="sections-benefit-workplaces"]') ||
                      document.querySelector('[data-test="text-address"]');
                      
        if (locEl) {
            // Clean up optional badge description usually found inside (e.g. "(mazowieckie)") if needed, 
            // butinnerText usually reads it fine. 
            // The user snippet shows text is: "Stawki 40, Wola, Warszawa(mazowieckie)"
            data.location = locEl.innerText.trim();
        } else {
            // Strict labeled fallback
            const allText = document.body.innerText;
            const locMatch = allText.match(/(?:Siedziba firmy|Miejsce pracy|Location|Workplace):\\s*([^\\n]+)/i);
            if (locMatch) {
                const cand = locMatch[1].trim();
                // Filter out common UI noise if accidentally captured
                if (cand.length < 100 && !cand.includes('Zobacz')) data.location = cand;
            }
        }
        
        // Work mode
        // User provided: sections-benefit-work-modes-hybrid (so we match prefix)
        const wmEl = document.querySelector('[data-test*="sections-benefit-work-modes"]');
        if (wmEl) {
            data.workMode = wmEl.innerText.trim();
        } else {
             const allText = document.body.innerText;
             const wmMatch = allText.match(/(?:Tryb pracy|Work mode|Workplace type):\\s*([^\\n]+)/i);
             if (wmMatch) data.workMode = wmMatch[1].trim();
        }
        
        // Employment type & Seniority
        const empTypeEl = document.querySelector('[data-test="sections-benefit-contracts"]');
        data.employmentType = empTypeEl?.innerText?.trim() || '';

        const seniorityEl = document.querySelector('[data-test="sections-benefit-employment-type-name"]');
        data.experienceLevel = seniorityEl?.innerText?.trim() || '';
        
        // Extract job description using DOM attributes (Robust)
        const descriptionParts = [];
        
        // Define stable sections by data-test attribute
        const domSections = [
            { 
                selector: '[data-test="section-about-project"]', 
                fallbackTitle: 'About the project' 
            },
            { 
                selector: '[data-test="section-responsibilities"]', 
                titleSelector: '[data-test="section-responsibilities-title"]', 
                fallbackTitle: 'Responsibilities' 
            },
            { 
                selector: '[data-test="section-requirements"]', 
                titleSelector: '[data-test="section-requirements-title"]',
                fallbackTitle: 'Requirements' 
            },
             { 
                selector: '[data-test="section-technologies"]', 
                titleSelector: '[data-test="section-technologies-title"]',
                fallbackTitle: 'Technologies' 
            },
             { 
                selector: '[data-test="section-training"]', 
                fallbackTitle: 'Training' 
            },
             { 
                selector: '[data-test="section-work-organization"]', 
                fallbackTitle: 'Work Organization' 
            },
             { 
                selector: '[data-test="section-offered"]', 
                titleSelector: '[data-test="section-offered-title"]',
                fallbackTitle: 'What we offer' 
            },
             { 
                selector: '[data-test="section-benefits"]', 
                titleSelector: '[data-test="section-benefits-title"]',
                fallbackTitle: 'Benefits' 
            }
        ];
        
        for (const secDef of domSections) {
            const sectionEl = document.querySelector(secDef.selector);
            if (sectionEl) {
                // Try to find a title inside or use fallback
                let title = secDef.fallbackTitle;
                // Note: Pracuj usually puts the title in a child with specific class or data-test
                // But grabbing the whole innerText usually works well as it preserves visual hierarchy.
                // However, let's look for specific title to clean it up?
                // Actually, sectionEl.innerText usually includes the Title + Content nicely formatted with newlines.
                
                // Let's check if we want to clean it.
                // Sometimes it includes "Hidden" text or UI artifacts.
                
                let text = sectionEl.innerText.trim();
                
                // Clean up "Read less" / "Read more" buttons
                text = text.replace(/Czytaj mniej/g, '').replace(/Czytaj więcej/g, '');
                text = text.replace(/Read less/g, '').replace(/Read more/g, '');
                
                if (text.length > 5) {
                    descriptionParts.push(text);
                }
            }
        }

        // Fallback: If ZERO sections found (maybe layout changed unpredictably?),
        // revert to markers? No, user said DOM structure is more stable.
        // If data-test attributes are missing, the page is likely broken or completely redesigned.
        // We will respect "do not guess" and return empty description rather than scraping random text.
        
        data.description = descriptionParts.join('\\n\\n');
        
        return data;
    })();
    """
    
    def scrape(self, driver: WebDriver, url: str) -> JobOffer:
        """Scrape job offer from Pracuj.pl."""
        driver.get(url)
        wait_for_page_load(driver)
        random_delay(2, 4)
        
        # Handle cookie consent
        self._handle_cookies(driver)
        random_delay(1, 2)
        
        # Scroll to load content
        try:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 2)")
            random_delay(1, 1.5)
        except Exception as e:
            print(f"Warning: Scroll failed: {e}")
        
        offer = self._create_base_offer(url)
        
        # Execute JavaScript extraction
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
                "[data-test='button-submitCookie'], #onetrust-accept-btn-handler",
                timeout=5
            )
            if cookie_btn:
                click_element_safely(driver, cookie_btn)
                random_delay(0.5, 1)
                print("Cookie consent handled")
        except Exception as e:
            print(f"Cookie handling info: {e}")
