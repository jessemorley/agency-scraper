# -*- coding: utf-8 -*-
import nest_asyncio # type: ignore
nest_asyncio.apply()

import asyncio
from playwright.async_api import async_playwright # type: ignore
import firebase_admin # type: ignore
from firebase_admin import credentials, firestore # type: ignore

cred = credentials.Certificate("serviceAccount.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

BASE_URL = "https://viviensmodels.com.au/sydney/men/"

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

async def scrape_viviens_incremental_update():
    scraped_ids = []
    added_count = 0

    # Step 1: fetch existing Firestore doc IDs
    existing_docs = db.collection("models").stream()
    existing_ids = set(doc.id for doc in existing_docs)

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
                "chest": "",
                "waist": "",
                "suit": "",
                "collar": "",
                "shoe": "",
                "hair": "",
                "eyes": ""
            }

            portfolio_images = []
            profile_page = await browser.new_page()
            await profile_page.goto(profile_url)
            await profile_page.wait_for_selector("div#model-gallery", timeout=10000)
            await profile_page.wait_for_selector("dl#specs", timeout=5000)

            # Out of town status
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
            measurements["chest"] = await get_text("Chest")
            measurements["waist"] = await get_text("Waist")
            measurements["suit"] = await get_text("Suit")
            measurements["collar"] = await get_text("Collar")
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
                "agency": "Vivien's",
                "out_of_town": out_of_town,
                "profile_url": profile_url,
                "portfolio_images": portfolio_images,
                "measurements": measurements
            }

            save_model_to_firestore(model_data)
            added_count += 1

        await browser.close()

        # Detect and remove models no longer listed
        scraped_ids = set(scraped_ids)
        to_delete = existing_ids - scraped_ids
        for doc_id in to_delete:
            print(f"🗑️ Deleting model no longer listed: {doc_id}")
            db.collection("models").document(doc_id).delete()

        print(f"✅ Done! {added_count} new models added. {len(to_delete)} removed.", flush=True)

# Run it
asyncio.run(scrape_viviens_incremental_update())
