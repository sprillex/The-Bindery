
from playwright.sync_api import Page, expect, sync_playwright

def verify_logs_feature(page: Page):
    # 1. Visit index - using https
    page.goto("https://localhost:5002")
    expect(page).to_have_title("RACHEL Module Creator")

    # 2. Check for "View Logs" link
    logs_link = page.get_by_role("link", name="View Logs")
    expect(logs_link).to_be_visible()

    # 3. Click and verify navigation
    logs_link.click()
    expect(page).to_have_title("Server Logs - RACHEL Module Creator")
    expect(page.locator("h1")).to_have_text("Server Logs")

    # 4. Check for log content (basic check)
    expect(page.locator("#log-content")).to_be_visible()

    # Take screenshot
    page.screenshot(path="/home/jules/verification/logs_page.png")

if __name__ == "__main__":
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--ignore-certificate-errors'])
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()
        try:
            verify_logs_feature(page)
            print("Verification successful!")
        except Exception as e:
            print(f"Verification failed: {e}")
        finally:
            browser.close()
