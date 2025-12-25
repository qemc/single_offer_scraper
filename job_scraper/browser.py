"""
Browser management using undetected-chromedriver.
"""

import undetected_chromedriver as uc
from .config import get_browser_config


class BrowserManager:
    """Manages browser instance."""
    
    def __init__(self, use_profile: bool = False):
        self.config = get_browser_config()
        self.driver = None
    
    def create_driver(self) -> uc.Chrome:
        """Create Chrome driver."""
        options = uc.ChromeOptions()
        
        # Performance options
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-notifications")
        
        self.driver = uc.Chrome(
            options=options,
            headless=self.config.headless,
            use_subprocess=True,
        )
        
        self.driver.set_page_load_timeout(self.config.page_load_timeout)
        self.driver.implicitly_wait(self.config.implicit_wait)
        
        return self.driver
    
    def get_driver(self) -> uc.Chrome:
        """Get existing driver or create new one."""
        if self.driver is None:
            self.create_driver()
        return self.driver
    
    def close(self) -> None:
        """Close browser."""
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None
    
    def __enter__(self):
        self.create_driver()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
