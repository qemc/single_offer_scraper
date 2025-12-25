"""
LinkedIn job offer scraper.
Requires logged-in Chrome profile for access.
Extracts only job-specific content.
"""

from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from urllib.parse import urlparse, parse_qs

from .base import BaseScraper
from ..models import JobOffer
from ..utils import (
    safe_find_element,
    safe_get_text,
    random_delay,
    wait_for_page_load,
    click_element_safely,
    scroll_to_element,
)


class LinkedInScraper(BaseScraper):
    """Scraper for LinkedIn job offers. Requires logged-in session."""
    
    URL_PATTERN = r"linkedin\.com/jobs/"
    SOURCE = "linkedin"
    
    # JavaScript to extract only job-specific content
    EXTRACTION_SCRIPT = """
    return (function() {
        const data = {};
        const bodyText = document.body.innerText;
        
        // --- 1. Title ---
        const titleEl = document.querySelector('.jobs-unified-top-card__job-title') ||
                       document.querySelector('h1.top-card-layout__title') ||
                       document.querySelector('h1.t-24') ||
                       document.querySelector('h1');
        data.title = titleEl?.innerText?.trim() || '';
        
        // --- 2. Company ---
        const companyEl = document.querySelector('.jobs-unified-top-card__company-name a') ||
                         document.querySelector('.jobs-unified-top-card__company-name') ||
                         document.querySelector('a.topcard__org-name-link') ||
                         document.querySelector('.top-card-layout__first-subline a') ||
                         document.querySelector('.job-details-jobs-unified-top-card__company-name');
        
        if (companyEl) {
            data.company = companyEl.innerText.trim();
        } else {
             try {
                const jsonLd = document.querySelector('script[type="application/ld+json"]');
                if (jsonLd) {
                    const schema = JSON.parse(jsonLd.innerText);
                    if (schema['@type'] === 'JobPosting' && schema.hiringOrganization?.name) {
                        data.company = schema.hiringOrganization.name;
                    }
                }
            } catch(e) {}
        }

        // --- 3. Location ---
        const locEl = document.querySelector('.jobs-unified-top-card__bullet') ||
                      document.querySelector('.topcard__flavor--bullet') ||
                      document.querySelector('.top-card-layout__first-subline span:nth-child(2)');
                      
        if (locEl) {
            const txt = locEl.innerText.trim();
            if (!['Remote', 'Hybrid', 'On-site'].includes(txt) && !txt.match(/\\d/)) {
                 data.location = txt;
            }
        }
        
        // --- 4. Work Mode ---
        const workModeEl = document.querySelector('.jobs-unified-top-card__workplace-type');
        if (workModeEl) {
             data.workMode = workModeEl.innerText.trim();
        } else {
             // Check keywords in top card subline using text matching
             const subline = document.querySelector('.top-card-layout__first-subline');
             if (subline) {
                 const txt = subline.innerText;
                 if (txt.includes('Remote')) data.workMode = 'Remote';
                 else if (txt.includes('Hybrid')) data.workMode = 'Hybrid';
                 else if (txt.includes('On-site')) data.workMode = 'On-site';
             }
        }

        // --- 5. Metadata (Seniority/Employment) ---
        // Public View Criteria List
        const criteriaItems = document.querySelectorAll('.description__job-criteria-item');
        criteriaItems.forEach(item => {
            const header = item.querySelector('.description__job-criteria-subheader')?.innerText.toLowerCase() || '';
            const val = item.querySelector('.description__job-criteria-text')?.innerText.trim();
            if (val) {
                if (header.includes('seniority')) data.experienceLevel = val;
                if (header.includes('employment')) data.employmentType = val;
            }
        });

        // Logged In View Insights
        if (!data.employmentType) {
            const insights = document.querySelectorAll('.jobs-unified-top-card__job-insight');
            for (const insight of insights) {
                const text = insight.innerText?.toLowerCase() || '';
                if (text.includes('full-time') || text.includes('part-time') || text.includes('contract')) {
                    data.employmentType = insight.innerText?.trim();
                }
                if (text.includes('entry level') || text.includes('mid-senior') || text.includes('associate')) {
                    data.experienceLevel = insight.innerText?.trim();
                }
            }
        }
        
        // --- 6. Description ---
        // Prioritize structured containers
        const descContainer = document.querySelector('.jobs-description__content') ||
                             document.querySelector('.jobs-box__html-content') ||
                             document.querySelector('.description__text') ||
                             document.querySelector('.show-more-less-html__content');
        
        if (descContainer) {
            let d = descContainer.innerText?.trim() || '';
            // Clean up UI artifacts like 'Show less' button text
            d = d.replace(/\\n\\s*Show less\\s*$/i, '').trim();
            data.description = d;
        } else {
             // Fallback: Strict marker search in body text
             const startMarker = 'Full Job Description'
             const idx = bodyText.indexOf(startMarker);
             if (idx > -1) {
                 // Try to cut off after description
                 let cut = bodyText.substring(idx + startMarker.length);
                 // Common footer markers
                 const endMarkers = ['Show less', 'Seniority level', 'Employment type', 'Job function', 'Industries'];
                 for(let m of endMarkers) {
                     if (cut.indexOf(m) > -1) {
                         cut = cut.split(m)[0];
                         break;
                     }
                 }
                 data.description = cut.trim();
             }
        }
        
        return data;
    })();
    """
    
    def scrape(self, driver: WebDriver, url: str) -> JobOffer:
        """Scrape job offer from LinkedIn."""
        clean_url = self._clean_url(url)
        driver.get(clean_url)
        wait_for_page_load(driver)
        random_delay(2, 4)
        
        offer = self._create_base_offer(clean_url)
        
        try:
            # Wait for either Public or Logged In title
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "h1, .jobs-unified-top-card, .top-card-layout"))
            )
        except Exception:
            pass
        
        random_delay(1, 2)
        self._expand_description(driver)
        random_delay(1, 2)
        
        try:
            data = driver.execute_script(self.EXTRACTION_SCRIPT)
            if data and isinstance(data, dict):
                offer.title = data.get('title', '') or "Unknown Title"
                offer.company = data.get('company', '') or "Unknown Company"
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
    
    def _clean_url(self, url: str) -> str:
        """Extract valid job URL, processing collection links if needed."""
        # Check for currentJobId in query params (collections, search, etc.)
        try:
            parsed = urlparse(url)
            params = parse_qs(parsed.query)
            if 'currentJobId' in params:
                job_id = params['currentJobId'][0]
                return f"https://www.linkedin.com/jobs/view/{job_id}"
        except:
            pass
            
        if "/jobs/view/" in url:
            parts = url.split("/jobs/view/")
            if len(parts) > 1:
                job_id = parts[1].split("?")[0].split("/")[0]
                return f"https://www.linkedin.com/jobs/view/{job_id}"
        return url
    
    def _expand_description(self, driver: WebDriver) -> None:
        try:
            # Try both Logged In and Public view 'Show more' buttons
            button_selector = "button[aria-label*='more'], .jobs-description__footer-button, button.show-more-less-html__button--more"
            see_more_btn = safe_find_element(driver, By.CSS_SELECTOR, button_selector, timeout=3)
            
            if see_more_btn:
                scroll_to_element(driver, see_more_btn)
                click_element_safely(driver, see_more_btn)
                random_delay(0.5, 1)
        except Exception:
            pass
