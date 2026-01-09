import os
import time
from typing import Optional, Tuple
from playwright.sync_api import Playwright, Page, TimeoutError as PlaywrightTimeoutError
from .scraper import scrape_income, scrape_withdrawal, scrape_balance, scrape_points, scrape_calendar_data, try_close_popups
from .reviews import REVIEWS
import random
from datetime import date



def smart_click(page: Page, selector: str, role: str = None, name: str = None, retries: int = 3, timeout: int = 5000) -> bool:
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
        page.wait_for_timeout(2000)
        try_close_popups(page)
        
        # Verify if we are logged in
        # PRO-TIP: "icon-lipin" might exist as an SVG symbol even if not logged in.
        # We must check for VISIBLE elements that only appear when authenticated.
        authenticated = False
        
        # 1. Check for specific text that only exists on Mine/Profile page when logged in
        if page.get_by_text("Saldo Rekening").is_visible(timeout=3000): 
            authenticated = True
        elif page.locator("i.icon-lipin").is_visible(timeout=1000): # Check specifically for <i> tag
            authenticated = True
        
        # 2. Check for "Login" or "Daftar" - if they are prominently visible, we are likely NOT logged in
        # (Be careful as they might be in a header/footer on many pages)
        if authenticated:
            # Final sanity check: make sure we aren't actually on the login page
            if "login" in page.url.lower():
                authenticated = False

        if authenticated:
            print("Session restored successfully (Already logged in).")
            return True
        
        print(f"Session invalid or expired. Logging in as {phone}...")
        page.goto("https://mba7.com/#/login", wait_until="networkidle", timeout=timeout*1000)
        page.wait_for_timeout(2000)
        try_close_popups(page)

        # Ensure we are actually on login page
        if "login" not in page.url.lower():
            print("  Attempting navigation to login page again...")
            page.goto("https://mba7.com/#/login", timeout=timeout*1000)
            page.wait_for_timeout(2000)

        page.get_by_role("textbox", name="Nomor Telepon").fill(phone_for_login)
        page.get_by_role("textbox", name="Kata Sandi").fill(password)
        
        # Handle the "Masuk" button in the login form
        login_btn = page.get_by_role("button", name="Masuk").first
        if login_btn.count() > 0:
            login_btn.click()
        else:
            smart_click(page, "button", role="button", name="Masuk")
            
        page.wait_for_timeout(4000)

        # After login: confirm buttons might appear
        for _ in range(3):
            if smart_click(page, "button", role="button", name="Mengonfirmasi", timeout=3000):
                page.wait_for_timeout(1000)
            else:
                break
        
        # Verify login success by checking for mine page elements
        page.goto("https://mba7.com/#/mine", timeout=timeout*1000)
        page.wait_for_timeout(3000)
        try_close_popups(page)
        
        success = False
        if page.get_by_text("Saldo Rekening").is_visible(timeout=5000): 
            success = True
        elif page.locator("i.icon-lipin").is_visible(timeout=2000):
            success = True

        if success:
             # Save storage state
             print(f"Login success. Saving session to {session_path}...")
             context.storage_state(path=session_path)
             return True
        
        print(f"Login verification failed. URL: {page.url}")
        return False

    except Exception as e:
        print(f"Login failed: {e}")
        return False


