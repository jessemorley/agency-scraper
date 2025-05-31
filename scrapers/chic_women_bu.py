# -*- coding: utf-8 -*-
import nest_asyncio
nest_asyncio.apply()

import asyncio
import re
from datetime import datetime
from playwright.async_api import async_playwright
import firebase_admin
from firebase_admin import credentials, firestore
import traceback

cred = credentials.Certificate("serviceAccount.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

BASE_URL = "https://www.chicmanagement.com.au/women/mainboard"

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

def save_model_to_firestore(model):
    doc_id = model['name'].lower().replace(" ", "_")
    db.collection("models").document(doc_id).set(model)
    print(f"📤 Added {model['name']} to Firestore", flush=True)

async def scrape_chic_models():
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
        await page.wait_for_selector('a.models-list-item_modelImage__Wvd4u')

        profile_links = await page.eval_on_selector_all(
            'a.models-list-item_modelImage__Wvd4u',
            "els => els.map(el => el.href)"
        )

        print(f"✅ Found {len(profile_links)} model profiles.", flush=True)

        for link in profile_links:
            name_slug = link.rstrip("/").split("/")[-1]
            if name_slug in existing_ids:
                print(f"⏩ Skipping existing model: {name_slug}")
                continue

            try:
                print(f"🔎 Visiting: {link}", flush=True)
                profile_page = await browser.new_page()
                await profile_page.goto(link)
                await profile_page.wait_for_selector('div.responsive-image_imageWrapper__3799i', timeout=8000)

                # Images
                style_attrs = await profile_page.eval_on_selector_all(
                    'div.responsive-image_imageWrapper__3799i',
                    'els => els.map(el => el.getAttribute("style"))'
                )
                image_urls = []
                for style in style_attrs:
                    match = re.search(r'url\(["\']?(https?://[^"\')]+)["\']?\)', style)
                    if match:
                        image_urls.append(match.group(1).strip())

                if not image_urls:
                    print(f"⚠️ No images found for {link}")
                    await profile_page.close()
                    continue

                # Measurements
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

                try:
                    items = await profile_page.query_selector_all('div.model-detail_modelDetailMeasurements__lXZ2d > div')
                    for item in items:
                        text = await item.inner_text()
                        if "Height" in text:
                            measurements["height"] = text.split(" ")[0].strip()
                        elif "Bust" in text:
                            measurements["bust"] = text.split(" ")[0].strip()
                        elif "Waist" in text:
                            measurements["waist"] = text.split(" ")[0].strip()
                        elif "Hips" in text:
                            measurements["hips"] = text.split(" ")[0].strip()
                        elif "Shoes" in text:
                            measurements["shoe"] = text.split(" ")[0].strip()
                        elif "Dress" in text:
                            measurements["dress"] = text.split(" ")[0].strip()
                        elif "Eye Colour" in text:
                            measurements["eyes"] = text.split("Eye Colour")[0].strip()
                        elif "Hair Colour" in text:
                            measurements["hair"] = text.split("Hair Colour")[0].strip()
                except Exception as e:
                    print(f"⚠️ Could not extract measurements for {link}: {e}")

                # Check "Out of Town"
                out_of_town = False
                try:
                    out_of_town_spans = await profile_page.query_selector_all('div.model-detail_item__cBV_M span')
                    for span in out_of_town_spans:
                        span_text = await span.inner_text()
                        if "Out of Town" in span_text:
                            out_of_town = True
                            break
                except:
                    pass

                model = {
                    "name": name_slug.replace("-", " ").title(),
                    "profile_url": link,
                    "portfolio_images": image_urls,
                    "agency": "Chic",
                    "out_of_town": out_of_town,
                    "gender": "female",
                    "board": BASE_URL,
                    "measurements": measurements
                }

                save_model_to_firestore(model)
                scraped_ids.append(name_slug)
                added_count += 1
                await profile_page.close()

            except Exception as e:
                print(f"❌ Error processing {link}: {e}", flush=True)
                traceback.print_exc()
                continue

    log_scrape_result(success=True, board=BASE_URL, added=added_count)

try:
    asyncio.run(scrape_chic_models())
except Exception as e:
    print("❌ Scrape failed:", e, flush=True)
    traceback.print_exc()
    log_scrape_result(success=False, board=BASE_URL, error_message=str(e))
