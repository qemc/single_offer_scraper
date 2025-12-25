# Single Offer Scraper

Scrapes job offers from Polish job boards.

## Supported Sites
- JustJoin.it
- TheProtocol.it
- Pracuj.pl
- LinkedIn (public view)

## Installation

In your `requirements.txt`:
```
git+https://github.com/qemc/job_offer_scraper.git
```

Then:
```bash
pip install -r requirements.txt
```

## Usage

```python
from job_scraper.engine import scrape_offer

result = scrape_offer("https://justjoin.it/job-offer/...")
print(result)
```

## Response Format

```json
{
  "status": "success",
  "title": "Job Title",
  "company": "Company Name",
  "location": "City",
  "salary": "10000 - 15000 PLN",
  "description": "..."
}
```

## Raspberry Pi / Headless Server

```bash
xvfb-run -a python your_script.py
```
