"""
Single Offer Scraper - Simple Entry Point
"""

from job_scraper.engine import scrape_offer

# Paste your job offer URL here
URL = "https://theprotocol.it/szczegoly/praca/data-governance-specialist-warszawa,oferta,acdf0000-ee11-326b-db88-08de434052b8"

if __name__ == "__main__":
    result = scrape_offer(URL)
    print(result)
