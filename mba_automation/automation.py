import os
import time
from typing import Optional, Tuple
from playwright.sync_api import Playwright, Page, TimeoutError as PlaywrightTimeoutError
from .scraper import scrape_income, scrape_withdrawal, scrape_balance, try_close_popups
from .reviews import REVIEWS
import random
from datetime import date

VIEWPORTS = {
    "iPhone 12": {"width": 390, "height": 844},
    "Pixel 5": {"width": 393, "height": 851},
    "Samsung S21": {"width": 360, "height": 800}
}

def smart_click(page: Page, selector: str, role: str = None, name: str = None, retries: int = 3, timeout: int = 5000):
    """Reliable clicking with retries and visibility checks."""
    for i in range(retries):
        try:
            if role and name:
                el = page.get_by_role(role, name=name)
            else:
                el = page.locator(selector).first
            
            el.wait_for(state="visible", timeout=timeout)
            el.click(timeout=timeout)
            return True
        except Exception:
            if i == retries - 1:
                return False
            page.wait_for_timeout(500)
    return False


def get_session_path(phone: str) -> str:
    """Returns the path for the session storage file."""
    # Ensure directory exists
    session_dir = os.path.join(os.path.dirname(__file__), "..", "sessions")
    os.makedirs(session_dir, exist_ok=True)
    
    # Normalize phone for filename
    norm = phone[2:] if phone.startswith('62') else phone
    return os.path.join(session_dir, f"{norm}.json")


def login(page: Page, context, phone: str, password: str, timeout: int = 30) -> bool:
    """
    Handles login logic including phone number normalization and popup handling.
    Attempts to restore session if available.
    Returns True if login appears successful, False otherwise.
    """
    session_path = get_session_path(phone)
    
    # 1. Try to restore session
    if os.path.exists(session_path):
        print(f"Restoring session from {session_path}...")
        # Note: In Playwright sync, we load storage_state when creating context. 
        # But if we are already here, the context might have been created without state 
        # if the file didn't exist at start (or we are in a retry/reload loop).
        # However, 'run' function now handles initial loading.
        # Here we just verify if we are already logged in.

    try:
        # Normalize phone: strip '62' prefix if present
        phone_for_login = phone[2:] if phone.startswith('62') else phone
        
        # Check if already logged in (session restored)
        page.goto("https://mba7.com/#/mine", wait_until="domcontentloaded", timeout=timeout*1000)
        try_close_popups(page)
        
        # Verify if we are logged in by checking specific element
        # .icon-lipin is usually present on authenticated pages
        # or check for "Saldo Rekening" text
        if page.locator(".iconfont.icon-lipin").count() > 0 or page.get_by_text("Saldo Rekening").is_visible():
            print("Session restored successfully (Already logged in).")
            return True
        
        print(f"Session invalid or expired. Logging in as {phone}...")
        page.goto("https://mba7.com/#/login", wait_until="networkidle", timeout=timeout*1000)
        try_close_popups(page)

        page.get_by_role("textbox", name="Nomor Telepon").fill(phone_for_login)
        page.get_by_role("textbox", name="Kata Sandi").fill(password)
        
        smart_click(page, "button", role="button", name="Masuk")

        # After login: confirm buttons might appear
        for _ in range(3):
            if smart_click(page, "button", role="button", name="Mengonfirmasi", timeout=2000):
                page.wait_for_timeout(500)
            else:
                break
        
        # Verify login
        try:
            page.wait_for_url("**/#/**", timeout=10000)
            success = True
        except Exception:
            # If we are on home page elements, consider success
            success = page.locator(".iconfont.icon-lipin").count() > 0

        if success:
             # Save storage state
             print(f"Login success. Saving session to {session_path}...")
             context.storage_state(path=session_path)
             return True
        
        return False

    except Exception as e:
        print(f"Login failed: {e}")
        return False


