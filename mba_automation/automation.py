import os
import sys
import time
from typing import Optional, Tuple
from playwright.sync_api import Playwright, Page, TimeoutError as PlaywrightTimeoutError
from .scraper import scrape_income, scrape_withdrawal, scrape_balance, scrape_points, scrape_calendar_data, try_close_popups
from .reviews import REVIEWS
import random
from datetime import date

# Force unbuffered output for realtime logging
def log(msg):
    print(msg, flush=True)



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
    """Robust login with retries and better verification."""
    session_path = get_session_path(phone)

    # Helper to check if logged in
    def check_is_logged_in():
        try:
            # 1. Check URL
            if "login" in page.url.lower(): return False
            
            # 2. Check for "Saldo Rekening" or Profile Icon
            # Increased timeout to 8s for slow VPS
            if page.get_by_text("Saldo Rekening").is_visible(timeout=8000): return True
            if page.locator("i.icon-lipin").is_visible(timeout=3000): return True
            
            return False
        except: return False

    try:
        phone_for_login = phone[2:] if phone.startswith('62') else phone
        
        # 1. TRY RESTORE
        if os.path.exists(session_path):
            log(f"Restoring session for {phone}...")
            try:
                page.goto("https://mba7.com/#/mine", wait_until="domcontentloaded", timeout=timeout*1000)
                try_close_popups(page)
                if check_is_logged_in():
                    log("Session restored successfully.")
                    return True
                log("Session expired or invalid.")
            except Exception as e:
                log(f"Session restore failed: {e}")

        # 2. PERFORM LOGIN
        log(f"Logging in as {phone}...")
        page.goto("https://mba7.com/#/login", wait_until="domcontentloaded", timeout=timeout*1000)
        page.wait_for_timeout(1000)
        try_close_popups(page)

        # Fill credentials
        page.get_by_role("textbox", name="Nomor Telepon").fill(phone_for_login)
        page.get_by_role("textbox", name="Kata Sandi").fill(password)
        
        # Click Login
        login_btn = page.get_by_role("button", name="Masuk").first
        if login_btn.count() > 0:
            login_btn.click()
        else:
            smart_click(page, "button", role="button", name="Masuk")
            
        
        page.wait_for_timeout(3000) # Wait for network/transition

        # Handle post-login popups/confirmations
        smart_click(page, "button", role="button", name="Mengonfirmasi", timeout=3000)
        
        # Verify
        page.goto("https://mba7.com/#/mine", timeout=timeout*1000)
        page.wait_for_timeout(3000)
        try_close_popups(page)

        if check_is_logged_in():
             log(f"Login success. Saving session...")
             context.storage_state(path=session_path)
             return True
        
        # Fail
        log(f"Login verification failed. URL: {page.url}")
        # Capture screenshot for debug if possible (removed for production safety/size)
        return False

    except Exception as e:
        log(f"Login CRITICAL FAILURE: {e}")
        return False


