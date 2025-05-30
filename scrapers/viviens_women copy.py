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

BASE_URL = "https://viviensmodels.com.au/sydney/mainboard/"
AGENCY_NAME = "Vivien's"
GENDER = "female"

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
    print("📝 Log entry added (success:", success, ")", flush=True)

async def scroll_until_all_models_loaded(page, max_waits=10):
    previous_count = 0
    same_count_retries = 0

    while True:
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(1000)
        models = await page.query_selector_all("div.model")
        current_count = len(models)

        if current_count == previous_count:
            same_count_retries += 1
            if same_count_retries >= max_waits:
                break
        else:
            same_count_retries = 0
            previous_count = current_count

    print(f"✅ All models loaded: {current_count} total", flush=True)
    return await page.query_selector_all("div.model")

def save_model_to_firestore(model):
    doc_id = model['name'].lower().replace(" ", "_")
    db.collection("models").document(doc_id).set(model)
    print(f"📤 Added {model['name']} to Firestore", flush=True)

async def scrape_viviens_men():
    scraped_ids = []
    added_count = 0

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
        await page.wait_for_selector("div.model")

        models = await scroll_until_all_models_loaded(page)

        for idx, model in enumerate(models):
            name_el = await model.query_selector("p.name a")
            name = await name_el.evaluate("el => el.textContent.trim()") if name_el else ""
            profile_url = await name_el.get_attribute("href") if name_el else ""
            if not profile_url.startswith("http"):
                profile_url = f"https://viviensmodels.com.au{profile_url}"

            doc_id = name.lower().replace(" ", "_")
            scraped_ids.append(doc_id)

            if doc_id in existing_ids:
                print(f"⏭️ Skipping existing model: {name}", flush=True)
                continue

            print(f"➕ [{idx+1}/{len(models)}] New model: {name}", flush=True)

            measurements = {
                "height": "",
                "bust": "",
                "waist": "",
                "hips": "",
                "dress": "",
                "shoe": "",
                "hair": "",
                "eyes": ""
            }

            portfolio_images = []
            profile_page = await browser.new_page()
            await profile_page.goto(profile_url)
            await profile_page.wait_for_selector("div#model-gallery", timeout=10000)
            await profile_page.wait_for_selector("dl#specs", timeout=5000)

            out_of_town = await profile_page.query_selector("div.out-of-town") is not None

            async def get_text(dt_label):
                dt = await profile_page.query_selector(f'dl#specs dt:text("{dt_label}")')
                if dt:
                    dd = await dt.evaluate_handle("el => el.nextElementSibling")
                    metric = await dd.query_selector("span.metric")
                    if metric:
                        return await metric.inner_text()
                    else:
                        return await dd.inner_text()
                return ""

            measurements["height"] = await get_text("Height")
            measurements["bust"] = await get_text("Bust")
            measurements["waist"] = await get_text("Waist")
            measurements["hips"] = await get_text("Hips")
            measurements["dress"] = await get_text("Dress")
            measurements["shoe"] = await get_text("Shoe")
            measurements["hair"] = await get_text("Hair")
            measurements["eyes"] = await get_text("Eyes")

            image_els = await profile_page.query_selector_all("div#model-gallery img")
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

        to_delete = existing_ids - set(scraped_ids)
        for doc_id in to_delete:
            db.collection("models").document(doc_id).delete()
            print(f"🗑️ Removed model: {doc_id}")

        print(f"✅ Done! {added_count} new models added. {len(to_delete)} removed.", flush=True)
        log_scrape_result(success=True, board=BASE_URL, added=added_count, removed=len(to_delete))

try:
    asyncio.run(scrape_viviens_men())
except Exception as e:
    print("❌ Scrape failed:", e, flush=True)
    traceback.print_exc()
    log_scrape_result(success=False, board=BASE_URL, error_message=str(e))
