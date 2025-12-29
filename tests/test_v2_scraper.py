#!/usr/bin/env python3
"""
Test V2 Camoufox Scraper - Single and Batch functionality.

Tests:
1. Single URL scraping with scrape_offer
2. Batch scraping with scrape_batch (multiple URLs)
3. Batch scraping with single URL (edge case)
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path

from job_scraper import scrape_offer, scrape_batch, get_max_concurrent_browsers

# Test URLs
TEST_URLS = [
    "https://justjoin.it/job-offer/n-ix-junior-data-engineer-warszawa-data",
    "https://www.linkedin.com/jobs/view/4350691274",
    "https://www.linkedin.com/jobs/view/4343075815",
    "https://theprotocol.it/szczegoly/praca/data-governance-specialist-warszawa,oferta,acdf0000-ee11-326b-db88-08de434052b8",
]

# Output directory
OUTPUT_DIR = Path(__file__).parent / "results"
OUTPUT_DIR.mkdir(exist_ok=True)


def print_result_summary(result: dict, index: int = None) -> None:
    """Print a summary of a scraping result."""
    prefix = f"[{index}] " if index is not None else ""
    status = result.get("status", "unknown")
    
    if status == "success":
        print(f"{prefix}✅ {result.get('source', '?').upper()}: {result.get('title', 'N/A')[:50]}")
        print(f"   Company: {result.get('company', 'N/A')}")
        print(f"   Salary: {result.get('salary', '-')}")
        print(f"   Experience: {result.get('experience_level', '-')}")
        print(f"   Work Mode: {result.get('work_mode', '-')}")
    else:
        error = result.get("error_description", "Unknown error")[:80]
        print(f"{prefix}❌ Error: {error}...")


def save_json(data, filename: str) -> Path:
    """Save data to JSON file."""
    filepath = OUTPUT_DIR / filename
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return filepath


async def test_single_scrape():
    """Test 1: Single URL scraping."""
    print("\n" + "=" * 60)
    print("TEST 1: Single URL Scraping (scrape_offer)")
    print("=" * 60)
    
    url = TEST_URLS[0]
    print(f"\nURL: {url}\n")
    
    result = await scrape_offer(url)
    
    print_result_summary(result)
    
    # Save result
    filepath = save_json(result, "test_single_scrape.json")
    print(f"\n📄 Saved to: {filepath}")
    
    return result


async def test_batch_scrape():
    """Test 2: Batch scraping with multiple URLs."""
    print("\n" + "=" * 60)
    print("TEST 2: Batch Scraping (scrape_batch with 4 URLs)")
    print(f"Concurrency limit: {get_max_concurrent_browsers()}")
    print("=" * 60)
    
    print(f"\nScraping {len(TEST_URLS)} URLs in parallel...\n")
    
    results = await scrape_batch(TEST_URLS)
    
    for i, result in enumerate(results, 1):
        print_result_summary(result, i)
        print()
    
    # Save results
    filepath = save_json(results, "test_batch_scrape.json")
    print(f"📄 Saved to: {filepath}")
    
    return results


async def test_batch_single_url():
    """Test 3: Batch scraping with single URL (edge case)."""
    print("\n" + "=" * 60)
    print("TEST 3: Batch Scraping with Single URL (edge case)")
    print("=" * 60)
    
    url = TEST_URLS[0]
    print(f"\nURL: {url}\n")
    
    results = await scrape_batch([url])
    
    print(f"Returned type: {type(results)}")
    print(f"Length: {len(results)}")
    
    if len(results) == 1:
        print_result_summary(results[0])
    
    # Save result
    filepath = save_json(results, "test_batch_single_url.json")
    print(f"\n📄 Saved to: {filepath}")
    
    return results


async def main():
    """Run all tests."""
    print("\n🚀 V2 Camoufox Scraper - Full Test Suite")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"Concurrency: {get_max_concurrent_browsers()} concurrent browsers")
    
    all_passed = True
    
    # Test 1: Single scrape
    try:
        result = await test_single_scrape()
        if result.get("status") != "success":
            all_passed = False
    except Exception as e:
        print(f"❌ Test 1 FAILED: {e}")
        all_passed = False
    
    # Test 2: Batch scrape
    try:
        results = await test_batch_scrape()
        if not all(r.get("status") == "success" for r in results):
            print("⚠️ Some URLs failed in batch")
    except Exception as e:
        print(f"❌ Test 2 FAILED: {e}")
        all_passed = False
    
    # Test 3: Batch with single URL
    try:
        results = await test_batch_single_url()
        if len(results) != 1:
            print("❌ Batch single URL should return array with 1 item")
            all_passed = False
        elif results[0].get("status") != "success":
            all_passed = False
    except Exception as e:
        print(f"❌ Test 3 FAILED: {e}")
        all_passed = False
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    if all_passed:
        print("✅ All tests passed!")
    else:
        print("⚠️ Some tests had issues - check output above")
    
    print(f"\nResults saved to: {OUTPUT_DIR.absolute()}")


if __name__ == "__main__":
    asyncio.run(main())
