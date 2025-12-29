# Job Offer Scraper

Async job scraper with anti-bot protection using Camoufox.

**Supported sites:** JustJoin.it, TheProtocol.it, Pracuj.pl, LinkedIn

## Installation

Add to your `requirements.txt`:
```
git+https://github.com/qemc/single_offer_scraper.git
```

Or install directly:
```bash
pip install git+https://github.com/qemc/single_offer_scraper.git
```

## Usage

### Single URL

```python
import asyncio
from job_scraper import scrape_offer

result = asyncio.run(scrape_offer("https://justjoin.it/job-offer/..."))

if result["status"] == "success":
    print(f"{result['title']} @ {result['company']}")
else:
    print(f"Error: {result['error_description']}")
```

### Batch Processing

```python
import asyncio
from job_scraper import scrape_batch

urls = [
    "https://justjoin.it/job-offer/...",
    "https://linkedin.com/jobs/view/...",
    "https://theprotocol.it/szczegoly/praca/...",
]

results = asyncio.run(scrape_batch(urls))

for r in results:
    print(f"{r['title']} @ {r['company']}")
```

### Configure Concurrency

Default: 3 concurrent browsers. Lower for memory-constrained devices.

```python
from job_scraper import set_max_concurrent_browsers

set_max_concurrent_browsers(2)  # Raspberry Pi
```

## Response Schema

```json
{
  "status": "success",
  "initial_url": "https://...",
  "url": "https://...",
  "title": "Job Title",
  "company": "Company Name",
  "source": "justjoin|theprotocol|pracuj|linkedin",
  "location": "City",
  "salary": "10000 - 15000 PLN",
  "experience_level": "Junior|Mid|Senior",
  "employment_type": "B2B|UoP",
  "work_mode": "Remote|Hybrid|On-site",
  "description": "Full job description...",
  "scraped_at": "2025-12-29T12:00:00.000000"
}
```

## Error Handling

Errors return the same structure with `status: "error"`:
```json
{
  "status": "error",
  "initial_url": "https://...",
  "error_description": "Detailed error message"
}
```
