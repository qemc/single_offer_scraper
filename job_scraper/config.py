"""
Scraper Configuration.
"""

# Async Scraping Configuration
SCRAPING_CONFIG = {
    # Maximum concurrent browser instances for batch processing
    # Lower this on memory-constrained devices (e.g., Raspberry Pi)
    "max_concurrent_browsers": 3,
    
    # Page load timeout in milliseconds
    "page_timeout_ms": 30000,
}


def get_max_concurrent_browsers() -> int:
    """Get the maximum number of concurrent browsers for batch processing."""
    return SCRAPING_CONFIG["max_concurrent_browsers"]


def set_max_concurrent_browsers(limit: int) -> None:
    """Set the maximum number of concurrent browsers for batch processing."""
    if limit < 1:
        raise ValueError("Concurrency limit must be at least 1")
    SCRAPING_CONFIG["max_concurrent_browsers"] = limit
