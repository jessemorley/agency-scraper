# -*- coding: utf-8 -*-
import nest_asyncio  # type: ignore
nest_asyncio.apply()
import asyncio
from playwright.async_api import async_playwright  # type: ignore
import firebase_admin  # type: ignore
from firebase_admin import credentials, firestore  # type: ignore
from datetime import datetime
import traceback
import re

# Initialize Firebase
cred = credentials.Certificate("serviceAccount.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

BASE_URL = "https://www.chicmanagement.com.au/women/mainboard/"
AGENCY_NAME = "Chic"
GENDER = "female"

# Centralized selectors for easy adaptation
SELECTORS = {
    "model_container": "div.models-listing__item",
    "model_name_link": "div.models-listing__name a",
    "profile_gallery": "div.profile-gallery__images img",
    "profile_specs": "div.profile-details__stats",
    "out_of_town": "div.profile-details__out-of-town",
    "profile_image_wrapper": "div.responsive-image_imageWrapper__3799i",
    "profile_link": "a.models-list-item_modelImage__Wvd4u",
    "profile_name": "h1.profile-details__name",
    "measurement_divs": "div.model-detail_modelDetailMeasurements__lXZ2d > div",
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
def save_model_to_firestore(model, doc_id):
    db.collection("models").document(doc_id).set(model)
    print(f"📤 Added {model['name']} to Firestore", flush=True)

# Main scraping function
async def scrape_chic_women():
    scraped_ids = []
    added_count = 0

    print(f"🔍 Starting scrape for {AGENCY_NAME} models...", flush=True)
    # Efficient Firestore query: only get models from this board
    existing_docs = db.collection("models").where("board", "==", BASE_URL).stream()
    existing_ids = set()
    for doc in existing_docs:
        existing_ids.add(doc.id)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(BASE_URL)
        await page.wait_for_selector(SELECTORS["profile_link"])

        profile_links = await page.eval_on_selector_all(
            SELECTORS["profile_link"],
            "els => els.map(el => el.href)"
        )
        total_loaded = len(profile_links)
        total_existing = 0
        total_new = 0

        for link in profile_links:
            name_slug = link.rstrip("/").split("/")[-1].replace("-", "_")
            if name_slug in existing_ids:
                total_existing += 1
            else:
                total_new += 1

        print(f"📊 Models loaded from site: {total_loaded}", flush=True)
        print(f"📦 Models already in database: {total_existing}", flush=True)
        print(f"🆕 New models to add: {total_new}", flush=True)

        for idx, link in enumerate(profile_links):
            name_slug = link.rstrip("/").split("/")[-1].replace("-", "_")
            if name_slug in existing_ids:
                print(f"⏩ Skipping existing model: {name_slug}")
                continue

            profile_page = await browser.new_page()
            try:
                print(f"🔎 Visiting: {link}", flush=True)
                await profile_page.goto(link)
                await profile_page.wait_for_selector(SELECTORS["profile_image_wrapper"], timeout=8000)

                # Images from style attribute
                style_attrs = await profile_page.eval_on_selector_all(
                    SELECTORS["profile_image_wrapper"],
                    'els => els.map(el => el.getAttribute("style"))'
                )
                image_urls = []
                for style in style_attrs:
                    if not style:
                        continue
                    match = re.search(r'url\(["\']?(https?://[^"\')]+)["\']?\)', style)
                    if match:
                        image_urls.append(match.group(1).strip())

                if not image_urls:
                    print(f"⚠️ No images found for {link}")
                    continue

                # Name
                name_el = await profile_page.query_selector(SELECTORS["profile_name"])
                name = await name_el.inner_text() if name_el else name_slug.replace("_", " ")

                # Out of town
                out_of_town = await profile_page.query_selector(SELECTORS["out_of_town"]) is not None

                # Measurements
                measurements = {label.lower(): "" for label in MEASUREMENT_LABELS}
                measurement_divs = await profile_page.query_selector_all(SELECTORS["measurement_divs"])
                for div in measurement_divs:
                    label_span = await div.query_selector("span")
                    if not label_span:
                        continue
                    label_raw = await label_span.inner_text()
                    label = label_raw.strip().lower().replace("colour", "").replace(" ", "")
                    value = (await div.inner_text()).replace(label_raw, "").strip()
                    if label in ["height", "bust", "waist", "hips"]:
                        value = value.split("/")[0].strip()
                    if label.startswith("eye"):
                        key = "eyes"
                    elif label.startswith("hair"):
                        key = "hair"
                    elif label.startswith("shoe"):
                        key = "shoe"
                    else:
                        key = label
                    if key in measurements:
                        measurements[key] = value

                model_data = {
                    "name": name,
                    "agency": AGENCY_NAME,
                    "gender": GENDER,
                    "out_of_town": out_of_town,
                    "profile_url": link,
                    "portfolio_images": image_urls,
                    "measurements": measurements,
                    "board": BASE_URL
                }

                save_model_to_firestore(model_data, name_slug)
                scraped_ids.append(name_slug)
                added_count += 1

            except Exception as e:
                print(f"❌ Error scraping {link}: {e}", flush=True)
                traceback.print_exc()
            finally:
                await profile_page.close()

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
