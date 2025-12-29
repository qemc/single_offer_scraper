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
import re
import traceback
from datetime import datetime
from typing import Any, Dict, List
from urllib.parse import urlparse, parse_qs

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
    var location = getTextByIcon('LocationOnOutlinedIcon');
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
         const subline = document.querySelector('.top-card-layout__first-subline');
         if (subline) {
             const txt = subline.innerText;
             if (txt.includes('Remote')) data.workMode = 'Remote';
             else if (txt.includes('Hybrid')) data.workMode = 'Hybrid';
             else if (txt.includes('On-site')) data.workMode = 'On-site';
         }
    }

    // --- 5. Metadata (Seniority/Employment) ---
    const criteriaItems = document.querySelectorAll('.description__job-criteria-item');
    criteriaItems.forEach(item => {
        const header = item.querySelector('.description__job-criteria-subheader')?.innerText.toLowerCase() || '';
        const val = item.querySelector('.description__job-criteria-text')?.innerText.trim();
        if (val) {
            if (header.includes('seniority')) data.experienceLevel = val;
            if (header.includes('employment')) data.employmentType = val;
        }
    });

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
    const descContainer = document.querySelector('.jobs-description__content') ||
                         document.querySelector('.jobs-box__html-content') ||
                         document.querySelector('.description__text') ||
                         document.querySelector('.show-more-less-html__markup');
    
    if (descContainer) {
        let d = descContainer.innerText?.trim() || '';
        d = d.replace(/\\n\\s*Show less\\s*$/i, '').trim();
        data.description = d;
    } else {
         const startMarker = 'Full Job Description'
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
    
    // --- Title ---
    data.title = getTestText('text-positionName') || document.querySelector('h1')?.innerText?.trim() || '';
    
    // --- Company ---
    let company = getTestText('text-employerName') || 
                  document.querySelector('[data-test="anchor-company-profile"]')?.innerText.trim();
    data.company = company || '';
    
    // --- Salary ---
    data.salary = getTestText('text-salary');
    
    // --- Location ---
    data.location = getTestText('text-workplaceAddress');
    
    // --- Work Mode ---
    const modeEl = document.querySelector('[data-test="text-workModes"]');
    if (modeEl) {
        data.workMode = modeEl.innerText.trim();
    }
    
    // --- Experience Level ---
    const expEl = document.querySelector('[data-test="text-experienceLevel"]');
    if (expEl) {
        data.experienceLevel = expEl.innerText.trim();
    }
    
    // --- Employment Type ---
    const typeEl = document.querySelector('[data-test="text-contractType"]');
    if (typeEl) {
        data.employmentType = typeEl.innerText.trim();
    }
    
    // --- Description ---
    const descSections = document.querySelectorAll('[data-test*="section-"], [data-scroll-id]');
    const descParts = [];
    descSections.forEach(sec => {
        if (sec.innerText && sec.innerText.trim().length > 20) {
            descParts.push(sec.innerText.trim());
        }
    });
    
    if (descParts.length > 0) {
        data.description = descParts.join('\\n\\n');
    } else {
        // Fallback to main content area
        const mainContent = document.querySelector('[data-test="section-description"]');
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
