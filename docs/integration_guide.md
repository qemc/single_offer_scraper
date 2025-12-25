# AI Integration Guide

> [!NOTE]
> This document is intended for AI Agents and Developers integrating the scraper into larger systems.

## 1. Python Library Usage

The project exposes a clean synchronous API in `src/engine.py`.

```python
from src.engine import scrape_offer

# Call the scraper - it never throws exceptions
result = scrape_offer("https://theprotocol.it/szczegoly/praca/...")

# Check status
if result["status"] == "success":
    print(f"Title: {result['title']}")
    print(f"Company: {result['company']}")
else:
    print(f"Error: {result['error_description']}")
```

## 2. Response Schema

### Success Response
```json
{
  "status": "success",
  "url": "https://...",
  "title": "Job Title",
  "company": "Company Name",
  "source": "justjoin|theprotocol|pracuj|linkedin",
  "location": "City, Region",
  "salary": "10000 - 15000 PLN",
  "experience_level": "Junior|Mid|Senior",
  "employment_type": "B2B|UoP",
  "work_mode": "Remote|Hybrid|On-site",
  "description": "Full job description...",
  "scraped_at": "2025-12-25T14:06:39.232881"
}
```

### Error Response
```json
{
  "status": "error",
  "error_description": "Detailed error message with traceback if applicable"
}
```

**Common Error Types:**
- `Invalid URL` - Empty or non-string input
- `Unsupported URL` - No scraper matches the URL pattern
- `Browser initialization failed` - Chrome/Chromium not available
- `Timeout` - Page took too long to load
- `Connection error` - Network issues
- `Scraping failed` - Generic error with full traceback

## 3. FastAPI Implementation Example

```python
from fastapi import FastAPI
from pydantic import BaseModel
from src.engine import scrape_offer

app = FastAPI()

class ScrapeRequest(BaseModel):
    url: str

@app.post("/scrape")
def scrape_endpoint(req: ScrapeRequest):
    """
    Scrape a job offer.
    Body: { "url": "https://..." }
    Returns: { "status": "success|error", ... }
    """
    # No try/except needed - engine handles all errors
    return scrape_offer(req.url)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

## 4. Raspberry Pi 5 Deployment (Headless/Xvfb)

To run **undetectable** scraping on a server (like RPi), standard headless mode (`--headless`) is often blocked. The solution is to use `Xvfb` (Virtual Framebuffer) to run a "headful" browser in a virtual display.

### Prerequisites
```bash
sudo apt-get update
sudo apt-get install -y xvfb chromium-browser
pip install fastapi uvicorn
```

### Running the API
```bash
# -a: Auto-allocate display number
# -s: Screen configuration (standard desktop res)
xvfb-run -a -s "-screen 0 1920x1080x24" uvicorn api:app --host 0.0.0.0 --port 8000
```

This command starts the FastAPI server. When `scrape_offer` launches Chrome, it renders into the virtual X11 display, bypassing headless checks.
