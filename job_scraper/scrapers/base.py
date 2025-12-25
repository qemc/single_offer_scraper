"""
Base scraper class - abstract interface for all job site scrapers.
"""

import re
from abc import ABC, abstractmethod
from typing import Optional

from selenium.webdriver.remote.webdriver import WebDriver

from ..models import JobOffer


class BaseScraper(ABC):
    """Abstract base class for job site scrapers."""
    
    # URL pattern to match for this scraper (regex)
    URL_PATTERN: str = ""
    
    # Source identifier
    SOURCE: str = ""
    
    def can_handle(self, url: str) -> bool:
        """Check if this scraper can handle the given URL."""
        if not self.URL_PATTERN:
            return False
        return bool(re.search(self.URL_PATTERN, url, re.IGNORECASE))
    
    @abstractmethod
    def scrape(self, driver: WebDriver, url: str) -> JobOffer:
        """
        Scrape job offer from the given URL.
        
        Args:
            driver: Selenium WebDriver instance
            url: URL of the job offer
            
        Returns:
            JobOffer instance with scraped data
        """
        pass
    
    def _create_base_offer(self, url: str) -> JobOffer:
        """Create a base JobOffer with URL and source."""
        return JobOffer(
            url=url,
            title="",
            company="",
            source=self.SOURCE,
        )
