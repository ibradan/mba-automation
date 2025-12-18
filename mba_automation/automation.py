from typing import Optional, Tuple
from playwright.sync_api import Playwright, Page, TimeoutError as PlaywrightTimeoutError
from .scraper import scrape_income, scrape_withdrawal, scrape_balance

VIEWPORTS = {
    "iPhone 12": {"width": 390, "height": 844},
    "Pixel 5": {"width": 393, "height": 851},
    "Samsung S21": {"width": 360, "height": 800}
}


def login(page: Page, phone: str, password: str, timeout: int = 30) -> bool:
    """
    Handles login logic including phone number normalization and popup handling.
    Returns True if login appears successful, False otherwise.
    """
    try:
        # Normalize phone: strip '62' prefix if present
        phone_for_login = phone[2:] if phone.startswith('62') else phone
        print(f"Logging in as {phone} (using: {phone_for_login})...")
        
        page.goto("https://mba7.com/#/login", wait_until="domcontentloaded", timeout=timeout*1000)

        page.get_by_role("textbox", name="Nomor Telepon").click()
        page.get_by_role("textbox", name="Nomor Telepon").fill(phone_for_login)

        page.get_by_role("textbox", name="Kata Sandi").click()
        page.get_by_role("textbox", name="Kata Sandi").fill(password)

        page.get_by_role("button", name="Masuk").click()

        # Checkbox (kalau ada)
        try:
            page.get_by_role("checkbox", name=" Tidak ada lagi yang diminta").click()
        except PlaywrightTimeoutError:
            pass

        # Setelah login: tombol "Mengonfirmasi" muncul 2x
        for i in range(2):
            try:
                page.get_by_role("button", name="Mengonfirmasi").click()
                page.wait_for_timeout(500)
                print(f"Mengonfirmasi login ke-{i+1} OK")
            except PlaywrightTimeoutError:
                print(f"Mengonfirmasi login ke-{i+1} nggak muncul (gapapa, lanjut).")
                break
        
        # Verify login success by waiting for URL change or home element
        try:
            page.wait_for_url("**/#/**", timeout=10000)
            page.wait_for_timeout(2000)
            print("Login successful.")
            return True
        except Exception:
            print("Warning: Login verification timed out, but proceeding...")
            return True

    except Exception as e:
        print(f"Login failed: {e}")
        return False


def perform_tasks(page: Page, iterations: int, review_text: Optional[str] = None) -> Tuple[int, int]:
    """
    Executes the main automation loop: checking progress, submitting reviews.
    Returns (tasks_completed, tasks_total).
    """
    tasks_completed = 0
    tasks_total = iterations

    # Navigate UI to get to the task list
    try:
        page.locator(".van-badge__wrapper.van-icon.van-icon-undefined.iconfont.icon-lipin").click()
    except PlaywrightTimeoutError:
        pass

    try:
        page.locator("i").nth(4).click()
    except PlaywrightTimeoutError:
        pass

    # Some extra clicks from original flow — wrapped in try/except
    for name in ["signIn.submit", "Mengonfirmasi", ""]:
        try:
            page.get_by_role("button", name=name).click()
        except PlaywrightTimeoutError:
            pass

    try:
        page.locator("i").first.click()
    except PlaywrightTimeoutError:
        pass

    # Masuk menu tiket
    try:
        page.locator(
            ".van-badge__wrapper.van-icon.van-icon-undefined.item-icon.iconfont.icon-ticket"
        ).click()
        page.wait_for_timeout(1000)  # Wait for page to load
    except PlaywrightTimeoutError:
        pass

    # ========== SCRAPE ACTUAL PROGRESS FROM PAGE ==========
    try:
        # Get progress indicator element
        progress_element = page.locator(".van-progress__pivot").first
        progress_text = progress_element.text_content(timeout=3000)
        print(f"Progress from page: {progress_text}")
        
        # Parse "60/60" format
        if progress_text and "/" in progress_text:
            parts = progress_text.split("/")
            tasks_completed = int(parts[0].strip())
            tasks_total = int(parts[1].strip())
            print(f"Parsed progress: {tasks_completed}/{tasks_total}")
    except Exception as e:
        print(f"Could not read progress from page: {e}")
        # Will use loop counting as fallback

    # ========== PERTAMA KALI ISI REVIEW ==========
    loop_count = 0
    try:
        if tasks_completed < tasks_total:
            try:
                page.get_by_role("button", name="Mendapatkan").click()
                print("Klik Mendapatkan (list) OK")
            except PlaywrightTimeoutError:
                print("Tombol 'Mendapatkan' di halaman list nggak ketemu.")
                raise Exception("Button 'Mendapatkan' (list) not found")

            page.wait_for_url("**/work**", timeout=10000)

            try:
                page.get_by_role("button", name="Mendapatkan").click()
                print("Klik Mendapatkan (detail) OK")
            except PlaywrightTimeoutError:
                print("Tombol 'Mendapatkan' di halaman detail nggak ketemu.")
                raise Exception("Button 'Mendapatkan' (detail) not found")

            try:
                page.get_by_text("Sedang Berlangsung").nth(1).click()
            except PlaywrightTimeoutError:
                print("'Sedang Berlangsung' ke-2 nggak ketemu.")
                raise Exception("'Sedang Berlangsung' 2 not found")

            try:
                page.get_by_role("radio", name="").click()
            except PlaywrightTimeoutError:
                pass

            page.get_by_role("textbox", name="Harap masukkan ulasan Anda di").click()
            # use provided review_text if given, otherwise default to 'bagus'
            text_to_fill = review_text if (review_text and len(review_text.strip())>0) else "bagus"
            page.get_by_role("textbox", name="Harap masukkan ulasan Anda di").fill(text_to_fill)

            page.get_by_role("button", name="Kirim").click()

            try:
                page.get_by_role("button", name="Mengonfirmasi").click()
            except PlaywrightTimeoutError:
                pass

            # ========== LOOP KIRIM ULANG ==========
            # Calculate remaining iterations
            # We just did 1, so subtract 1 more
            remaining_iterations = max(0, tasks_total - tasks_completed - 1)
            print(f"Tasks completed: {tasks_completed + 1}/{tasks_total}. Remaining loops: {remaining_iterations}")
            
            loop_count = 1 # We already did one
            for i in range(remaining_iterations):
                print(f"Loop ke-{i+1} (Total progress: {tasks_completed + i + 2}/{tasks_total})")
                page.wait_for_timeout(1250)

                try:
                    page.get_by_text("Sedang Berlangsung").nth(1).click()
                    page.get_by_role("button", name="Kirim").click()
                    loop_count += 1  # Count loop iterations
                except PlaywrightTimeoutError:
                    print("Elemen utama nggak ketemu, berhenti loop.")
                    break

                try:
                    page.get_by_role("button", name="Mengonfirmasi").click()
                except PlaywrightTimeoutError:
                    print("Konfirmasi nggak muncul di loop ini (gapapa).")
                    continue
        else:
            print(f"All tasks already completed ({tasks_completed}/{tasks_total}). Skipping automation.")
            loop_count = 0

        print(f"Selesai loop. {loop_count} iterations completed")
        
    except Exception as e:
        print(f"⚠️ Automation loop interrupted: {e}")
        print("Proceeding to scrape data anyway...")

    print(f"Selesai loop. {loop_count} iterations completed")
    
    # Re-scrape progress from page to get final count
    try:
        # Go to ticket page to be sure
        page.locator(".van-badge__wrapper.van-icon.van-icon-undefined.item-icon.iconfont.icon-ticket").click()
        page.wait_for_timeout(500)
        
        progress_element = page.locator(".van-progress__pivot").first
        progress_text = progress_element.text_content(timeout=3000)
        print(f"Final progress from page: {progress_text}")
        
        if progress_text and "/" in progress_text:
            parts = progress_text.split("/")
            tasks_completed = int(parts[0].strip())
            tasks_total = int(parts[1].strip())
            print(f"Parsed final progress: {tasks_completed}/{tasks_total}")
    except Exception as e:
        print(f"Could not re-scrape progress: {e}")
        # Fallback: add loop_count to initial tasks_completed (capped at tasks_total)
        if tasks_completed > 0:
            tasks_completed = min(tasks_completed + loop_count, tasks_total)
            print(f"Using fallback progress calculation: {tasks_completed}/{tasks_total}")

    return tasks_completed, tasks_total


