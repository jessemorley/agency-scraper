# -*- coding: utf-8 -*-
import nest_asyncio  # type: ignore
nest_asyncio.apply()
import asyncio
from playwright.async_api import async_playwright  # type: ignore
import firebase_admin  # type: ignore
from firebase_admin import credentials, firestore  # type: ignore
from datetime import datetime
import traceback

# Initialize Firebase
cred = credentials.Certificate("serviceAccount.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

BASE_URL = "https://www.chicmanagement.com.au/women/mainboard/"
AGENCY_NAME = "Chic Management"
GENDER = "female"

# Centralized selectors for easy adaptation
SELECTORS = {
    "model_container": "div.models-listing__item",
    "model_name_link": "div.models-listing__name a",
    "profile_gallery": "div.profile-gallery__images img",
    "profile_specs": "div.profile-details__stats",
    "out_of_town": "div.profile-details__out-of-town",
}

MEASUREMENT_LABELS = [
    "Height", "Bust", "Waist", "Hips", "Dress", "Shoe", "Hair", "Eyes"
]

# Function to log scrape results
def log_scrape_result(success, board, added=0, removed=0, error_message=None):
    log_entry = {
        "timestamp": datetime.utcnow(),
        "board": board,
        "success": success,
        "added": added,
        "removed": removed,
    }
    if not success and error_message:
        log_entry["error"] = error_message

    db.collection("scrape_logs").add(log_entry)
    print("📝 Log entry added", flush=True)

# Function to scroll until all models are loaded
async def scroll_until_all_models_loaded(page, max_waits=10):
    previous_count = 0
    same_count_retries = 0

    while True:
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(1000)
        models = await page.query_selector_all(SELECTORS["model_container"])
        current_count = len(models)

        if current_count == previous_count:
            same_count_retries += 1
            if same_count_retries >= max_waits:
                break
        else:
            same_count_retries = 0
            previous_count = current_count

    print(f"✅ All models loaded: {current_count} total", flush=True)
    return await page.query_selector_all(SELECTORS["model_container"])

# Function to save model data to Firestore
def save_model_to_firestore(model):
    doc_id = model['name'].lower().replace(" ", "_")
    db.collection("models").document(doc_id).set(model)
    print(f"📤 Added {model['name']} to Firestore", flush=True)

# Main scraping function
async def scrape_chic_women():
    scraped_ids = []
    added_count = 0

    print(f"🔍 Starting scrape for {AGENCY_NAME} models...", flush=True)
    existing_docs = db.collection("models").stream()
    existing_ids = set()
    for doc in existing_docs:
        data = doc.to_dict()
        if data.get("board") == BASE_URL:
            existing_ids.add(doc.id)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(BASE_URL)
        await page.wait_for_selector('a.models-list-item_modelImage__Wvd4u')

        # Get all profile links directly
        profile_links = await page.eval_on_selector_all(
            'a.models-list-item_modelImage__Wvd4u',
            "els => els.map(el => el.href)"
        )
        total_loaded = len(profile_links)
        total_existing = 0
        total_new = 0

        # Count how many models are already in the database
        for link in profile_links:
            doc_id = link.rstrip('/').split('/')[-1].replace("-", "_").lower()
            if doc_id in existing_ids:
                total_existing += 1
            else:
                total_new += 1

        print(f"📊 Models loaded from site: {total_loaded}", flush=True)
        print(f"📦 Models already in database: {total_existing}", flush=True)
        print(f"🆕 New models to add: {total_new}", flush=True)

        for idx, profile_url in enumerate(profile_links):
            doc_id = profile_url.rstrip('/').split('/')[-1].replace("-", "_").lower()
            scraped_ids.append(doc_id)

            if doc_id in existing_ids:
                print(f"⏭️ Skipping existing model: {doc_id}", flush=True)
                continue

            print(f"➕ [{idx+1}/{len(profile_links)}] New model: {doc_id}", flush=True)

            profile_page = await browser.new_page()
            await profile_page.goto(profile_url)
            await profile_page.wait_for_selector(SELECTORS["profile_gallery"], timeout=10000)
            await profile_page.wait_for_selector(SELECTORS["profile_specs"], timeout=5000)

            # Extract name
            name_el = await profile_page.query_selector("h1.profile-details__name")
            name = await name_el.inner_text() if name_el else doc_id

            # Check for out of town status
            out_of_town = await profile_page.query_selector(SELECTORS["out_of_town"]) is not None

            # Extract measurements from profile details
            measurements = {label.lower(): "" for label in MEASUREMENT_LABELS}
            stats_el = await profile_page.query_selector(SELECTORS["profile_specs"])
            if stats_el:
                stats_text = await stats_el.inner_text()
                import re
                for label in MEASUREMENT_LABELS:
                    match = re.search(rf"{label}:\s*([^\n]+)", stats_text, re.IGNORECASE)
                    if match:
                        measurements[label.lower()] = match.group(1).strip()

            # Extract portfolio images
            image_els = await profile_page.query_selector_all(SELECTORS["profile_gallery"])
            portfolio_images = []
            for img in image_els:
                src = await img.get_attribute("src")
                if src:
                    portfolio_images.append(src)
            await profile_page.close()

            model_data = {
                "name": name,
                "agency": AGENCY_NAME,
                "gender": GENDER,
                "out_of_town": out_of_town,
                "profile_url": profile_url,
                "portfolio_images": portfolio_images,
                "measurements": measurements,
                "board": BASE_URL
            }

            save_model_to_firestore(model_data)
            added_count += 1

        await browser.close()

        print(f"🗑️ Checking for removed models...", flush=True)
        to_delete = existing_ids - set(scraped_ids)
        for doc_id in to_delete:
            db.collection("models").document(doc_id).delete()
            print(f"🗑️ Removed model: {doc_id}")

        print(f"✅ Done! {added_count} new models added. {len(to_delete)} removed.", flush=True)
        log_scrape_result(success=True, board=BASE_URL, added=added_count, removed=len(to_delete))

try:
    asyncio.run(scrape_chic_women())
except Exception as e:
    print("❌ Scrape failed:", e, flush=True)
    traceback.print_exc()
    log_scrape_result(success=False, board=BASE_URL, error_message=str(e))
