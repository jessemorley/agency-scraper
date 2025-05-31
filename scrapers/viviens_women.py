import asyncio
import re
import json
import traceback
from datetime import datetime
from google.cloud import firestore
from collections import defaultdict
from playwright.async_api import async_playwright

BASE_URL = "https://viviensmodels.com.au/sydney/women/"
AGENCY_NAME = "Vivien's"
GENDER = "female"

SELECTORS = {
    "model_links": "div#model_list a",
    "name": "div.details h2",
    "details": "div.details span",
    "portfolio_images": "ul.slides li img"
}

MEASUREMENT_LABELS = ["height", "bust", "waist", "hips", "dress", "shoe", "hair", "eyes"]

def extract_numeric_value(text):
    match = re.search(r"(\d+\s?cm|\d+)", text)
    if match:
        return re.sub(r"[^\d]", "", match.group(0))
    return ""

async def extract_model_data(page, profile_url):
    await page.goto(profile_url)
    name = await page.locator(SELECTORS["name"]).text_content() or ""
    detail_spans = await page.locator(SELECTORS["details"]).all()
    image_elements = await page.locator(SELECTORS["portfolio_images"]).all()

    # Measurements
    measurements = {label: "" for label in MEASUREMENT_LABELS}
    for span in detail_spans:
        text = (await span.text_content()).strip().lower()
        for label in MEASUREMENT_LABELS:
            if label in text:
                measurements[label] = extract_numeric_value(text)

    # Check for out of town status
    out_of_town = any("out of town" in (await span.text_content()).lower() for span in detail_spans)

    # Portfolio images
    image_urls = []
    for img in image_elements:
        src = await img.get_attribute("src")
        if src:
            image_urls.append(src.strip())

    model = {
        "name": name.strip(),
        "agency": AGENCY_NAME,
        "gender": GENDER,
        "out_of_town": out_of_town,
        "profile_url": profile_url,
        "portfolio_images": image_urls,
        "measurements": measurements,
        "board": BASE_URL
    }

    return model

# Firestore setup
db = firestore.Client()

def log_scrape_result(success, board, error_message=None, scraped_count=0, skipped_count=0):
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "success": success,
        "board": board,
        "scraped_count": scraped_count,
        "skipped_count": skipped_count,
    }
    if error_message:
        log_entry["error_message"] = error_message
    db.collection("scrape_logs").add(log_entry)

async def scrape_viviens_models():
    model_data = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(BASE_URL)
        await auto_scroll(page)

        model_links = await page.locator(SELECTORS["model_links"]).evaluate_all("els => els.map(e => e.href)")

        scraped_count = 0
        skipped_count = 0
        for url in model_links:
            name_key = url.rstrip("/").split("/")[-1].replace("-", "_").lower()
            if db.collection("models").document(name_key).get().exists:
                print(f"⏭️ Skipped existing model: {name_key}", flush=True)
                skipped_count += 1
                continue
            try:
                model = await extract_model_data(page, url)
                db.collection("models").document(name_key).set(model)
                model_data.append(model)
                scraped_count += 1
                print(f"✅ Scraped {model['name']}", flush=True)
            except Exception as e:
                print(f"❌ Error scraping {url}: {e}", flush=True)
            try:
                model = await extract_model_data(page, url)
                model_data.append(model)
                print(f"✅ Scraped {model['name']}", flush=True)
            except Exception as e:
                print(f"❌ Error scraping {url}: {e}", flush=True)

        with open("viviens_women.json", "w") as f:
            json.dump(model_data, f, indent=2)

        print(f"✅ Finished. Total models scraped: {scraped_count}, skipped: {skipped_count}")
        log_scrape_result(success=True, board=BASE_URL, scraped_count=scraped_count, skipped_count=skipped_count)

async def auto_scroll(page):
    previous_height = None
    while True:
        current_height = await page.evaluate("document.body.scrollHeight")
        if previous_height == current_height:
            break
        previous_height = current_height
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(1)

if __name__ == "__main__":
    try:
        asyncio.run(scrape_viviens_models())
    except Exception as e:
        traceback.print_exc()
        log_scrape_result(success=False, board=BASE_URL, error_message=str(e))
