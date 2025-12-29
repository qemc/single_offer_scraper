"""
Camoufox Engine V2 - Async web scraper with anti-bot protection.

This module provides a standalone async scraping function that handles
browser lifecycle, stealth mechanics, and resource limits automatically.

Usage:
    from job_scraper.camoufox_engine import scrape_offer, scrape_batch
    
    result = await scrape_offer("https://example.com/job")
    results = await scrape_batch([url1, url2, ...])
"""

from .core import scrape_offer, scrape_batch

__all__ = ["scrape_offer", "scrape_batch"]
