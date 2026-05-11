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

# Global status tracking
STATUS = "Bot starting..."
LAST_UPDATE = "Never"
NEXT_RUN = "Unknown"
SECONDS_REMAINING = 0
SECONDS_UNTIL_CHECK = 0
LAST_CHECK = "Never"

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
                global STATUS, LAST_UPDATE, NEXT_RUN, SECONDS_REMAINING, SECONDS_UNTIL_CHECK
                LAST_UPDATE = time.strftime('%H:%M:%S')
                
                await page.goto(URL)
                await take_screenshot(page)
                await asyncio.sleep(5)

                STATUS = "Cleaning popups and ads..."
                await close_popups(page)
                await take_screenshot(page)

                # Fill the form
                STATUS = f"Filling form (Name: {NAME}, UID: {UID})..."
                await page.fill('input[name="Name"]', NAME)
                await page.fill('input[name="FreeFireUID"]', UID)
                await take_screenshot(page)

                # Submit
                submit_btn = page.locator('input[type="submit"]')
                if await submit_btn.is_visible():
                    STATUS = "Submitting form..."
                    print("Clicking submit button...")
                    
                    wait_time = 0
                    def handle_dialog(dialog):
                        nonlocal wait_time
                        print(f"Alert received: {dialog.message}")
                        cooldown = parse_cooldown(dialog.message)
                        if cooldown:
                            h, m = cooldown
                            wait_time = (h * 3600) + (m * 60) + 60
                        asyncio.create_task(dialog.dismiss())

                    page.on("dialog", handle_dialog)
                    try:
                        await submit_btn.click(force=True, timeout=5000)
                    except Exception as e:
                        print(f"Click failed, trying JS click: {e}")
                        await page.evaluate('document.querySelector("input[type=\\"submit\\"]").click()')
                    
                    await asyncio.sleep(2)
                    await take_screenshot(page)

                    if wait_time > 0:
                        SECONDS_REMAINING = wait_time
                        NEXT_RUN = time.strftime('%H:%M:%S', time.localtime(time.time() + wait_time))
                        
                        while SECONDS_REMAINING > 0:
                            # Set Next Check to 1 hour or remaining time
                            SECONDS_UNTIL_CHECK = min(SECONDS_REMAINING, 3600)
                            
                            while SECONDS_UNTIL_CHECK > 0:
                                m, s = divmod(SECONDS_REMAINING, 60)
                                h, m = divmod(m, 60)
                                STATUS = f"Cooldown: {h:02d}:{m:02d}:{s:02d} remaining..."
                                await asyncio.sleep(1)
                                SECONDS_REMAINING -= 1
                                SECONDS_UNTIL_CHECK -= 1
                            
                            if SECONDS_REMAINING > 0:
                                print("Hourly check: Re-verifying site status...")
                                break # Re-run main navigation
                    else:
                        print("Submission successful! Waiting for 10-hour cycle...")
                        SECONDS_REMAINING = 10 * 3600
                        NEXT_RUN = time.strftime('%H:%M:%S', time.localtime(time.time() + SECONDS_REMAINING))
                        while SECONDS_REMAINING > 0:
                            SECONDS_UNTIL_CHECK = min(SECONDS_REMAINING, 3600)
                            while SECONDS_UNTIL_CHECK > 0:
                                m, s = divmod(SECONDS_REMAINING, 60)
                                h, m = divmod(m, 60)
                                STATUS = f"Next Run: {h:02d}:{m:02d}:{s:02d} left..."
                                await asyncio.sleep(1)
                                SECONDS_REMAINING -= 1
                                SECONDS_UNTIL_CHECK -= 1
                            break # Re-check hourly
                else:
                    STATUS = "Error: Submit button not found. Retrying..."
                    await asyncio.sleep(60)
            except Exception as e:
                STATUS = f"Loop Error: {str(e)[:50]}..."
                print(f"Unexpected error in loop: {e}")
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
    img_html = '<p>Waiting for first screenshot...</p>'
    if os.path.exists('static/preview.png'):
        img_html = f'<img src="/static/preview.png?t={time.time()}">'
    
    return f"""
    <html>
        <head>
            <title>HUKEX Bot Premium</title>
            <meta http-equiv="refresh" content="30">
            <style>
                body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; text-align: center; background: #0b0b0d; color: #e0e0e0; padding: 20px; }}
                .container {{ max-width: 950px; margin: auto; background: #141417; padding: 35px; border-radius: 20px; border: 1px solid #2a2a2e; box-shadow: 0 15px 45px rgba(0,0,0,0.6); }}
                img {{ max-width: 100%; border: 2px solid #3a3a3e; border-radius: 12px; margin-top: 25px; box-shadow: 0 5px 15px rgba(0,0,0,0.3); }}
                .status-box {{ display: flex; justify-content: space-around; margin-bottom: 25px; padding: 20px; background: #1c1c1f; border-radius: 12px; border-top: 3px solid #ff9800; }}
                .status-item {{ flex: 1; }}
                .label {{ font-size: 0.8em; color: #777; text-transform: uppercase; letter-spacing: 1.5px; margin-bottom: 8px; }}
                .value {{ font-size: 1.25em; font-weight: 600; color: #4caf50; }}
                .timer-container {{ display: flex; justify-content: space-between; gap: 20px; margin-bottom: 25px; }}
                .timer-box {{ flex: 1; background: #1c1c1f; padding: 20px; border-radius: 12px; border-bottom: 3px solid #2196f3; }}
                .countdown {{ font-size: 2.2em; color: #ff5722; font-family: 'Courier New', Courier, monospace; font-weight: bold; margin-top: 10px; }}
                h1 {{ color: #ff9800; margin-bottom: 5px; font-size: 2.8em; text-transform: uppercase; letter-spacing: 2px; }}
                .subtitle {{ color: #666; margin-bottom: 35px; font-style: italic; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>HUKEX PREMIER BOT</h1>
                <div class="subtitle">Ultimate Automation Dashboard</div>
                
                <div class="status-box">
                    <div class="status-item">
                        <div class="label">Bot Status</div>
                        <div class="value">{STATUS}</div>
                    </div>
                </div>

                <div class="timer-container">
                    <div class="timer-box">
                        <div class="label">Next Status Check</div>
                        <div id="check-timer" class="countdown">00:00:00</div>
                    </div>
                    <div class="timer-box" style="border-bottom-color: #f44336;">
                        <div class="label">Total Time Remaining</div>
                        <div id="total-timer" class="countdown">00:00:00</div>
                    </div>
                </div>

                <div class="status-box" style="border-top-color: #2196f3; margin-top: 10px;">
                    <div class="status-item">
                        <div class="label">Last Interaction</div>
                        <div class="value">{LAST_UPDATE}</div>
                    </div>
                    <div class="status-item">
                        <div class="label">Scheduled Submission</div>
                        <div class="value">{NEXT_RUN}</div>
                    </div>
                </div>

                {img_html}
            </div>

            <script>
                let totalSecs = {SECONDS_REMAINING};
                let checkSecs = {SECONDS_UNTIL_CHECK};
                
                function fmt(s) {{
                    let h = Math.floor(s / 3600);
                    let m = Math.floor((s % 3600) / 60);
                    let sc = s % 60;
                    return (h<10?'0'+h:h) + ":" + (m<10?'0'+m:m) + ":" + (sc<10?'0'+sc:sc);
                }}

                function tick() {{
                    document.getElementById('total-timer').innerText = fmt(totalSecs);
                    document.getElementById('check-timer').innerText = fmt(checkSecs);
                    
                    if (totalSecs > 0) totalSecs--;
                    if (checkSecs > 0) checkSecs--;
                    else if (totalSecs > 0) {{
                        document.getElementById('check-timer').innerText = "RE-CHECKING...";
                    }}
                }}
                
                setInterval(tick, 1000);
                tick();
            </script>
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
