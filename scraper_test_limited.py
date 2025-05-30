# -*- coding: utf-8 -*-
import nest_asyncio
nest_asyncio.apply()

import asyncio
import json
from playwright.async_api import async_playwright
import firebase_admin
from firebase_admin import credentials, firestore
import datetime

# Setup Firebase
cred = credentials.Certificate("serviceAccount.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

BASE_URL = "https://viviensmodels.com.au/sydney/mainboard/"

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

    print(f"✅ All models loaded: {len(models)} found", flush=True)
    return await page.query_selector_all("div.model")

async def scrape_viviens_models():
    model_data = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(BASE_URL)
        await page.wait_for_selector("div.model")
        print("🌐 Navigated to mainboard page", flush=True)

        models = await scroll_until_all_models_loaded(page)

        for idx, model in enumerate(models):
            if idx >= 3:
                print("🛑 Reached testing limit of 3 profiles", flush=True)
                break
            try:
                name_el = await model.query_selector("p.name a")
                name = await name_el.evaluate("el => el.textContent.trim()") if name_el else ""
                profile_url = await name_el.get_attribute("href") if name_el else ""
                if not profile_url.startswith("http"):
                    profile_url = f"https://viviensmodels.com.au{profile_url}"

                print(f"🔗 [{idx+1}/{len(models)}] Visiting: {profile_url}", flush=True)

                profile_page = await browser.new_page()
                await profile_page.goto(profile_url)
                await profile_page.wait_for_selector("div#model-gallery", timeout=10000)

                image_els = await profile_page.query_selector_all("div#model-gallery img")
                sample_images = [await img.get_attribute("src") for img in image_els if await img.get_attribute("src")]

                await profile_page.close()

                model_info = {
                    "name": name,
                    "profile_url": profile_url,
                    "sample_images": ";".join(sample_images)
                }

                model_data.append(model_info)
                save_model_to_firestore(model_info)

            except Exception as e:
                print(f"⚠️ Error scraping model [{idx+1}]: {e}", flush=True)

        await browser.close()

    print("✅ Done scraping!", flush=True)
    return model_data

def save_model_to_firestore(model):
    doc_id = model['name'].lower().replace(" ", "_")
    db.collection("models").document(doc_id).set(model)
    print(f"📤 Uploaded: {model['name']} to Firestore", flush=True)

def run():
    asyncio.run(scrape_viviens_models())
    print(f"🏁 Finished at {datetime.datetime.now().isoformat()}", flush=True)

if __name__ == "__main__":
    run()
