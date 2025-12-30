"""
Core V2 scraping engine using Camoufox (AsyncCamoufox).

Features:
- Async/await interface for non-blocking scraping
- Configurable semaphore limiting concurrent browsers (see config.py)
- Headless stealth mode with humanize and geoip enabled
- No xvfb required - works natively on macOS and Raspberry Pi
- Same output schema as V1 engine for compatibility
- Uses exact same extraction scripts as V1 for reliable data extraction
"""

import asyncio
import os
import re
import traceback
from datetime import datetime
from typing import Any, Dict, List
from urllib.parse import urlparse, parse_qs

# Suppress dock icon on macOS (must be set before importing browser)
os.environ["MOZ_HEADLESS"] = "1"

from camoufox.async_api import AsyncCamoufox

from ..config import get_max_concurrent_browsers, SCRAPING_CONFIG

# =============================================================================
# GLOBAL SEMAPHORE - Limits concurrent browser instances to prevent OOM
# Initialized lazily to respect config changes
# =============================================================================
_browser_semaphore = None


def _get_semaphore() -> asyncio.Semaphore:
    """Get or create the browser semaphore with configured limit."""
    global _browser_semaphore
    if _browser_semaphore is None:
        _browser_semaphore = asyncio.Semaphore(get_max_concurrent_browsers())
    return _browser_semaphore


# Page load timeout in milliseconds (from config)
PAGE_TIMEOUT_MS = SCRAPING_CONFIG["page_timeout_ms"]

# URL patterns for supported job sites
URL_PATTERNS = {
    "justjoin": r"justjoin\.it",
    "theprotocol": r"theprotocol\.it",
    "pracuj": r"pracuj\.pl",
    "linkedin": r"linkedin\.com/jobs",
}


# =============================================================================
# SITE-SPECIFIC EXTRACTION SCRIPTS (ported from V1)
# =============================================================================

