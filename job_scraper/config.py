"""
Browser configuration.
"""

import platform
from dataclasses import dataclass


@dataclass
class BrowserConfig:
    """Browser settings."""
    headless: bool = False
    page_load_timeout: int = 30
    implicit_wait: int = 10


def get_os_type() -> str:
    """Detect the operating system."""
    system = platform.system()
    if system == "Darwin":
        return "macos"
    elif system == "Linux":
        return "linux"
    return "unknown"


def get_browser_config() -> BrowserConfig:
    """Get browser configuration."""
    return BrowserConfig()


# Scraping behavior
SCRAPING_CONFIG = {
    "min_delay": 1.0,
    "max_delay": 3.0,
    "scroll_pause": 0.5,
}
