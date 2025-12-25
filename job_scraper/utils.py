"""
Utility functions for the job scraper.
"""

import random
import time
import re
from typing import Optional

from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from .config import SCRAPING_CONFIG


def random_delay(min_seconds: float = None, max_seconds: float = None) -> None:
    """Sleep for a random duration to mimic human behavior."""
    min_s = min_seconds or SCRAPING_CONFIG["min_delay"]
    max_s = max_seconds or SCRAPING_CONFIG["max_delay"]
    time.sleep(random.uniform(min_s, max_s))


def smooth_scroll(driver: WebDriver, scroll_pause: float = None) -> None:
    """Scroll down the page smoothly to load dynamic content."""
    pause = scroll_pause or SCRAPING_CONFIG["scroll_pause"]
    
    # Get scroll height
    last_height = driver.execute_script("return document.body.scrollHeight")
    
    while True:
        # Scroll down incrementally
        current_position = driver.execute_script("return window.pageYOffset")
        target_position = min(current_position + 500, last_height)
        
        driver.execute_script(f"window.scrollTo(0, {target_position})")
        time.sleep(pause)
        
        # Check if we've reached the bottom
        new_height = driver.execute_script("return document.body.scrollHeight")
        if current_position + 500 >= last_height and new_height == last_height:
            break
        last_height = new_height


def scroll_to_element(driver: WebDriver, element: WebElement) -> None:
    """Scroll to make an element visible."""
    driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
    time.sleep(0.3)


def safe_get_text(element: Optional[WebElement], default: str = "") -> str:
    """Safely get text from an element."""
    if element is None:
        return default
    try:
        text = element.text.strip()
        return text if text else default
    except Exception:
        return default


def safe_find_element(driver: WebDriver, by: By, selector: str, timeout: int = 5) -> Optional[WebElement]:
    """Safely find an element with wait."""
    try:
        element = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((by, selector))
        )
        return element
    except Exception:
        return None


def safe_find_elements(driver: WebDriver, by: By, selector: str, timeout: int = 5) -> list:
    """Safely find multiple elements with wait."""
    try:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((by, selector))
        )
        return driver.find_elements(by, selector)
    except Exception:
        return []


def clean_text(text: str) -> str:
    """Clean up text by removing extra whitespace."""
    if not text:
        return ""
    # Replace multiple whitespace with single space
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def extract_salary(text: str) -> Optional[str]:
    """Extract salary information from text."""
    # Common patterns for Polish job sites
    patterns = [
        r'(\d[\d\s]*[-–]\s*\d[\d\s]*\s*(?:PLN|zł|EUR|USD))',
        r'(\d[\d\s]*\s*(?:PLN|zł|EUR|USD))',
        r'(od\s*\d[\d\s]*\s*(?:PLN|zł|EUR|USD))',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return clean_text(match.group(1))
    
    return None


def click_element_safely(driver: WebDriver, element: WebElement) -> bool:
    """Safely click an element with scroll and retry."""
    try:
        scroll_to_element(driver, element)
        random_delay(0.3, 0.6)
        element.click()
        return True
    except Exception:
        try:
            # Try JavaScript click as fallback
            driver.execute_script("arguments[0].click();", element)
            return True
        except Exception:
            return False


def wait_for_page_load(driver: WebDriver, timeout: int = 10) -> None:
    """Wait for page to fully load."""
    WebDriverWait(driver, timeout).until(
        lambda d: d.execute_script("return document.readyState") == "complete"
    )
