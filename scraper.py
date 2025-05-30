# -*- coding: utf-8 -*-
"""# Scrapers

## Viviens
"""

import nest_asyncio
nest_asyncio.apply()

import asyncio
import json
from playwright.async_api import async_playwright

BASE_URL = "https://viviensmodels.com.au/sydney/mainboard/"

async def scroll_until_all_models_loaded(page, max_waits=10):
    previous_count = 0
    same_count_retries = 0

    while True:
        # Scroll to bottom
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(1000)  # allow time for AJAX to load

        # Count models
        models = await page.query_selector_all("div.model")
        current_count = len(models)

        if current_count == previous_count:
            same_count_retries += 1
            if same_count_retries >= max_waits:
                break
        else:
            same_count_retries = 0
            previous_count = current_count

    print(f"✅ All models loaded: {current_count} total")
    return await page.query_selector_all("div.model")

async def scrape_viviens_models():
    model_data = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(BASE_URL)
        await page.wait_for_selector("div.model")

        # Scroll until all models are loaded
        models = await scroll_until_all_models_loaded(page)

        for idx, model in enumerate(models):
            try:
                name_el = await model.query_selector("p.name a")
                name = await name_el.evaluate("el => el.textContent.trim()") if name_el else ""
                profile_url = await name_el.get_attribute("href") if name_el else ""
                if not profile_url.startswith("http"):
                    profile_url = f"https://viviensmodels.com.au{profile_url}"

                print(f"🔗 [{idx+1}/{len(models)}] Visiting: {profile_url}")

                # Visit profile
                profile_page = await browser.new_page()
                await profile_page.goto(profile_url)
                await profile_page.wait_for_selector("div#model-gallery", timeout=10000)

                image_els = await profile_page.query_selector_all("div#model-gallery img")
                sample_images = []
                for img in image_els:
                    src = await img.get_attribute("src")
                    if src:
                        sample_images.append(src)

                await profile_page.close()

                model_data.append({
                    "name": name,
                    "profile_url": profile_url,
                    "sample_images": ";".join(sample_images)
                })

            except Exception as e:
                print(f"⚠️ Error scraping model [{idx+1}]: {e}")

        await browser.close()

    with open("viviens_models.json", "w") as f:
        json.dump(model_data, f, indent=2)

    print("✅ Done! Saved to viviens_models.json")
    return model_data

# Run it
asyncio.run(scrape_viviens_models())