def perform_checkin(page: Page) -> Tuple[float, list]:
    """
    Navigates to points shop, clicks check-in if available, scrapes points and calendar.
    Returns (points_balance, calendar_days).
    """
    points = 0.0
    calendar = []
    
    log("Performing Check-in & Points Scraping...")
    try:
        # 1. Navigation: Go directly to points shop
        log("  Navigating to Points Shop...")
        page.goto("https://mba7.com/#/points/shop", timeout=45000)
        page.wait_for_timeout(2000)
        try_close_popups(page)

        # 2. Scrape Points FIRST (while on main shop page)
        points = scrape_points(page)
        log(f"  Initial points balance: {points}")

        # 3. Open Calendar Popup using smart_click
        log("  Opening calendar popup...")
        calendar_opened = False
        
        # Try sign-in-container first, then "Masuk" text
        if smart_click(page, ".sign-in-container", timeout=2000):
            log("    Clicked .sign-in-container")
            page.wait_for_timeout(2000)
            calendar_opened = page.locator(".van-calendar__month-title").first.is_visible(timeout=3000)
        elif smart_click(page, "button", role="button", name="Masuk", timeout=2000):
            log("    Clicked 'Masuk' button")
            page.wait_for_timeout(2000)
            calendar_opened = page.locator(".van-calendar__month-title").first.is_visible(timeout=3000)
        else:
            log("    Could not find calendar trigger (might be already checked in today)")

        # 4. Scrape Calendar Data (Current attendance)
        if calendar_opened:
            log("    Calendar popup opened successfully")
            calendar = scrape_calendar_data(page)
        else:
            log("    Calendar not opened, skipping calendar scraping")
            return points, calendar

        # 5. PERFORM CHECK-IN if calendar is open
        log("  Attempting check-in...")
        if smart_click(page, ".van-calendar__confirm", timeout=3000):
            log("    Clicked check-in submit button")
            page.wait_for_timeout(2000)
            
            # Handle Success Dialog
            if smart_click(page, "button", role="button", name="Mengonfirmasi", timeout=3000):
                log("    ✓ Check-in successful! Clicked confirmation.")
                page.wait_for_timeout(1000)
                
                # Re-scrape calendar if still visible
                if page.locator(".van-calendar__month-title").first.is_visible(timeout=2000):
                    calendar = scrape_calendar_data(page)
                    log(f"    Updated calendar: {len(calendar)} days checked in")
            else:
                log("    No success dialog (might already be checked in)")
            
            try_close_popups(page)
            
            # Re-scrape points after check-in attempt
            new_points = scrape_points(page)
            if new_points > points:
                log(f"    ✓ Points increased: {points} -> {new_points}")
            points = new_points
        else:
            log("    Check-in button not found or not clickable")

    except Exception as e:
        log(f"  Error in perform_checkin: {e}")
        
    return points, calendar


def scrape_task_progress(page: Page) -> Tuple[int, int]:
    """
    Robustly scrapes the current task progress (e.g., '34/60') from the page.
    Returns (completed, total). Returns (0, 0) if not found.
    """
    try:
        # Progress is usually in .van-progress__pivot
        # We try explicit selectors first
        # OPTIMIZED: Reduced timeout from 2000 to 500 for speedier checks
        progress_element = page.locator(".van-progress__pivot").first
        
        if progress_element.count() > 0 and progress_element.is_visible(timeout=500):
            text = progress_element.text_content(timeout=500)
            if text and "/" in text:
                parts = text.split("/")
                completed = int(parts[0].strip())
                total = int(parts[1].strip())
                return completed, total
        
        # Fallback: Check for text "xx/xx" anywhere if pivot is hidden/loading
        # This helps when the UI is slightly different or lagging
        # Regex search is expensive so we do a quick check
        # But for safety, return 0,0 quickly if not found to avoid drag
        return 0, 0

    except Exception:
        pass
    
    return 0, 0


