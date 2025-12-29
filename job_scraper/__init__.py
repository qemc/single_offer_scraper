"""
Job Offer Scraper Package.

Async scraper using Camoufox for anti-bot protection.
Supports: JustJoin.it, TheProtocol.it, Pracuj.pl, LinkedIn

Installation:
    pip install git+https://github.com/qemc/single_offer_scraper.git
Usage:
    import asyncio
    from job_scraper import scrape_offer, scrape_batch
    
    # Single URL
    result = asyncio.run(scrape_offer("https://..."))
    
    # Batch (parallel, max 3 concurrent by default)
    results = asyncio.run(scrape_batch([url1, url2, ...]))
    
    # Configure concurrency
    from job_scraper import set_max_concurrent_browsers
    set_max_concurrent_browsers(2)  # Lower for Raspberry Pi
"""

# Main scraping functions
from .camoufox_engine import scrape_offer, scrape_batch

# Config helpers
from .config import (
    get_max_concurrent_browsers,
    set_max_concurrent_browsers,
)

__all__ = [
    "scrape_offer",
    "scrape_batch",
    "get_max_concurrent_browsers",
    "set_max_concurrent_browsers",
]
