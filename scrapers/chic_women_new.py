
import nest_asyncio # type: ignore
nest_asyncio.apply()

import asyncio
import re
import json
from playwright.async_api import async_playwright # type: ignore

BASE_URL = "https://www.chicmanagement.com.au/women/mainboard"

async def scrape_chic_models():
    model_data = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(BASE_URL)

        # Scroll to load all models
        previous_height = None
        while True:
            current_height = await page.evaluate("document.body.scrollHeight")
            if previous_height == current_height:
                break
            previous_height = current_height
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(1500)

        model_links = await page.query_selector_all(".model a")
        profile_urls = list(set([await link.get_attribute("href") for link in model_links if link]))

        for url in profile_urls:
            try:
                await page.goto(url)
                name = await page.locator("h1").inner_text()

                # Extract measurements block
                details_block = await page.locator(".model-details p").inner_text()

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

                for line in details_block.split("\n"):
                    match = re.match(r"(Height|Bust|Waist|Hips|Dress|Shoe|Hair|Eyes) (.+)", line)
                    if match:
                        key = match.group(1).lower()
                        value = match.group(2).split("/")[0].strip()  # strip imperial
                        measurements[key] = value

                # Get portfolio images
                images = await page.query_selector_all(".flexslider .slides img")
                image_urls = list({await img.get_attribute("src") for img in images if img})

                model_entry = {
                    "name": name,
                    "agency": "Chic",
                    "gender": "female",
                    "out_of_town": False,
                    "profile_url": url,
                    "portfolio_images": image_urls,
                    "measurements": measurements,
                    "board": BASE_URL
                }

                print(f"✅ Scraped: {name}", flush=True)
                model_data.append(model_entry)

            except Exception as e:
                print(f"❌ Error scraping model at {url}: {e}", flush=True)
                continue

        with open("chic_women.json", "w") as f:
            json.dump(model_data, f, indent=2)

        print(f"✅ Finished scraping {len(model_data)} models.")

if __name__ == "__main__":
    asyncio.run(scrape_chic_models())
