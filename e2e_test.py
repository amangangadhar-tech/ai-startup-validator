import re
from playwright.sync_api import sync_playwright

def run(playwright):
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context(viewport={'width': 1280, 'height': 1024})
    page = context.new_page()
    page.goto("http://localhost:8000")
    
    page.fill("#ideaInput", "AI code reviewer for microservices")
    page.click("#validateBtn")
    
    # Wait for the done state. This means the last progress step gets the 'active' class (or 'done').
    print("Waiting for validation to finish...")
    page.wait_for_selector("#step-done.active", timeout=120000)
    
    # Wait a bit for Chart.js animation
    page.wait_for_timeout(2000)
    
    print("Done! Taking screenshot...")
    page.screenshot(path="Phase3_Dashboard.png", full_page=True)

    browser.close()

with sync_playwright() as playwright:
    run(playwright)
