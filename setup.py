from setuptools import setup, find_packages

setup(
    name="job_offer_scraper",
    version="1.0.0",
    packages=find_packages(),
    package_dir={"": "."},
    install_requires=[
        "undetected-chromedriver>=3.5.0",
        "selenium>=4.15.0",
    ],
    python_requires=">=3.8",
)