def perform_tasks(page: Page, context, phone: str, password: str, iterations: int, review_text: Optional[str] = None, progress_callback=None) -> Tuple[int, int]:
    """
    Executes the main automation loop: checking progress, submitting reviews.
    Returns (tasks_completed, tasks_total).
    """
    tasks_completed = 0
    tasks_total = iterations

    def resurrect_session():
        """Helper to re-login if session is lost."""
        print("⚠️ Session lost! Attempting to resurrect...")
        if login(page, context, phone, password):
            print("🚀 Session resurrected! Navigating back to grab...")
            page.goto("https://mba7.com/#/grab", timeout=45000)
            page.wait_for_timeout(3000)
            try_close_popups(page)
            return True
        return False

    # Navigate to grab page directly (where first Mendapatkan button is)
    print("Navigating to grab page...")
    try:
        page.goto("https://mba7.com/#/grab", timeout=45000) # Increased timeout
        page.wait_for_timeout(3000)  # Wait for page to load
        from .scraper import try_close_popups
        try_close_popups(page)
        print("Grab page loaded successfully")
    except Exception as e:
        print(f"Navigation error: {e}")
        # Detect if we were sent to login
        if "login" in page.url:
            resurrect_session()
        else:
            # Retry once
            try:
                 print("Retrying navigation...")
                 page.reload()
                 page.wait_for_timeout(5000)
                 try_close_popups(page)
            except: pass

    # ========== SCRAPE ACTUAL PROGRESS FROM PAGE ==========
    try:
        # Retry reading progress
        for _ in range(3):
            # Check for logout mid-scrape
            if "login" in page.url:
                resurrect_session()

            try:
                # Get progress indicator element
                progress_element = page.locator(".van-progress__pivot").first
                if progress_element.is_visible(timeout=3000):
                    progress_text = progress_element.text_content(timeout=1000)
                    print(f"Progress from page: {progress_text}")
                    
                    # Parse "60/60" format
                    if progress_text and "/" in progress_text:
                        parts = progress_text.split("/")
                        tasks_completed = int(parts[0].strip())
                        tasks_total = int(parts[1].strip())
                        print(f"Parsed progress: {tasks_completed}/{tasks_total}")
                        
                        # Initial callback
                        if progress_callback:
                            try: progress_callback(tasks_completed, tasks_total)
                            except: pass
                        
                        break
            except: 
                page.wait_for_timeout(1000)
    except Exception as e:
        print(f"Could not read progress from page: {e}")

    # ========== PERTAMA KALI ISI REVIEW ==========
    loop_count = 0
    try:
        if "login" in page.url:
            resurrect_session()

        if tasks_completed < tasks_total:
            # Click Mendapatkan button on grab page (button 1)
            try:
                # Use specific CSS selector for first Mendapatkan button on /grab page
                btn = page.locator("#app > div > div.van-config-provider.provider-box > div.main-wrapper.travel-bg > div.div-flex-center > button").first
                btn.wait_for(state="visible", timeout=15000)
                btn.click()
                print("Klik Mendapatkan (grab page) OK")
            except Exception as e:
                if "login" in page.url:
                    resurrect_session()
                    # Retry once after resurrection
                    btn = page.locator("#app > div > div.van-config-provider.provider-box > div.main-wrapper.travel-bg > div.div-flex-center > button").first
                    btn.click()
                else:
                    print(f"Tombol 'Mendapatkan' (Grab) not found: {e}. Refreshing page...")
                    page.reload()
                    page.wait_for_timeout(5000)
                    try_close_popups(page)
                    # Retry click after refresh
                    try:
                         btn = page.locator("#app > div > div.van-config-provider.provider-box > div.main-wrapper.travel-bg > div.div-flex-center > button").first
                         btn.wait_for(state="visible", timeout=10000)
                         btn.click()
                         print("Klik Mendapatkan (grab page) OK (After Retry)")
                    except:
                         raise Exception("Button 'Mendapatkan' (grab) not found after retry")

            # Wait for navigation to work page
            page.wait_for_url("**/work**", timeout=10000)
            page.wait_for_timeout(2000)  # Wait for page to load

            # Click Mendapatkan button on work/detail page (button 2)
            try:
                # Try text-based selector since van-tab ID might be dynamic
                btn = page.locator("button:has-text('Mendapatkan')").first
                btn.wait_for(state="visible", timeout=15000)
                btn.click()
                print("Klik Mendapatkan (detail) OK")
            except Exception as e:
                if "login" in page.url:
                    resurrect_session()
                    # We might need to go back to grab and start again
                    raise Exception("Redirected to login during detail click")
                print(f"Tombol 'Mendapatkan' di halaman detail nggak ketemu: {e}")
                raise Exception("Button 'Mendapatkan' (detail) not found")

            try:
                page.get_by_text("Sedang Berlangsung").nth(1).click()
            except PlaywrightTimeoutError:
                print("'Sedang Berlangsung' ke-2 nggak ketemu.")
                # Fallback: try looking for the first one if 2nd not found
                # raise Exception("'Sedang Berlangsung' 2 not found")
                pass

            try:
                page.get_by_role("radio", name="").click()
            except PlaywrightTimeoutError:
                pass

            # Determine identifying review for the day if not provided
            daily_seed = f"{date.today()}-{phone}"
            daily_rand = random.Random(daily_seed)
            daily_review = daily_rand.choice(REVIEWS)

            try:
                page.get_by_role("textbox", name="Harap masukkan ulasan Anda di").click()
                # Use provided review_text if given, otherwise pick daily consistent review
                if review_text and len(review_text.strip()) > 0:
                    text_to_fill = review_text
                else:
                    text_to_fill = daily_review
                    print(f"Using daily consistent review: {text_to_fill}")
                
                page.get_by_role("textbox", name="Harap masukkan ulasan Anda di").fill(text_to_fill)
                page.get_by_role("button", name="Kirim").click()
            except: pass

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
            
            # Update callback after first task
            if progress_callback:
                try: progress_callback(tasks_completed + 1, tasks_total)
                except: pass
            
            consecutive_failures = 0
            
            for i in range(remaining_iterations):
                # CHECK FOR LOGOUT AT START OF EACH LOOP
                if "login" in page.url:
                    if not resurrect_session():
                        break

                current_completed = tasks_completed + i + 2
                print(f"Loop ke-{i+1} (Total progress: {current_completed}/{tasks_total})")
                page.wait_for_timeout(1000) # Slight delay

                try:
                    # Robust clicking: find element, ensuring it's enabled
                    el = page.get_by_text("Sedang Berlangsung").nth(1)
                    if el.is_visible():
                        el.click()
                        
                        # Wait for Kirim button
                        k_btn = page.get_by_role("button", name="Kirim")
                        if k_btn.is_visible(timeout=2000):
                            k_btn.click()
                            loop_count += 1
                            consecutive_failures = 0 # Reset failure count
                            
                            # CALLBACK HERE for real-time update
                            if progress_callback:
                                try: progress_callback(current_completed, tasks_total)
                                except: pass

                        else:
                             print("Tombol Kirim tidak muncul (mungkin delay)")
                             if "login" in page.url:
                                 resurrect_session()
                    else:
                        if "login" in page.url:
                            resurrect_session()
                        else:
                            print("Elemen utama hidden/hilang")
                            consecutive_failures += 1
                        
                except PlaywrightTimeoutError:
                    if "login" in page.url:
                        resurrect_session()
                    else:
                        print("Elemen utama nggak ketemu (Timeout).")
                        consecutive_failures += 1
                
                # Self-healing: if too many consecutive failures, refresh and trying to recover would be complex here as state is lost
                # Instead, we break early to trigger the outer retry loop in cli.py which is safer
                if consecutive_failures >= 3:
                     print("Terlalu banyak kegagalan berturut-turut. Breaking loop untuk restart.")
                     break

                try:
                    page.get_by_role("button", name="Mengonfirmasi").click(timeout=1500)
                except:
                    pass
        else:
            print(f"All tasks already completed ({tasks_completed}/{tasks_total}). Skipping automation.")
            loop_count = 0
            # Callback even if skipped
            if progress_callback:
                try: progress_callback(tasks_completed, tasks_total)
                except: pass

        print(f"Selesai loop. {loop_count} iterations completed")
        
    except Exception as e:
        print(f"⚠️ Automation loop interrupted: {e}")
        # Detect logout in catch block too
        if "login" in page.url:
            resurrect_session()
        print("Proceeding to scrape data anyway...")

    print(f"Selesai loop. {loop_count} iterations completed")
    
    # Re-scrape progress from page to get final count
    try:
        # Check login before final scrape
        if "login" in page.url:
            resurrect_session()

        # Go to ticket page to be sure
        page.locator(".van-badge__wrapper.van-icon.van-icon-undefined.item-icon.iconfont.icon-ticket").click()
        try_close_popups(page) # Should be available in scope or via import if function
        
        progress_element = page.locator(".van-progress__pivot").first
        progress_text = progress_element.text_content(timeout=5000)
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

    # Final callback
    if progress_callback:
        try: progress_callback(tasks_completed, tasks_total)
        except: pass

    return tasks_completed, tasks_total


