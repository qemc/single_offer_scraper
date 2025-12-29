"""
Core scraping engine.
Exposes a clean API for scraping job offers.
"""

from typing import Dict, Any
import traceback

# Import scrapers (relative imports)
from .scrapers.justjoin import JustJoinScraper
from .scrapers.theprotocol import TheProtocolScraper
from .scrapers.pracuj import PracujScraper
from .scrapers.linkedin import LinkedInScraper

# Import browser management
from .browser import BrowserManager

# Initialize scrapers once
SCRAPERS = [
    JustJoinScraper(),
    TheProtocolScraper(),
    PracujScraper(),
    LinkedInScraper(),
]


def get_scraper_for_url(url: str):
    """Find the appropriate scraper for the given URL."""
    for scraper in SCRAPERS:
        if scraper.can_handle(url):
            return scraper
    return None


def scrape_offer(url: str) -> Dict[str, Any]:
    """
    Scrape a single job offer from the URL.
    
    Args:
        url: The job offer URL.
        
    Returns:
        Dict with 'status' field:
        - On success: {"status": "success", "url": ..., "title": ..., ...}
        - On error: {"status": "error", "error_description": "..."}
    """
    # Validate URL
    if not url or not isinstance(url, str):
        return {
            "status": "error",
            "error_description": "Invalid URL: URL must be a non-empty string"
        }
    
    # Save original URL before any processing
    initial_url = url
    url = url.strip()
    
    scraper = get_scraper_for_url(url)
    if not scraper:
        return {
            "status": "error",
            "initial_url": initial_url,
            "error_description": f"Unsupported URL: No scraper available for '{url}'. Supported sites: JustJoin.it, TheProtocol.it, Pracuj.pl, LinkedIn"
        }

    # Determine if we need a specific profile (e.g. for LinkedIn)
    use_profile = scraper.SOURCE == "linkedin"
    
    try:
        with BrowserManager(use_profile=use_profile) as browser:
            driver = browser.get_driver()
            
            if driver is None:
                return {
                    "status": "error",
                    "initial_url": initial_url,
                    "error_description": "Browser initialization failed: Could not create Chrome driver"
                }
            
            # Execute scraping
            offer = scraper.scrape(driver, url)
            
            if offer is None:
                return {
                    "status": "error",
                    "initial_url": initial_url,
                    "error_description": "Scraping returned no data: The page may have changed or is not accessible"
                }
            
            # Build success response
            result = offer.to_dict()
            result["status"] = "success"
            result["initial_url"] = initial_url
            return result
            
    except TimeoutError as e:
        return {
            "status": "error",
            "initial_url": initial_url,
            "error_description": f"Timeout: Page took too long to load. {str(e)}"
        }
    except ConnectionError as e:
        return {
            "status": "error",
            "initial_url": initial_url,
            "error_description": f"Connection error: Could not reach the website. {str(e)}"
        }
    except Exception as e:
        # Capture full traceback for debugging
        error_trace = traceback.format_exc()
        return {
            "status": "error",
            "initial_url": initial_url,
            "error_description": f"Scraping failed: {str(e)}\n\nTraceback:\n{error_trace}"
        }