def run(playwright: Playwright, phone: str, password: str, headless: bool = False, slow_mo: int = 200, iterations: int = 30, review_text: Optional[str] = None, viewport_name: str = "iPhone 12", timeout: int = 30, sync_only: bool = False) -> Tuple[int, int, float, float, float]:
    browser = playwright.chromium.launch(headless=headless, slow_mo=slow_mo)
    
    vp = VIEWPORTS.get(viewport_name, VIEWPORTS["iPhone 12"])
    context = browser.new_context(viewport=vp)
    page = context.new_page()

    # Set timeout (convert to ms)
    page.set_default_timeout(timeout * 1000) 

    # OPTIMIZATION: Block heavy resources (images, fonts, media) to save RAM/CPU
    def intercept_route(route):
        if route.request.resource_type in ["image", "media", "font"]:
            route.abort()
        else:
            route.continue_()
    
    page.route("**/*", intercept_route)

    try:
        # ========== LOGIN ==========
        if not login(page, phone, password, timeout):
            print("Login failed, aborting run.")
            return 0, iterations, 0.0, 0.0, 0.0

        # ========== PERFORM TASKS ==========
        tasks_completed, tasks_total = 0, iterations
        if not sync_only:
            tasks_completed, tasks_total = perform_tasks(page, iterations, review_text)
        else:
            print("Sync only mode: checking current progress...")
            try:
                # Direct navigation is more reliable than clicking icons
                page.goto("https://mba7.com/#/ticket", timeout=timeout*1000)
                page.wait_for_timeout(4000)
                from .scraper import try_close_popups
                try_close_popups(page)
                
                # Look for progress text (usually "X/Y")
                progress_element = page.locator(".van-progress__pivot").first
                if progress_element.count() > 0:
                    progress_text = progress_element.text_content(timeout=5000)
                    if progress_text and "/" in progress_text:
                        parts = progress_text.split("/")
                        tasks_completed = int(parts[0].strip())
                        tasks_total = int(parts[1].strip())
                        print(f"  ✓ Current progress detected: {tasks_completed}/{tasks_total}")
                else:
                    # Alternative: check record status count if pivot not found?
                    # For now, if not found, we assume 0 or keep what we have
                    pass
            except Exception as e:
                print(f"  ✗ Could not read progress during sync: {e}")

        # ========== SCRAPE DATA ==========
        print("Scraping income from deposit records...")
        income = scrape_income(page, timeout)
        
        print("Scraping withdrawal from withdrawal records...")
        withdrawal = scrape_withdrawal(page, timeout)

        print("Scraping balance from profile...")
        balance = scrape_balance(page, timeout)
        
        # Return progress with income, withdrawal, and balance
        print(f"Returning final progress: {tasks_completed}/{tasks_total}")
        return tasks_completed, tasks_total, income, withdrawal, balance

    finally:
        context.close()
        browser.close()



