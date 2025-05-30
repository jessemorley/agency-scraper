# -*- coding: utf-8 -*-
import nest_asyncio
nest_asyncio.apply()

import asyncio
import re
from playwright.async_api import async_playwright
import firebase_admin
from firebase_admin import credentials, firestore

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

    print(f"✅ All models loaded: {current_count} total", flush=True)
    return await page.query_selector_all("div.model")

def save_model_to_firestore(model):
    doc_id = model['name'].lower().replace(" ", "_")
    db.collection("models").document(doc_id).set(model)
    print(f"📤 Uploaded {model['name']} to Firestore", flush=True)

async def scrape_viviens_mainboard_limited():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(BASE_URL)
        await page.wait_for_selector("div.model")

        models = await scroll_until_all_models_loaded(page)

        for idx, model in enumerate(models[:3]):
            try:
                name_el = await model.query_selector("p.name a")
                name = await name_el.evaluate("el => el.textContent.trim()") if name_el else ""
                profile_url = await name_el.get_attribute("href") if name_el else ""
                if not profile_url.startswith("http"):
                    profile_url = f"https://viviensmodels.com.au{profile_url}"

                print(f"🔗 [{idx+1}/3] Scraping: {name}", flush=True)

                measurements = {
                    "height": "",
                    "bust": "",
                    "waist": "",
                    "hips": "",
                    "dress": "",
                    "hair": "",
                    "eyes": ""
                }

                # Get measurement elements directly from metric spans
                height_el = await model.query_selector("div.measurements .metric:nth-of-type(1)")
                bust_el = await model.query_selector("div.measurements .metric:nth-of-type(2)")
                waist_el = await model.query_selector("div.measurements .metric:nth-of-type(3)")
                hips_el = await model.query_selector("div.measurements .metric:nth-of-type(4)")
                dress_el = await model.eval_on_selector("div.measurements", "el => el.innerText") if await model.query_selector("div.measurements") else ""

                if height_el:
                    height_text = await height_el.inner_text()
                    measurements["height"] = height_text.replace("cm", "").strip()

                if bust_el:
                    measurements["bust"] = await bust_el.inner_text()

                if waist_el:
                    measurements["waist"] = await waist_el.inner_text()

                if hips_el:
                    measurements["hips"] = await hips_el.inner_text()

                if dress_el:
                    match = re.search(r"D\s*(\S+)", dress_el)
                    if match:
                        measurements["dress"] = match.group(1)

                # Hair and eyes
                he_html = await model.eval_on_selector("div.hair-eyes", "el => el.innerText") if await model.query_selector("div.hair-eyes") else None
                if he_html:
                    hair_match = re.search(r"Hair:\s*(.*?)(,|$)", he_html)
                    eyes_match = re.search(r"Eyes:\s*(.*)", he_html)
                    if hair_match: measurements["hair"] = hair_match.group(1).strip()
                    if eyes_match: measurements["eyes"] = eyes_match.group(1).strip()

                # Portfolio images from profile page
                portfolio_images = []
                profile_page = await browser.new_page()
                await profile_page.goto(profile_url)
                await profile_page.wait_for_selector("div#model-gallery", timeout=10000)

                image_els = await profile_page.query_selector_all("div#model-gallery img")
                for img in image_els:
                    src = await img.get_attribute("src")
                    if src:
                        portfolio_images.append(src)
                await profile_page.close()

                model_data = {
                    "name": name,
                    "profile_url": profile_url,
                    "portfolio_images": portfolio_images,
                    "measurements": measurements
                }

                save_model_to_firestore(model_data)

            except Exception as e:
                print(f"⚠️ Error scraping model [{idx+1}]: {e}", flush=True)

        await browser.close()
        print("✅ Done! All model data written to Firestore.", flush=True)

# Run it
asyncio.run(scrape_viviens_mainboard_limited())
