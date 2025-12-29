from setuptools import setup, find_packages

setup(
    name="job_offer_scraper",
    version="2.0.0",
    description="Async job offer scraper using Camoufox with anti-bot protection",
    packages=find_packages(),
    install_requires=[
        "camoufox[geoip]>=0.4.0",
    ],
    python_requires=">=3.9",
)
