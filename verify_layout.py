from playwright.sync_api import Page, expect, sync_playwright

def verify_layout(page: Page):
    # 1. Visit index - using https
    page.goto("https://localhost:5002")
    expect(page).to_have_title("RACHEL Module Creator")

    # 2. Check for "Create New Module" button
    create_link = page.get_by_role("link", name="+ Create New Module")
    expect(create_link).to_be_visible()

    # 3. Check that forms are NOT present on index
    expect(page.locator("text=Create New Module from RSS")).not_to_be_visible()
    expect(page.locator("text=Create New Weather Module")).not_to_be_visible()

    # Take screenshot of clean index
    page.screenshot(path="/home/jules/verification/clean_index.png")

    # 4. Click Create and verify navigation
    create_link.click()
    expect(page).to_have_title("Create New Module - RACHEL Module Creator")
    expect(page.locator("h1")).to_have_text("Create New Module")

    # 5. Check forms ARE present here
    expect(page.locator("text=Create New Module from RSS")).to_be_visible()
    expect(page.locator("text=Create New Weather Module")).to_be_visible()

    # Take screenshot of create page
    page.screenshot(path="/home/jules/verification/create_page.png")

if __name__ == "__main__":
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--ignore-certificate-errors'])
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()
        try:
            verify_layout(page)
            print("Verification successful!")
        except Exception as e:
            print(f"Verification failed: {e}")
        finally:
            browser.close()