JUSTJOIN_EXTRACTION_SCRIPT = """
(function() {
    var data = {};
    
    // --- Helper: Find text by icon ---
    function getTextByIcon(iconId) {
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
    var salaryMatch = document.body.innerText.match(/(\\d[\\d\\s]*-(?:\\s*\\d[\\d\\s]*)?)\\s*(PLN|EUR|USD)/i);
    if (salaryMatch) {
         data.salary = salaryMatch[0].trim();
    }

    // --- Location ---
    // Try to extract from ld+json structured data first (most reliable)
    var location = null;
    var ldJsonScript = document.querySelector('script[type="application/ld+json"]');
    if (ldJsonScript) {
        try {
            var ldJson = JSON.parse(ldJsonScript.textContent);
            if (ldJson.jobLocation && ldJson.jobLocation.address) {
                var addr = ldJson.jobLocation.address;
                var parts = [];
                if (addr.streetAddress) parts.push(addr.streetAddress);
                if (addr.addressLocality) parts.push(addr.addressLocality);
                if (parts.length > 0) location = parts.join(', ');
            }
        } catch(e) {}
    }
    
    // Fallback: Find location as sibling to company icon container
    if (!location) {
        var companyIcon = document.querySelector('svg[data-testid="ApartmentRoundedIcon"]');
        if (companyIcon) {
            // Location is typically in a sibling MuiBox-root before the company link
            var companyContainer = companyIcon.closest('a, div[class*="MuiStack"]');
            if (companyContainer && companyContainer.parentElement) {
                var siblings = companyContainer.parentElement.children;
                for (var i = 0; i < siblings.length; i++) {
                    var sib = siblings[i];
                    // Skip the company link itself and separators
                    if (sib.tagName === 'A' || sib.tagName === 'SPAN') continue;
                    var sibText = sib.innerText.trim();
                    // Location typically contains comma or city name
                    if (sibText && sibText.length > 2 && sibText.length < 100) {
                        location = sibText;
                        break;
                    }
                }
            }
        }
    }
    
    // Last fallback: try old icon selector
    if (!location) {
        location = getTextByIcon('LocationOnOutlinedIcon') || getTextByIcon('PlaceIcon');
    }
    data.location = location;

    // --- Metadata Chips (Seniority, Mode, Type) ---
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

THEPROTOCOL_EXTRACTION_SCRIPT = """
(function() {
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
    data.company = company || "";
    
    // Salary
    data.salary = getTestText('text-salary-value');
    
    // --- 2. Details Metadata ---
    // Location
    data.location = getTestText('text-primaryLocation');
    
    // Work Mode
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
            let text = el.innerText.trim();
            descParts.push(text);
        }
    });
    
    if (descParts.length > 0) {
        data.description = descParts.join('\\n\\n');
    } else {
        data.description = ""; 
    }
    
    return data;
})();
"""

LINKEDIN_EXTRACTION_SCRIPT = """
(function() {
    const data = {};
    const bodyText = document.body.innerText;
    
    // --- 0. Remove login modal if present ---
    const modal = document.querySelector('.base-modal, .authwall-join-form__modal');
    if (modal) modal.remove();
    const overlay = document.querySelector('.modal-overlay');
    if (overlay) overlay.remove();
    document.body.style.overflow = 'auto';
    
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

    // --- 3. Location and Work Mode from top card ---
    const topFlavors = document.querySelectorAll('.topcard__flavor--bullet, .topcard__flavor, .top-card-layout__first-subline span');
    for (const flavor of topFlavors) {
        const txt = flavor.innerText?.trim() || '';
        
        // Check for work mode in parentheses: "Poznań, Poland (Hybrid)"
        const modeMatch = txt.match(/\\(?(Remote|Hybrid|On-site|Zdalna|Hybrydowa)\\)?/i);
        if (modeMatch) {
            data.workMode = modeMatch[1];
        }
        
        // Location typically contains a comma (City, Country) and is not the company name
        if (!data.location && txt.includes(',') && txt.length > 2) {
            // This is likely a location like "Poznań, Poland"
            data.location = txt.replace(/\\s*\\(?(Remote|Hybrid|On-site|Zdalna|Hybrydowa)\\)?\\s*/gi, '').trim();
        }
    }
    
    // Fallback location - look for specific location element
    if (!data.location) {
        const locEl = document.querySelector('.jobs-unified-top-card__bullet') ||
                      document.querySelector('.topcard__flavor--bullet');
        if (locEl) {
            const txt = locEl.innerText?.trim() || '';
            // Only use if it looks like a location (has comma or Poland/Polska)
            if (txt.includes(',') || txt.toLowerCase().includes('poland') || txt.toLowerCase().includes('polska')) {
                data.location = txt.replace(/\\s*\\(.*\\)\\s*$/, '');
            }
        }
    }
    
    // Last resort - try to find location in the subline
    if (!data.location) {
        const subline = document.querySelector('.top-card-layout__first-subline, .topcard__flavor-row');
        if (subline) {
            const txt = subline.innerText || '';
            // Look for patterns like "City, Country" or just city names
            const locMatch = txt.match(/([A-ZÀ-Ž][a-zà-ž]+(?:,\\s*[A-ZÀ-Ž][a-zà-ž]+)+)/);
            if (locMatch) {
                data.location = locMatch[1];
            }
        }
    }
    
    // Fallback work mode
    if (!data.workMode) {
        const workModeEl = document.querySelector('.jobs-unified-top-card__workplace-type');
        if (workModeEl) {
            data.workMode = workModeEl.innerText.trim();
        } else {
            // Search in body text
            if (bodyText.includes('Remote') || bodyText.includes('Zdalna')) data.workMode = 'Remote';
            else if (bodyText.includes('Hybrid') || bodyText.includes('Hybrydowa')) data.workMode = 'Hybrid';
        }
    }

    // --- 4. Metadata (Seniority/Employment) from job criteria ---
    const criteriaItems = document.querySelectorAll('.description__job-criteria-item');
    criteriaItems.forEach(item => {
        // Fixed: use subtitle not subheader
        const subtitle = item.querySelector('.description__job-criteria-subtitle')?.innerText?.toLowerCase() || '';
        const text = item.querySelector('.description__job-criteria-text')?.innerText?.trim();
        if (text) {
            if (subtitle.includes('seniority') || subtitle.includes('poziom')) {
                data.experienceLevel = text;
            }
            if (subtitle.includes('employment') || subtitle.includes('zatrudnienia')) {
                data.employmentType = text;
            }
            if (subtitle.includes('function') || subtitle.includes('funkcja')) {
                // Job function, could be useful
            }
        }
    });

    // Fallback for seniority/employment from job insights
    if (!data.experienceLevel || !data.employmentType) {
        const insights = document.querySelectorAll('.jobs-unified-top-card__job-insight, li');
        for (const insight of insights) {
            const text = insight.innerText?.toLowerCase() || '';
            if (!data.employmentType) {
                if (text.includes('full-time') || text.includes('pełny etat')) {
                    data.employmentType = 'Full-time';
                } else if (text.includes('part-time')) {
                    data.employmentType = 'Part-time';
                } else if (text.includes('contract')) {
                    data.employmentType = 'Contract';
                }
            }
            if (!data.experienceLevel) {
                if (text.includes('entry level') || text.includes('junior')) {
                    data.experienceLevel = 'Entry level';
                } else if (text.includes('mid-senior') || text.includes('mid')) {
                    data.experienceLevel = 'Mid-Senior level';
                } else if (text.includes('associate')) {
                    data.experienceLevel = 'Associate';
                } else if (text.includes('senior')) {
                    data.experienceLevel = 'Senior';
                }
            }
        }
    }
    
    // --- 5. Description ---
    const descContainer = document.querySelector('.jobs-description__content') ||
                         document.querySelector('.jobs-box__html-content') ||
                         document.querySelector('.description__text') ||
                         document.querySelector('.show-more-less-html__markup');
    
    if (descContainer) {
        let d = descContainer.innerText?.trim() || '';
        d = d.replace(/\\n\\s*Show less\\s*$/i, '').trim();
        data.description = d;
    } else {
         const startMarker = 'Full Job Description';
         const idx = bodyText.indexOf(startMarker);
         if (idx > -1) {
             let cut = bodyText.substring(idx + startMarker.length);
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

PRACUJ_EXTRACTION_SCRIPT = """
(function() {
    const data = {};
    
    // Helper to get text from data-test
    function getTestText(testId) {
        const el = document.querySelector(`[data-test="${testId}"]`);
        return el ? el.innerText.trim() : null;
    }
    
    // Helper to get badge title text from a sections-benefit element
    function getBadgeTitle(sectionTestId) {
        const section = document.querySelector(`[data-test="${sectionTestId}"]`);
        if (section) {
            const titleEl = section.querySelector('[data-test="offer-badge-title"]');
            return titleEl ? titleEl.innerText.trim() : null;
        }
        return null;
    }
    
    // --- Title ---
    data.title = getTestText('text-positionName') || document.querySelector('h1')?.innerText?.trim() || '';
    
    // --- Company (clean up "O firmie" / "About the company" suffix) ---
    let company = getTestText('text-employerName') || 
                  document.querySelector('[data-test="anchor-company-profile"]')?.innerText.trim();
    if (company) {
        company = company.replace(/O firmie$/i, '').replace(/About the company$/i, '').trim();
    }
    data.company = company || '';
    
    // --- Salary ---
    // The salary section uses data-test="section-salary" and each amount is in data-test="text-earningAmount"
    const salarySection = document.querySelector('[data-test="section-salary"]');
    if (salarySection) {
        // Get all earning amounts (there may be multiple for different contract types)
        const earningAmounts = salarySection.querySelectorAll('[data-test="text-earningAmount"]');
        if (earningAmounts.length > 0) {
            const salaries = [];
            earningAmounts.forEach(el => {
                const amount = el.innerText.trim();
                // Get the contract type following this amount
                const parent = el.closest('[data-test="section-salaryPerContractType"]');
                if (parent) {
                    const contractType = parent.querySelector('[data-test="text-contractTypeName"]');
                    if (contractType) {
                        salaries.push(amount + ' ' + contractType.innerText.trim());
                    } else {
                        salaries.push(amount);
                    }
                } else {
                    salaries.push(amount);
                }
            });
            data.salary = salaries.join('; ');
        }
    }
    
    // Fallback to old text-salary selector if section-salary not found
    if (!data.salary) {
        data.salary = getTestText('text-salary');
    }
    
    // --- Location (from sections-benefit-workplaces or map section) ---
    data.location = getBadgeTitle('sections-benefit-workplaces');
    if (!data.location) {
        // Try the map section with full address
        const streetEl = document.querySelector('[data-test="text-address-street"]');
        const addressEl = document.querySelector('[data-test="text-address"]');
        if (streetEl && addressEl) {
            data.location = streetEl.innerText.trim() + ', ' + addressEl.innerText.trim();
        } else if (addressEl) {
            data.location = addressEl.innerText.trim();
        } else if (streetEl) {
            data.location = streetEl.innerText.trim();
        }
    }
    // Clean up location - remove region suffix in parentheses like "(Masovian)"
    if (data.location) {
        data.location = data.location.replace(/\\s*\\([^)]*\\)\\s*$/, '').trim();
    }
    
    // --- Employment Type / Contract (from sections-benefit-contracts) ---
    data.employmentType = getBadgeTitle('sections-benefit-contracts');
    
    // --- Work Schedule / Hours (from sections-benefit-work-schedule) ---
    const workSchedule = getBadgeTitle('sections-benefit-work-schedule');
    if (workSchedule) {
        // Append to employment type if it exists
        if (data.employmentType) {
            data.employmentType += ', ' + workSchedule;
        } else {
            data.employmentType = workSchedule;
        }
    }
    
    // --- Experience Level / Seniority (from sections-benefit-employment-type-name) ---
    data.experienceLevel = getBadgeTitle('sections-benefit-employment-type-name');
    
    // --- Work Mode (from any sections-benefit-work-modes-* element) ---
    // The attribute can have suffixes like -hybrid, -many, -remote, etc.
    const workModeEl = document.querySelector('[data-test^="sections-benefit-work-modes"]');
    if (workModeEl) {
        const titleEl = workModeEl.querySelector('[data-test="offer-badge-title"]');
        if (titleEl) {
            data.workMode = titleEl.innerText.trim();
        }
    }
    
    // --- Fallback: Try old selectors if new structure didn't provide data ---
    if (!data.location) {
        data.location = getTestText('text-workplaceAddress');
    }
    if (!data.workMode) {
        const modeEl = document.querySelector('[data-test="text-workModes"]');
        if (modeEl) data.workMode = modeEl.innerText.trim();
    }
    if (!data.experienceLevel) {
        const expEl = document.querySelector('[data-test="text-experienceLevel"]');
        if (expEl) data.experienceLevel = expEl.innerText.trim();
    }
    if (!data.employmentType) {
        const typeEl = document.querySelector('[data-test="text-contractType"]');
        if (typeEl) data.employmentType = typeEl.innerText.trim();
    }
    
    // --- Description (new structure uses multiple section-* elements) ---
    const descSections = [
        'section-about-project',
        'section-responsibilities', 
        'section-requirements',
        'section-offered',
        'section-benefits',
        'section-technologies',
        'section-about-us',
        'section-description'
    ];
    
    const descParts = [];
    descSections.forEach(sectionId => {
        const sec = document.querySelector(`[data-test="${sectionId}"]`);
        if (sec && sec.innerText && sec.innerText.trim().length > 10) {
            descParts.push(sec.innerText.trim());
        }
    });
    
    // Fallback: try generic section selector
    if (descParts.length === 0) {
        const genericSections = document.querySelectorAll('[data-test*="section-"]');
        genericSections.forEach(sec => {
            const text = sec.innerText?.trim() || '';
            if (text.length > 20 && !descParts.includes(text)) {
                descParts.push(text);
            }
        });
    }
    
    if (descParts.length > 0) {
        data.description = descParts.join('\\n\\n');
    } else {
        // Last resort: get main content area
        const mainContent = document.querySelector('[data-scroll-id]') || 
                           document.querySelector('main') ||
                           document.querySelector('[role="main"]');
        data.description = mainContent?.innerText?.trim() || '';
    }
    
    return data;
})();
"""


def _detect_source(url: str) -> str:
    """Detect the job site source from URL."""
    for source, pattern in URL_PATTERNS.items():
        if re.search(pattern, url, re.IGNORECASE):
            return source
    return "unknown"


def _get_extraction_script(source: str) -> str:
    """Get the appropriate extraction script for the source."""
    scripts = {
        "justjoin": JUSTJOIN_EXTRACTION_SCRIPT,
        "theprotocol": THEPROTOCOL_EXTRACTION_SCRIPT,
        "linkedin": LINKEDIN_EXTRACTION_SCRIPT,
        "pracuj": PRACUJ_EXTRACTION_SCRIPT,
    }
    return scripts.get(source, "")


def _clean_linkedin_url(url: str) -> str:
    """Extract valid job URL from LinkedIn, processing collection links if needed."""
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


def _create_error_response(url: str, initial_url: str, error_msg: str) -> Dict[str, Any]:
    """Create standardized error response matching V1 schema."""
    return {
        "status": "error",
        "initial_url": initial_url,
        "url": url,
        "error_description": error_msg,
        "scraped_at": datetime.now().isoformat(),
    }


def _create_success_response(
    url: str,
    initial_url: str,
    source: str,
    data: Dict[str, Any],
) -> Dict[str, Any]:
    """Create standardized success response matching V1 schema."""
    return {
        "status": "success",
        "initial_url": initial_url,
        "url": url,
        "title": data.get("title") or "",
        "company": data.get("company") or "",
        "source": source,
        "location": data.get("location"),
        "salary": data.get("salary"),
        "experience_level": data.get("experienceLevel"),
        "employment_type": data.get("employmentType"),
        "work_mode": data.get("workMode"),
        "description": data.get("description") or "",
        "scraped_at": datetime.now().isoformat(),
    }


async def _handle_cookies(page, source: str) -> None:
    """Handle cookie consent popups based on site."""
    try:
        if source == "justjoin":
            btn = await page.query_selector("button:has-text('Accept'), button:has-text('Akceptuj')")
            if btn:
                await btn.click()
                await asyncio.sleep(0.5)
        elif source == "theprotocol":
            btn = await page.query_selector("#onetrust-accept-btn-handler, button[id*='accept']")
            if btn:
                await btn.click()
                await asyncio.sleep(0.5)
    except:
        pass


async def _expand_sections(page, source: str) -> None:
    """Expand 'show more' sections based on site."""
    try:
        if source == "theprotocol":
            await page.evaluate("""
            const btns = document.querySelectorAll('button[data-test="button-toggle"], button');
            btns.forEach(b => {
                if(b.innerText.toLowerCase().includes('więcej') || b.innerText.toLowerCase().includes('more')) {
                    b.click();
                }
            });
            """)
        elif source == "linkedin":
            btn = await page.query_selector("button[aria-label*='more'], .jobs-description__footer-button, button.show-more-less-html__button--more")
            if btn:
                await btn.scroll_into_view_if_needed()
                await btn.click()
                await asyncio.sleep(0.5)
    except:
        pass


async def scrape_offer(url: str) -> Dict[str, Any]:
    """
    Scrape a single job offer URL using Camoufox.
    
    Uses the same extraction logic as V1 scrapers for reliable data extraction.
    
    Args:
        url: The job offer URL to scrape.
        
    Returns:
        Dict with 'status' field matching V1 schema.
    """
    # Validate input
    if not url or not isinstance(url, str):
        return _create_error_response(
            url="",
            initial_url=str(url) if url else "",
            error_msg="Invalid URL: URL must be a non-empty string",
        )
    
    initial_url = url
    url = url.strip()
    source = _detect_source(url)
    
    if source == "unknown":
        return _create_error_response(
            url=url,
            initial_url=initial_url,
            error_msg=f"Unsupported URL: No scraper available for '{url}'. "
                      f"Supported sites: JustJoin.it, TheProtocol.it, Pracuj.pl, LinkedIn",
        )
    
    # Clean LinkedIn URLs
    if source == "linkedin":
        url = _clean_linkedin_url(url)
    
    # Get extraction script for this source
    extraction_script = _get_extraction_script(source)
    if not extraction_script:
        return _create_error_response(
            url=url,
            initial_url=initial_url,
            error_msg=f"No extraction script for source: {source}",
        )
    
    # Acquire semaphore slot - this limits concurrent browsers
    async with _get_semaphore():
        try:
            # Launch fresh browser context for unique fingerprint
            async with AsyncCamoufox(
                headless=True,
                humanize=True,
                geoip=True,
            ) as browser:
                page = await browser.new_page()
                
                try:
                    # Navigate with timeout
                    await page.goto(url, timeout=PAGE_TIMEOUT_MS, wait_until="domcontentloaded")
                    
                    # Wait for content to load
                    await asyncio.sleep(2)
                    
                    # Handle cookies
                    await _handle_cookies(page, source)
                    await asyncio.sleep(1)
                    
                    # Expand sections
                    await _expand_sections(page, source)
                    await asyncio.sleep(1)
                    
                    # Execute site-specific extraction script
                    data = await page.evaluate(extraction_script)
                    
                    if data and isinstance(data, dict):
                        return _create_success_response(
                            url=url,
                            initial_url=initial_url,
                            source=source,
                            data=data,
                        )
                    else:
                        return _create_error_response(
                            url=url,
                            initial_url=initial_url,
                            error_msg="Extraction script returned invalid data",
                        )
                    
                except asyncio.TimeoutError:
                    return _create_error_response(
                        url=url,
                        initial_url=initial_url,
                        error_msg=f"Timeout: Page took longer than {PAGE_TIMEOUT_MS // 1000}s to load",
                    )
                finally:
                    await page.close()
                    
        except Exception as e:
            error_trace = traceback.format_exc()
            return _create_error_response(
                url=url,
                initial_url=initial_url,
                error_msg=f"Scraping failed: {str(e)}\n\nTraceback:\n{error_trace}",
            )


async def scrape_batch(urls: List[str]) -> List[Dict[str, Any]]:
    """
    Scrape multiple URLs concurrently.
    
    This function uses asyncio.gather to process all URLs in parallel,
    but the global semaphore ensures only 4 browsers run at once.
    
    Args:
        urls: List of job offer URLs to scrape.
        
    Returns:
        List of result dicts, in the same order as input URLs.
    """
    tasks = [scrape_offer(url) for url in urls]
    results = await asyncio.gather(*tasks, return_exceptions=False)
    return list(results)
