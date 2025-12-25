# Scraper Maintenance Guide

> [!IMPORTANT]
> This guide is for AI Agents upgrading the scrapers when vendor sites change.

## General Strategy
All scrapers prioritize **Strict Extraction** (no guessing). If a selector fails, it returns `None` or `Unknown` rather than guessing a potentially wrong value. When upgrading, maintain this philosophy.

## Project Structure

```
src/
├── engine.py          # Entry point - scrape_offer() function
├── browser.py         # Chrome driver management (undetected-chromedriver)
├── models.py          # JobOffer dataclass with to_dict()
├── utils.py           # Helper functions (delays, scrolling, safe element finding)
└── scrapers/
    ├── base.py        # BaseScraper abstract class
    ├── justjoin.py    # JustJoin.it scraper
    ├── theprotocol.py # TheProtocol.it scraper
    ├── pracuj.py      # Pracuj.pl scraper
    └── linkedin.py    # LinkedIn scraper
```

## Site-Specific Maintenance

### 1. JustJoin.it (`src/scrapers/justjoin.py`)

**Current Strategy**: `data-testid` attributes
- Title: `[data-testid="offer-view-title"]`
- Company: `[data-testid="offer-view-company"]`
- Description: `[data-testid="offer-view-content"]`

**Fragility**: High. They use dynamic CSS modules (`css-1x2y3z`). **DO NOT use class names**.

**When It Breaks**:
1. Open job page in browser DevTools
2. Search for `data-testid` attributes
3. If removed, look for `__next` container structure or JSON-LD in `<script type="application/ld+json">`
4. Update the `EXTRACTION_SCRIPT` JavaScript in the file

---

### 2. TheProtocol.it (`src/scrapers/theprotocol.py`)

**Current Strategy**: `data-test` attributes
- Title: `[data-test="text-offerTitle"]`
- Company: `[data-test="text-offerEmployer"]`
- Sections: `[data-test="section-requirements"]`, `[data-test="section-responsibilities"]`, etc.

**Robustness**: High. Very clean structure.

**Multilingual**: Supports Polish/English via stable section IDs.

**When It Breaks**:
1. Check if `data-test` changed to `data-testid` or similar
2. Update the `sections` array in `EXTRACTION_SCRIPT`
3. Company may have "Firma: " prefix - the regex handles this

---

### 3. Pracuj.pl (`src/scrapers/pracuj.py`)

**Current Strategy**: Hybrid approach
- Metadata: `[data-test="sections-benefit-*"]` attributes
- JSON-LD: `<script type="application/ld+json">` for company, title
- Description: `[data-test="section-job-description"]` or `[data-scroll-id="job-description"]`

**Common Issues**: 
- "Show full description" button may need clicking
- Description container class names change frequently

**When It Breaks**:
1. Check JSON-LD first (usually stable)
2. Inspect description container - look for `data-test` or `data-scroll-id`
3. Update `_expand_description()` if button selector changes

---

### 4. LinkedIn (`src/scrapers/linkedin.py`)

**Current Strategy**: Dual-View Support (Guest + Logged-in)

**Guest View Selectors**:
- Title: `h1.top-card-layout__title`
- Company: `a.topcard__org-name-link`
- Description: `.description__text`, `.show-more-less-html__content`

**Logged-in View Selectors** (fallback):
- Title: `.jobs-unified-top-card__job-title`
- Company: `.jobs-unified-top-card__company-name`
- Description: `.jobs-description__content`

**Complexity**: Extreme. LinkedIn serves different HTML based on:
- Login state
- A/B testing
- Cookies and session

**Critical Points**:
1. URL handling: `_clean_url()` extracts `currentJobId` from query params
2. "Show more" button: Script removes trailing "Show less" text
3. Always test BOTH guest and logged-in views when debugging

**When It Breaks**:
1. Open page in incognito (guest view) and logged-in
2. Compare DOM structures
3. Update selector arrays in `EXTRACTION_SCRIPT` - they try multiple selectors in order

---

## Testing After Changes

```bash
# Test each site
python main.py  # Update URL in main.py for each site

# Expected output: dict with "status": "success"
```

## Key Files to Modify

| Issue | File to Edit |
|-------|-------------|
| Selector not finding element | `src/scrapers/<site>.py` - update `EXTRACTION_SCRIPT` |
| Browser issues | `src/browser.py` |
| New field needed | `src/models.py` (add to JobOffer dataclass) |
| Timing/delay issues | `config.py` (SCRAPING_CONFIG) |
