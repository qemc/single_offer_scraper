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

### Success
```json
{
  "status": "success",
  "initial_url": "https://linkedin.com/jobs/view/123?tracking=...",
  "url": "https://linkedin.com/jobs/view/123",
  "title": "Data Governance Specialist",
  "company": "Mindbox Sp. z o.o.",
  "source": "theprotocol",
  "location": "Warszawa, Masovian",
  "salary": "24 000 - 27 000 zł",
  "experience_level": "mid • senior",
  "employment_type": "B2B contract (full-time)",
  "work_mode": "hybrid",
  "description": "Full job description...",
  "scraped_at": "2025-12-26T19:29:43.134663"
}
```

**Note:** `initial_url` is the exact URL passed to `scrape_offer()`, while `url` may be cleaned/normalized by the scraper.

### Error
```json
{
  "status": "error",
  "initial_url": "https://example.com/invalid-job",
  "error_description": "Unsupported URL: No scraper available..."
}
```

## Raspberry Pi / Headless Server

```bash
xvfb-run -a python your_script.py
```