def perform_tasks(page: Page, context, phone: str, password: str, iterations: int, review_text: Optional[str] = None, progress_callback=None) -> Tuple[int, int]:
    """
    Executes the main automation loop using STRICT STATE VERIFICATION.
    It does NOT trust local counters. It scrapes the page to know the truth.
    """
    
    def resurrect_session():
        """Helper to re-login if session is lost."""
        log("⚠️ Session lost! Attempting to resurrect...")
        if login(page, context, phone, password):
            log("🚀 Session resurrected! Navigating back to grab...")
            page.goto("https://mba7.com/#/grab", timeout=45000)
            page.wait_for_timeout(3000)
            try_close_popups(page)
            return True
        return False

    # 1. NAVIGATION
    log("Navigating to tasks page...")
    try:
        page.goto("https://mba7.com/#/grab", timeout=45000)
        page.wait_for_timeout(3000)
        try_close_popups(page)
        
        if "grab" not in page.url and "ticket" not in page.url:
            log("  Navigating via button...")
            page.locator(".icon-ticket").first.click()
            page.wait_for_timeout(3000)
    except Exception as e:
         log(f"Navigation error: {e}")
         if "login" in page.url: resurrect_session()

    # 2. INITIAL STATE CHECK
    current_completed, current_total = scrape_task_progress(page)
    
    # If the page total is bigger than our config, respect the page (e.g. E3 60 tasks)
    if current_total > iterations:
        iterations = current_total
        log(f"Adjusting target iterations to {iterations} based on page.")

    log(f"Initial State: {current_completed}/{iterations}")

    # 3. TASK LOOP
    # We loop until the page SAYS we are done.
    consecutive_errors = 0
    max_consecutive_errors = 5
    
    # Pre-calculate selectors for speed
    loc_pivot = page.locator(".van-progress__pivot").first
    loc_confirm = page.get_by_role("button", name="Mengonfirmasi")
    loc_kirim = page.get_by_role("button", name="Kirim")
    loc_task_active = page.locator(".task-item.active").first
    
    while current_completed < iterations:
        # Callback Update
        if progress_callback:
            try: progress_callback(current_completed, iterations)
            except: pass

        # Check for logout rarely (only on error or explicitly)
        if "login" in page.url:
            if not resurrect_session():
                log("Could not resurrect session. Stopping.")
                break
                
        log(f"⚡ FAST EXEC: Task {current_completed + 1}/{iterations}...")

        task_success = False

        try:
            # A. FAST ACTION
            # Prioritize finding the active task or Kirim button instantly
            if loc_kirim.is_visible(timeout=500):
                 loc_kirim.click()
            elif loc_task_active.is_visible(timeout=500):
                 loc_task_active.click()
                 # Immediate check for Kirim after click
                 if loc_kirim.is_visible(timeout=1000):
                     loc_kirim.click()
            else:
                 # Fallback to slower text search
                 log("  CSS failed, trying text search...")
                 page.get_by_text("Sedang Berlangsung").first.click(timeout=1000)
                 if loc_kirim.is_visible(timeout=1000):
                     loc_kirim.click()

            # B. FAST CONFIRM
            # Wait for success dialog max 2s
            if loc_confirm.is_visible(timeout=2000):
                loc_confirm.click()
                task_success = True
                consecutive_errors = 0 
            else:
                log("  ⚠ No confirm dialog. Might have missed or failed.")
                consecutive_errors += 1

        except Exception as e:
            log(f"  Error: {e}")
            consecutive_errors += 1

        # C. HYBRID STATE CHECK
        # To be fast, we assume success if we clicked confirm.
        # But we verify every step to be safe, just with very low timeout.
        
        # Short sleep only if we suspect lag, otherwise GO GO GO
        # page.wait_for_timeout(100) 
        
        try:
            # Super fast check
            if loc_pivot.is_visible(timeout=500):
                txt = loc_pivot.text_content(timeout=100)
                if txt and "/" in txt:
                    parts = txt.split("/")
                    new_completed = int(parts[0].strip())
                    new_total = int(parts[1].strip())
                    
                    if new_completed > current_completed:
                         current_completed = new_completed
                         if new_total > iterations: iterations = new_total
                         log(f"  ✓ Up: {current_completed}/{iterations}")
                         continue # NEXT LOOP IMMEDIATELY
        except: pass
        
        # If we didn't confirm via scrape, check if we should verify harder or just retry
        if task_success:
             # We clicked confirm, so we 'probably' succeeded. 
             # Optimistically increment for the log, but scraper will catch up next loop.
             pass 
        else:
             if consecutive_errors > max_consecutive_errors:
                 log("  STALLED. Reloading...")
                 page.reload()
                 page.wait_for_timeout(3000)
                 consecutive_errors = 0
                 # Re-sync
                 c, t = scrape_task_progress(page)
                 if c > 0: current_completed = c

    
    log(f"Loop finished. Final: {current_completed}/{iterations}")
    return current_completed, iterations