def run(playwright: Playwright, phone: str, password: str, headless: bool = False, slow_mo: int = 200, iterations: int = 30, review_text: Optional[str] = None, viewport_name: str = "iPhone 12", timeout: int = 30, sync_only: bool = False, progress_callback=None) -> Tuple[int, int, float, float, float]:
    browser = playwright.chromium.launch(headless=headless, slow_mo=slow_mo)
    
    vp = VIEWPORTS.get(viewport_name, VIEWPORTS["iPhone 12"])
    
    # Check for existing session
    session_path = get_session_path(phone)
    storage_state = session_path if os.path.exists(session_path) else None
    
    if storage_state:
        print(f"Attempting to load session from {storage_state}")
    
    # Create context with storage_state if available
    try:
        context = browser.new_context(viewport=vp, storage_state=storage_state)
    except Exception as e:
        print(f"Failed to load session (corrupt?): {e}")
        # Fallback to no session
        context = browser.new_context(viewport=vp)

    page = context.new_page()

    # Set timeout (convert to ms)
    page.set_default_timeout(timeout * 1000) 

    # OPTIMIZATION: Block heavy resources to save RAM, CPU, and Battery
    def intercept_route(route):
        # Strictly block images, media, and fonts
        # Blocking stylesheets can be risky for selectors but fonts/images/media are safe
        if route.request.resource_type in ["image", "media", "font", "manifest", "other"]:
            route.abort()
        else:
            route.continue_()
    
    page.route("**/*", intercept_route)

    try:
        # ========== LOGIN ==========
        # Login now handles restoration check AND saving to 'context'
        if not login(page, context, phone, password, timeout):
            print("Login failed, aborting run.")
            return 0, iterations, 0.0, 0.0, 0.0

        # ========== PERFORM TASKS ==========
        tasks_completed, tasks_total = 0, iterations
        if not sync_only:
            tasks_completed, tasks_total = perform_tasks(page, context, phone, password, iterations, review_text, progress_callback=progress_callback)
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
        if sync_only:
            # STABLE SYNC: Double-check logic to ensure balance isn't changing
            print("  Performing STABLE SYNC check (Double Scrape)...")
            b1 = scrape_balance(page, timeout)
            
            # Initial wait
            page.wait_for_timeout(5000)
            b2 = scrape_balance(page, timeout)
            
            if abs(b1 - b2) > 0.01:
                print(f"  Balance unstable (diff: {b2-b1}). Waiting for final check...")
                page.wait_for_timeout(5000)
                balance = scrape_balance(page, timeout)
            else:
                print("  Balance stable.")
                balance = b2
        else:
            balance = scrape_balance(page, timeout)
        
        # Return progress with income, withdrawal, and balance
        print(f"Returning final progress: {tasks_completed}/{tasks_total}")
        return tasks_completed, tasks_total, income, withdrawal, balance

    finally:
        context.close()
        browser.close()