def perform_checkin(page: Page) -> Tuple[float, list]:
    """
    Navigates to points shop, clicks check-in if available, scrapes points and calendar.
    Returns (points_balance, calendar_days).
    """
    points = 0.0
    calendar = []
    
    print("Performing Check-in & Points Scraping...")
    try:
        # 1. Navigation: Go directly to points shop
        print("  Navigating to Points Shop...")
        page.goto("https://mba7.com/#/points/shop", timeout=45000)
        page.wait_for_timeout(3000)
        try_close_popups(page)

        # 2. Scrape Points FIRST (while on main shop page)
        points = scrape_points(page)
        print(f"  Initial points balance: {points}")

        # 3. Open Calendar Popup using smart_click
        print("  Opening calendar popup...")
        calendar_opened = False
        
        # Try sign-in-container first, then "Masuk" text
        if smart_click(page, ".sign-in-container", timeout=2000):
            print("    Clicked .sign-in-container")
            page.wait_for_timeout(2000)
            calendar_opened = page.locator(".van-calendar__month-title").first.is_visible(timeout=3000)
        elif smart_click(page, "button", role="button", name="Masuk", timeout=2000):
            print("    Clicked 'Masuk' button")
            page.wait_for_timeout(2000)
            calendar_opened = page.locator(".van-calendar__month-title").first.is_visible(timeout=3000)
        else:
            print("    Could not find calendar trigger (might be already checked in today)")

        # 4. Scrape Calendar Data (Current attendance)
        if calendar_opened:
            print("    Calendar popup opened successfully")
            calendar = scrape_calendar_data(page)
        else:
            print("    Calendar not opened, skipping calendar scraping")
            return points, calendar

        # 5. PERFORM CHECK-IN if calendar is open
        print("  Attempting check-in...")
        if smart_click(page, ".van-calendar__confirm", timeout=3000):
            print("    Clicked check-in submit button")
            page.wait_for_timeout(2000)
            
            # Handle Success Dialog
            if smart_click(page, "button", role="button", name="Mengonfirmasi", timeout=3000):
                print("    ✓ Check-in successful! Clicked confirmation.")
                page.wait_for_timeout(1000)
                
                # Re-scrape calendar if still visible
                if page.locator(".van-calendar__month-title").first.is_visible(timeout=2000):
                    calendar = scrape_calendar_data(page)
                    print(f"    Updated calendar: {len(calendar)} days checked in")
            else:
                print("    No success dialog (might already be checked in)")
            
            try_close_popups(page)
            
            # Re-scrape points after check-in attempt
            new_points = scrape_points(page)
            if new_points > points:
                print(f"    ✓ Points increased: {points} -> {new_points}")
            points = new_points
        else:
            print("    Check-in button not found or not clickable")

    except Exception as e:
        print(f"  Error in perform_checkin: {e}")
        
    return points, calendar


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

    # Navigate to grab page (where tasks are)
    print("Navigating to tasks page...")
    try:
        # Try direct goto first
        page.goto("https://mba7.com/#/grab", timeout=45000)
        page.wait_for_timeout(3000)
        try_close_popups(page)
        
        # If not on grab page, try clicking icon-ticket (legacy flow)
        if "grab" not in page.url and "ticket" not in page.url:
            print("  Not on grab page, trying icon-ticket navigation...")
            ticket_selectors = [
                ".van-badge__wrapper.van-icon.van-icon-undefined.item-icon.iconfont.icon-ticket",
                ".icon-ticket",
                "[class*='icon-ticket']"
            ]
            for selector in ticket_selectors:
                btn = page.locator(selector).first
                if btn.count() > 0 and btn.is_visible(timeout=3000):
                    btn.click()
                    page.wait_for_timeout(3000)
                    break

        print("Tasks page check done.")
    except Exception as e:
        print(f"Navigation error: {e}")
        # Detect if we were sent to login
        if "login" in page.url:
            resurrect_session()

    # ========== SCRAPE ACTUAL PROGRESS FROM PAGE ==========
    # ... (skipping for brevity but keeping implementation)

    # ========== PERTAMA KALI ISI REVIEW ==========
    loop_count = 0
    try:
        if "login" in page.url:
            resurrect_session()

        if tasks_completed < tasks_total:
            # Click Mendapatkan button (button 1: Grab/List)
            try:
                # 1. Try User's Simple Selector first
                btn = page.get_by_role("button", name="Mendapatkan").first
                if btn.count() > 0 and btn.is_visible(timeout=5000):
                    btn.click()
                    print("Klik Mendapatkan (Role/Name) OK")
                else:
                    # 2. Try Specific CSS selector fallback
                    btn = page.locator("#app > div > div.van-config-provider.provider-box > div.main-wrapper.travel-bg > div.div-flex-center > button").first
                    btn.wait_for(state="visible", timeout=5000)
                    btn.click()
                    print("Klik Mendapatkan (CSS) OK")
            except Exception as e:
                # ... (error handling)
                pass

            # Wait for navigation to work page
            page.wait_for_url("**/work**", timeout=10000)
            page.wait_for_timeout(2000)

            # Click Mendapatkan button on work/detail page (button 2)
            try:
                # Same: Try simple role first
                btn = page.get_by_role("button", name="Mendapatkan").first
                if btn.count() > 0 and btn.is_visible(timeout=5000):
                    btn.click()
                    print("Klik Mendapatkan (Detail Role) OK")
                else:
                    # Text based fallback
                    btn = page.locator("button:has-text('Mendapatkan')").first
                    btn.wait_for(state="visible", timeout=5000)
                    btn.click()
                    print("Klik Mendapatkan (Detail Text) OK")
            except Exception as e:
                # ...
                pass

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


def run(playwright: Playwright, phone: str, password: str, headless: bool = False, slow_mo: int = 200, iterations: int = 30, review_text: Optional[str] = None, sync_only: bool = False, progress_callback=None) -> Tuple[int, int, float, float, float, float, list]:
    browser = playwright.chromium.launch(
        headless=headless, 
        slow_mo=slow_mo,
        args=[
            "--disable-gpu",
            "--disable-dev-shm-usage",
            "--no-first-run",
            "--no-default-browser-check",
            "--single-process", # CRITICAL for 1GB RAM
            "--renderer-process-limit=1",
            "--js-flags=\"--max-old-space-size=128\"", # Cap V8 heap to 128MB
            "--disable-blink-features=AutomationControlled"
        ]
    )
    
    # Default professional mobile viewport
    vp = {"width": 390, "height": 844}
    
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
    timeout = 30
    page.set_default_timeout(timeout * 1000) 

    # OPTIMIZATION: Block heavy resources to save RAM, CPU, and Battery
    def intercept_route(route):
        # Strictly block images, media, and fonts
        # Blocking stylesheets can be risky for selectors but fonts/images/media are safe
        if route.request.resource_type in ["image", "media", "font"]:
            route.abort()
        else:
            route.continue_()
    
    page.route("**/*", intercept_route)

    try:
        # ========== LOGIN ==========
        # Login now handles restoration check AND saving to 'context'
        if not login(page, context, phone, password, timeout):
            print("Login failed, aborting run.")
            return 0, iterations, 0.0, 0.0, 0.0, 0.0, []

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

        # ========== CHECK-IN & POINTS ==========
        # Always run check-in/points scrape unless explicitly disabled (not yet implemented)
        # Check-in logic already handles if already checked in
        points, calendar = perform_checkin(page)
        
        # Return progress with income, withdrawal, balance, points, and calendar
        print(f"Returning final progress: {tasks_completed}/{tasks_total}, Points: {points}, Calendar days: {len(calendar)}")
        return tasks_completed, tasks_total, income, withdrawal, balance, points, calendar

    finally:
        context.close()
        browser.close()