def run(playwright: Playwright, phone: str, password: str, headless: bool = False, slow_mo: int = 200, iterations: int = 30, review_text: Optional[str] = None, sync_only: bool = False, progress_callback=None) -> Tuple[int, int, float, float, float, float, list]:
    browser = playwright.chromium.launch(
        headless=headless, 
        slow_mo=50,
        args=[
            "--disable-gpu",
            "--disable-dev-shm-usage",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-blink-features=AutomationControlled"
        ]
    )
    
    # Default professional mobile viewport
    vp = {"width": 390, "height": 844}
    
    # Check for existing session
    session_path = get_session_path(phone)
    storage_state = session_path if os.path.exists(session_path) else None
    
    if storage_state:
        log(f"Attempting to load session from {storage_state}")
    
    # Create context with storage_state if available
    try:
        context = browser.new_context(viewport=vp, storage_state=storage_state)
    except Exception as e:
        log(f"Failed to load session (corrupt?): {e}")
        # Fallback to no session
        context = browser.new_context(viewport=vp)

    page = context.new_page()

    # Set timeout (convert to ms)
    # Set timeout (convert to ms) - Reduced to prevent zombie processes
    timeout = 25
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
        if not login(page, context, phone, password, 45): # Increased login timeout slightly for safety against slow network
            log("Login failed, aborting run.")
            return 0, iterations, 0.0, 0.0, 0.0, 0.0, []

        # ========== PERFORM TASKS ==========
        tasks_completed, tasks_total = 0, iterations
        if not sync_only:
            tasks_completed, tasks_total = perform_tasks(page, context, phone, password, iterations, review_text, progress_callback=progress_callback)
        else:
            log("Sync only mode: checking current progress...")
            try:
                # Navigate to grab page where progress is shown
                log("  Navigating to /grab page...")
                page.goto("https://mba7.com/#/grab", timeout=timeout*1000)
                page.wait_for_timeout(4000)
                from .scraper import try_close_popups
                try_close_popups(page)
                page.wait_for_timeout(2000)
                
                # Log current URL to verify navigation
                log(f"  Current URL: {page.url}")
                
                # Look for ALL progress elements and log them
                progress_elements = page.locator(".van-progress__pivot")
                count = progress_elements.count()
                log(f"  Found {count} progress elements")
                
                # Try each element to find one with X/Y format
                for i in range(count):
                    try:
                        elem = progress_elements.nth(i)
                        text = elem.text_content(timeout=2000)
                        log(f"    Element {i}: '{text}'")
                        if text and "/" in text:
                            parts = text.split("/")
                            tasks_completed = int(parts[0].strip())
                            tasks_total = int(parts[1].strip())
                            log(f"  ✓ Current progress detected: {tasks_completed}/{tasks_total}")
                            break
                    except Exception as e:
                        log(f"    Element {i}: error - {e}")
                else:
                    log("  ✗ No valid progress element found")
            except Exception as e:
                log(f"  ✗ Could not read progress during sync: {e}")

        # ========== SCRAPE DATA ==========
        log("Scraping income from deposit records...")
        income = scrape_income(page, timeout)
        
        log("Scraping withdrawal from withdrawal records...")
        withdrawal = scrape_withdrawal(page, timeout)

        log("Scraping balance from profile...")
        if sync_only:
            # STABLE SYNC: Double-check logic to ensure balance isn't changing
            log("  Performing STABLE SYNC check (Double Scrape)...")
            b1 = scrape_balance(page, timeout)
            
            # Initial wait
            page.wait_for_timeout(5000)
            b2 = scrape_balance(page, timeout)
            
            if abs(b1 - b2) > 0.01:
                log(f"  Balance unstable (diff: {b2-b1}). Waiting for final check...")
                page.wait_for_timeout(5000)
                balance = scrape_balance(page, timeout)
            else:
                log("  Balance stable.")
                balance = b2
        else:
            balance = scrape_balance(page, timeout)

        # ========== CHECK-IN & POINTS ==========
        # Always run check-in/points scrape unless explicitly disabled (not yet implemented)
        # Check-in logic already handles if already checked in
        points, calendar = perform_checkin(page)
        
        # Return progress with income, withdrawal, balance, points, and calendar
        log(f"Returning final progress: {tasks_completed}/{tasks_total}, Points: {points}, Calendar days: {len(calendar)}")
        return tasks_completed, tasks_total, income, withdrawal, balance, points, calendar

    finally:
        context.close()
        browser.close()



