import asyncio
import re
import time
import threading
import os
from flask import Flask, send_from_directory
from playwright.async_api import async_playwright

# Configuration
NAME = "HUKEX"
UID = "877998709"
URL = "https://www.lordneox.top/index.html"

async def close_popups(page):
    """Attempt to close common popups/ads on the site."""
    try:
        # 1. Remove iframes and overlays that block clicks
        await page.evaluate("""() => {
            const blockSelectors = ['iframe', '.adsbygoogle', '#announcementPopup', '.overlay', '.modal'];
            blockSelectors.forEach(selector => {
                document.querySelectorAll(selector).forEach(el => {
                    // Only remove if they are likely ads or popups
                    if (selector !== '#announcementPopup' || el.style.display !== 'none') {
                        el.remove();
                    }
                });
            });
        }""")
        
        # 2. Specifically look for close buttons if they are part of the UI logic
        close_selectors = [
            "#announcementPopup .close", "#announcementPopup .btn-close",
            ".close-button", ".close-btn", "#close-button", 
            "button:has-text('Close')", "span:has-text('×')"
        ]
        for selector in close_selectors:
            if await page.is_visible(selector):
                await page.click(selector, timeout=2000)
                print(f"Closed popup using: {selector}")
                await asyncio.sleep(1)
    except Exception as e:
        # We don't want to crash if a popup isn't found or already removed
        pass

def parse_cooldown(text):
    """Extract hours and minutes from the cooldown message."""
    # Example: ⏳ Please wait 6h 9m before submitting again.
    match = re.search(r'(\d+)h\s*(\d+)m', text)
    if match:
        hours = int(match.group(1))
        minutes = int(match.group(2))
        return hours, minutes
    return None

async def run_bot():
    async with async_playwright() as p:
        # On servers (Render/Docker), headless must be True.
        # Locally, you can set it to False if you want to see the browser.
        headless_mode = os.environ.get("HEADLESS", "True").lower() == "true"
        browser = await p.chromium.launch(headless=headless_mode)
        context = await browser.new_context()
        page = await context.new_page()

        while True:
            try:
                await page.goto(URL)
                await take_screenshot(page)
                await asyncio.sleep(5)  # Wait for ads/popups to load

                await close_popups(page)
                await take_screenshot(page)

                # Fill the form
                print(f"Filling form: Name={NAME}, UID={UID}")
                await page.fill('input[name="Name"]', NAME)
                await page.fill('input[name="FreeFireUID"]', UID)
                await take_screenshot(page)

                # Submit using pixel click or button click
                submit_btn = page.locator('input[type="submit"]')
                if await submit_btn.is_visible():
                    print("Clicking submit button...")
                    
                    # Capture alerts (which site uses for cooldown messages)
                    wait_time = 0
                    def handle_dialog(dialog):
                        nonlocal wait_time
                        print(f"Alert received: {dialog.message}")
                        cooldown = parse_cooldown(dialog.message)
                        if cooldown:
                            h, m = cooldown
                            wait_time = (h * 3600) + (m * 60) + 60  # Add 1 minute buffer
                        asyncio.create_task(dialog.dismiss())

                    page.on("dialog", handle_dialog)
                    try:
                        # Use force=True to click even if something is theoretically 'intercepting' it
                        await submit_btn.click(force=True, timeout=5000)
                    except Exception as e:
                        print(f"Click failed, trying JS click: {e}")
                        await page.evaluate('document.querySelector("input[type=\\"submit\\"]").click()')
                    
                    await asyncio.sleep(2)
                    await take_screenshot(page)

                    if wait_time > 0:
                        print(f"Cooldown active. Waiting for {wait_time // 3600}h {(wait_time % 3600) // 60}m...")
                        await asyncio.sleep(wait_time)
                    else:
                        print("Submission successful! Waiting for 10-hour cycle...")
                        await asyncio.sleep(10 * 3600)  # Wait 10 hours for next submission
                else:
                    print("Submit button not found. Retrying in 1 minute...")
                    await asyncio.sleep(60)
            except Exception as e:
                print(f"Unexpected error in loop: {e}")
                print("Retrying in 1 minute...")
                await asyncio.sleep(60)

async def take_screenshot(page):
    """Capture a screenshot for the web preview."""
    try:
        if not os.path.exists('static'):
            os.makedirs('static')
        await page.screenshot(path='static/preview.png')
    except Exception as e:
        print(f"Failed to take screenshot: {e}")

# Add a web server for the preview dashboard
app = Flask(__name__)

@app.route('/')
def home():
    return """
    <html>
        <head>
            <title>LordNeox Bot Preview</title>
            <meta http-equiv="refresh" content="5">
            <style>
                body { font-family: sans-serif; text-align: center; background: #121212; color: white; }
                img { max-width: 90%; border: 5px solid #333; margin-top: 20px; }
                .status { margin-top: 10px; font-size: 1.2em; color: #00ff00; }
            </style>
        </head>
        <body>
            <h1>LordNeox Bot Status</h1>
            <div class="status">Live Preview (Auto-refreshes every 5s)</div>
            <img src="/static/preview.png?t=""" + str(time.time()) + """">
        </body>
    </html>
    """

@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('static', path)

def run_flask():
    app.run(host='0.0.0.0', port=10000)

if __name__ == "__main__":
    # Start Flask in a background thread
    threading.Thread(target=run_flask, daemon=True).start()
    
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        print("\nBot stopped by user.")
