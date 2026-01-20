import os
import sys
import time
from typing import Optional, Tuple
from playwright.sync_api import Playwright, Page, TimeoutError as PlaywrightTimeoutError
from .scraper import scrape_income, scrape_withdrawal, scrape_balance, scrape_points, scrape_calendar_data, try_close_popups, scrape_dana_amal_records
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
                page.wait_for_timeout(3000)  # Give page time to load session
                try_close_popups(page)
                if check_is_logged_in():
                    log("Session restored successfully.")
                    return True
                log("Session expired or invalid.")
            except Exception as e:
                log(f"Session restore failed: {e}")

        # 2. PERFORM LOGIN
        log(f"Logging in as {phone}...")
        
        # Retry logic for login page navigation
        for attempt in range(3):
            try:
                page.goto("https://mba7.com/#/login", wait_until="domcontentloaded", timeout=timeout*1000)
                page.wait_for_timeout(3000)  # Increased wait for page to fully render
                try_close_popups(page)
                
                # Wait explicitly for phone field to be ready
                phone_field = page.get_by_role("textbox", name="Nomor Telepon")
                phone_field.wait_for(state="visible", timeout=15000)
                break
            except Exception as e:
                log(f"Login page load attempt {attempt+1} failed: {e}")
                if attempt == 2:
                    raise
                page.wait_for_timeout(2000)

        # Fill credentials with explicit waits
        try:
            phone_field = page.get_by_role("textbox", name="Nomor Telepon")
            phone_field.wait_for(state="visible", timeout=10000)
            phone_field.click()
            phone_field.fill(phone_for_login)
            log(f"  Filled phone: {phone_for_login}")
        except Exception as e:
            log(f"  Phone field fill failed: {e}")
            # Fallback: try input[type='tel'] or first input
            try:
                inputs = page.locator("input").all()
                if len(inputs) >= 1:
                    inputs[0].fill(phone_for_login)
                    log("  Filled phone via fallback selector")
            except:
                raise Exception("Could not find phone field")
        
        page.wait_for_timeout(500)
        
        try:
            pwd_field = page.get_by_role("textbox", name="Kata Sandi")
            pwd_field.wait_for(state="visible", timeout=10000)
            pwd_field.click()
            pwd_field.fill(password)
            log(f"  Filled password")
        except Exception as e:
            log(f"  Password field fill failed: {e}")
            # Fallback: try input[type='password']
            try:
                pwd_input = page.locator("input[type='password']").first
                pwd_input.fill(password)
                log("  Filled password via fallback selector")
            except:
                raise Exception("Could not find password field")
        
        page.wait_for_timeout(500)
        
        # Click Login
        login_btn = page.get_by_role("button", name="Masuk").first
        if login_btn.count() > 0:
            login_btn.click()
            log("  Clicked login button")
        else:
            smart_click(page, "button", role="button", name="Masuk")
            
        page.wait_for_timeout(5000)  # Increased wait for network/transition

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


def wait_for_stable_and_confirm_order(page: Page, max_wait: int = 30) -> bool:
    """
    Waits for the server to become stable (image appears) and handles 'konfirmasi order' if needed.
    Returns True if stable, False if timeout.
    """
    log("  Waiting for server to stabilize...")
    
    # Wait for image OR any product image element to appear (indicates stable)
    image_selectors = [
        "img[src*='product']",
        "img[src*='hotel']",
        "img[src*='travel']",
        ".van-image img",
        ".product-image img",
        "img.van-image__img",
    ]
    
    start_time = time.time()
    stable = False
    
    while time.time() - start_time < max_wait:
        # Check for konfirmasi order button and click it
        try:
            konfirm_btn = page.get_by_role("button", name="Konfirmasi")
            if konfirm_btn.count() > 0 and konfirm_btn.first.is_visible(timeout=500):
                log("  🔄 Found 'Konfirmasi' button, clicking...")
                konfirm_btn.first.click()
                page.wait_for_timeout(2000)
                continue
        except:
            pass
        
        # Also check "Mengonfirmasi" button
        try:
            mengonfirm_btn = page.get_by_role("button", name="Mengonfirmasi")
            if mengonfirm_btn.count() > 0 and mengonfirm_btn.first.is_visible(timeout=500):
                log("  🔄 Found 'Mengonfirmasi' button, clicking...")
                mengonfirm_btn.first.click()
                page.wait_for_timeout(2000)
                continue
        except:
            pass
        
        # Check for image (stable indicator)
        for selector in image_selectors:
            try:
                img = page.locator(selector).first
                if img.count() > 0 and img.is_visible(timeout=500):
                    log("  ✅ Server stable (image visible)")
                    stable = True
                    break
            except:
                continue
        
        if stable:
            break
            
        # Also check for Kirim button as alternative stability indicator
        try:
            kirim = page.get_by_role("button", name="Kirim")
            if kirim.count() > 0 and kirim.is_visible(timeout=500):
                log("  ✅ Server stable (Kirim button visible)")
                stable = True
                break
        except:
            pass
            
        page.wait_for_timeout(1000)
    
    if not stable:
        log(f"  ⚠️ Server not stable after {max_wait}s")
    
    return stable


def perform_tasks(page: Page, context, phone: str, password: str, iterations: int, review_text: Optional[str] = None, progress_callback=None) -> Tuple[int, int]:
    """
    Executes the main automation loop: checking progress, submitting reviews.
    Returns (tasks_completed, tasks_total).
    """
    tasks_completed = 0
    tasks_total = iterations
    loop_count = 0  # Track actual completed iterations in this session

    # DEBUG: Log what we received
    log(f"🔍 [DEBUG] perform_tasks called with iterations={iterations}")

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

    # Navigate to grab page (where tasks are)
    log("Navigating to tasks page...")
    try:
        # Try direct goto first
        page.goto("https://mba7.com/#/grab", timeout=45000)
        page.wait_for_timeout(3000)
        try_close_popups(page)
        
        # If not on grab page, try clicking icon-ticket (legacy flow)
        if "grab" not in page.url and "ticket" not in page.url:
            log("  Not on grab page, trying icon-ticket navigation...")
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

        log("Tasks page check done.")
    except Exception as e:
        log(f"Navigation error: {e}")
        # Detect if we were sent to login
        if "login" in page.url:
            resurrect_session()

    # ========== SCRAPE ACTUAL PROGRESS FROM PAGE ==========
    # ========== SCRAPE ACTUAL PROGRESS FROM PAGE ==========
    try:
        # Check if we need to login
        if "login" in page.url:
            resurrect_session()
            
        progress_element = page.locator(".van-progress__pivot").first
        if progress_element.count() > 0 and progress_element.is_visible(timeout=3000):
            progress_text = progress_element.text_content(timeout=1000)
            log(f"🔍 [DEBUG] Initial progress from page: '{progress_text}'")
            if progress_text and "/" in progress_text:
                parts = progress_text.split("/")
                initial_completed = int(parts[0].strip())
                scraped_total = int(parts[1].strip())
                
                log(f"🔍 [DEBUG] Parsed: completed={initial_completed}, scraped_total={scraped_total}, current tasks_total={tasks_total}")
                
                # Use higher of configured or scraped total (handles E3=60 correctly)
                if scraped_total > tasks_total:
                    tasks_total = scraped_total
                    log(f"🔍 [DEBUG] Updated tasks_total from page: {tasks_total}")
                elif scraped_total < tasks_total:
                    # FIX: Do NOT downgrade tasks_total if configured is higher!
                    log(f"🔍 [DEBUG] Scraped ({scraped_total}) < Configured ({tasks_total}). IGNORING scraped value to ensure full run.")
                    pass
                
                if initial_completed > tasks_completed:
                    tasks_completed = initial_completed
                    log(f"Resuming from {tasks_completed}/{tasks_total}")
        else:
            log(f"🔍 [DEBUG] Progress element not found or not visible!")
    except Exception as e:
        log(f"Initial progress scrape failed (assuming 0): {e}")

    # ========== PERTAMA KALI ISI REVIEW ==========
    loop_count = 0
    try:
        if "login" in page.url:
            resurrect_session()

        # ALWAYS TRY TO RUN - removed check for tasks_completed < tasks_total
        # This allows manual runs even when tasks appear complete
        if True:  # Was: if tasks_completed < tasks_total:
            # Click Mendapatkan button (button 1: Grab/List)
            try:
                # 1. Try User's Simple Selector first
                btn = page.get_by_role("button", name="Mendapatkan").first
                if btn.count() > 0 and btn.is_visible(timeout=5000):
                    btn.click()
                    log("Klik Mendapatkan (Role/Name) OK")
                else:
                    # 2. Try Specific CSS selector fallback
                    btn = page.locator("#app > div > div.van-config-provider.provider-box > div.main-wrapper.travel-bg > div.div-flex-center > button").first
                    btn.wait_for(state="visible", timeout=5000)
                    btn.click()
                    log("Klik Mendapatkan (CSS) OK")
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
                    log("Klik Mendapatkan (Detail Role) OK")
                else:
                    # Text based fallback
                    btn = page.locator("button:has-text('Mendapatkan')").first
                    btn.wait_for(state="visible", timeout=5000)
                    btn.click()
                    log("Klik Mendapatkan (Detail Text) OK")
            except Exception as e:
                # ...
                pass

            try:
                page.get_by_text("Sedang Berlangsung").nth(1).click()
            except PlaywrightTimeoutError:
                log("'Sedang Berlangsung' ke-2 nggak ketemu.")
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
                    log(f"Using daily consistent review: {text_to_fill}")
                
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
            log(f"🔍 [DEBUG] Loop calculation: tasks_total={tasks_total}, tasks_completed={tasks_completed}, remaining_iterations={remaining_iterations}")
            log(f"Tasks completed: {tasks_completed + 1}/{tasks_total}. Remaining loops: {remaining_iterations}")
            
            loop_count = 1 # We already did one
            tasks_completed += 1  # IMPORTANT: Accumulate from first task
            
            # Update callback after first task
            if progress_callback:
                try: progress_callback(tasks_completed, tasks_total)
                except: pass
            
            consecutive_failures = 0
            
            for i in range(remaining_iterations):
                # CHECK FOR LOGOUT AT START OF EACH LOOP
                if "login" in page.url:
                    if not resurrect_session():
                        break

                log(f"Loop ke-{i+2} (Total progress: {tasks_completed}/{tasks_total})")
                
                page.wait_for_timeout(500)  # Slightly longer delay for stability

                try:
                    # APPROACH 1: Click "Sedang Berlangsung" then "Kirim"
                    clicked_task = False
                    
                    # Try multiple ways to click task
                    task_selectors = [
                        ("get_by_text", "Sedang Berlangsung", 1),
                        ("get_by_text", "Sedang Berlangsung", 0),
                        ("locator", ".van-cell:has-text('Sedang Berlangsung')", 0),
                        ("locator", "[class*='task-item']", 0),
                    ]
                    
                    for sel_type, sel_val, idx in task_selectors:
                        try:
                            if sel_type == "get_by_text":
                                el = page.get_by_text(sel_val).nth(idx)
                            else:
                                el = page.locator(sel_val).nth(idx)
                            
                            if el.is_visible(timeout=1000):
                                el.click(force=True)
                                clicked_task = True
                                page.wait_for_timeout(800)
                                break
                        except:
                            continue
                    
                    # If couldn't click task, try direct Kirim click
                    if not clicked_task:
                        log("  Could not find task item, trying direct Kirim button...")
                    
                    # NEW: Wait for server to stabilize first
                    if not wait_for_stable_and_confirm_order(page, max_wait=15):
                        log("  Server not stable, trying to continue anyway...")
                    
                    # APPROACH 2: Find and click Kirim button
                    k_btn = page.get_by_role("button", name="Kirim")
                    
                    # Wait up to 5 seconds for Kirim to appear (increased)
                    kirim_visible = False
                    for _ in range(10):
                        if k_btn.is_visible(timeout=500):
                            kirim_visible = True
                            break
                        
                        # Check for any confirmation dialogs while waiting
                        try:
                            konfirm = page.get_by_role("button", name="Konfirmasi")
                            if konfirm.count() > 0 and konfirm.first.is_visible(timeout=200):
                                konfirm.first.click()
                                log("  Clicked Konfirmasi while waiting for Kirim")
                                page.wait_for_timeout(1000)
                        except:
                            pass
                        
                        page.wait_for_timeout(500)
                    
                    if kirim_visible:
                        k_btn.click(force=True)
                        loop_count += 1
                        tasks_completed += 1
                        consecutive_failures = 0
                        
                        if progress_callback:
                            try: progress_callback(tasks_completed, tasks_total)
                            except: pass
                        
                        log(f"✓ Task {tasks_completed}/{tasks_total} completed")
                        
                        # Click confirm if appears
                        try:
                            page.get_by_role("button", name="Mengonfirmasi").click(timeout=2000)
                        except:
                            pass
                    else:
                        log("  Tombol Kirim tidak muncul")
                        consecutive_failures += 1
                        
                        # Check if login lost
                        if "login" in page.url:
                            if not resurrect_session():
                                break
                        
                        # APPROACH 3: Try JS injection to find and click
                        try:
                            result = page.evaluate("""
                                () => {
                                    const btns = document.querySelectorAll('button');
                                    for (let btn of btns) {
                                        if (btn.textContent.includes('Kirim') && getComputedStyle(btn).display !== 'none') {
                                            btn.click();
                                            return 'clicked';
                                        }
                                    }
                                    return 'not_found';
                                }
                            """)
                            if result == 'clicked':
                                log("  JS injection click successful!")
                                loop_count += 1
                                tasks_completed += 1
                                consecutive_failures = 0
                                if progress_callback:
                                    try: progress_callback(tasks_completed, tasks_total)
                                    except: pass
                        except Exception as js_err:
                            log(f"  JS injection failed: {js_err}")
                        
                except PlaywrightTimeoutError:
                    log("Elemen utama nggak ketemu (Timeout).")
                    consecutive_failures += 1
                    if "login" in page.url:
                        resurrect_session()
                except Exception as e:
                    log(f"Loop error: {e}")
                    consecutive_failures += 1
                
                # Self-healing: if 4+ consecutive failures, try navigating back to /grab
                if consecutive_failures >= 4:
                    log("⚠️ Too many failures, navigating back to /grab...")
                    try:
                        page.goto("https://mba7.com/#/grab", timeout=30000)
                        page.wait_for_timeout(3000)
                        try_close_popups(page)
                        
                        # Click Mendapatkan again to restart flow
                        btn = page.get_by_role("button", name="Mendapatkan").first
                        if btn.count() > 0 and btn.is_visible(timeout=3000):
                            btn.click()
                            page.wait_for_timeout(2000)
                            log("  Re-clicked Mendapatkan, continuing...")
                        
                        consecutive_failures = 0
                    except Exception as nav_err:
                        log(f"  Navigation recovery failed: {nav_err}")
                        if consecutive_failures >= 6:
                            log("  Breaking loop after 6 consecutive failures")
                            break

                # Try to click Mengonfirmasi at end of each loop
                try:
                    page.get_by_role("button", name="Mengonfirmasi").click(timeout=1000)
                except:
                    pass
        else:
            log(f"All tasks already completed ({tasks_completed}/{tasks_total}). Skipping automation.")
            # Callback even if skipped
            if progress_callback:
                try: progress_callback(tasks_completed, tasks_total)
                except: pass

        log(f"Selesai loop. {loop_count} iterations completed, total: {tasks_completed}/{tasks_total}")
        
    except Exception as e:
        log(f"⚠️ Automation loop interrupted: {e}")
        # Detect logout in catch block too
        if "login" in page.url:
            resurrect_session()
        log("Proceeding to scrape data anyway...")

    log(f"Selesai loop. {loop_count} iterations completed, accumulated: {tasks_completed}/{tasks_total}")
    
    # Re-scrape progress from page to get final count
    scraped_progress = None
    try:
        # Check login before final scrape
        if "login" in page.url:
            resurrect_session()

        # Try direct navigation instead of clicking icon
        page.goto("https://mba7.com/#/ticket", timeout=30000)
        page.wait_for_timeout(3000)
        try_close_popups(page)
        
        progress_element = page.locator(".van-progress__pivot").first
        if progress_element.count() > 0:
            progress_text = progress_element.text_content(timeout=5000)
            log(f"Final progress from page: {progress_text}")
            
            if progress_text and "/" in progress_text:
                parts = progress_text.split("/")
                scraped_completed = int(parts[0].strip())
                scraped_total = int(parts[1].strip())
                log(f"Parsed final progress: {scraped_completed}/{scraped_total}")
                
                # Use the HIGHER value between scraped and accumulated
                tasks_completed = max(tasks_completed, scraped_completed)
                # CRITICAL FIX: Do NOT downgrade tasks_total! Keep the higher value (configured vs scraped)
                tasks_total = max(tasks_total, scraped_total)
                
                # ========== GUARANTEE 100% COMPLETION ==========
                # AGGRESSIVE RETRY: Will NOT stop until website shows target reached!
                retry_count = 0
                max_retries = 10  # INCREASED: More aggressive retry
                
                log(f"🎯 [GUARANTEE] Target: {tasks_total} tasks. Currently: {tasks_completed}")
                
                while tasks_completed < tasks_total and retry_count < max_retries:
                    retry_count += 1
                    remaining = tasks_total - tasks_completed
                    log(f"🔄 RETRY {retry_count}/{max_retries}: Still {remaining} tasks remaining ({tasks_completed}/{tasks_total})")
                    
                    # Go back to grab page and try again
                    try:
                        page.goto("https://mba7.com/#/grab", timeout=45000)
                        page.wait_for_timeout(3000)
                        try_close_popups(page)
                        
                        # Mini loop to complete remaining tasks
                        for _ in range(remaining + 5):  # +5 buffer
                            try:
                                # Click Sedang Berlangsung
                                el = page.get_by_text("Sedang Berlangsung").nth(1)
                                if el.is_visible(timeout=2000):
                                    el.click(force=True)
                                    page.wait_for_timeout(500)
                                    
                                    # Click Kirim
                                    k_btn = page.get_by_role("button", name="Kirim")
                                    if k_btn.is_visible(timeout=2000):
                                        k_btn.click(force=True)
                                        tasks_completed += 1
                                        log(f"✓ Retry task done: {tasks_completed}/{tasks_total}")
                                        
                                        # Click confirm
                                        try:
                                            page.get_by_role("button", name="Mengonfirmasi").click(timeout=1500)
                                        except:
                                            pass
                                        
                                        if tasks_completed >= tasks_total:
                                            log(f"🎉 All tasks completed!")
                                            break
                            except:
                                pass
                        
                        # Re-check progress
                        page.goto("https://mba7.com/#/ticket", timeout=30000)
                        page.wait_for_timeout(2000)
                        pe = page.locator(".van-progress__pivot").first
                        if pe.count() > 0:
                            txt = pe.text_content(timeout=2000)
                            if txt and "/" in txt:
                                p = txt.split("/")
                                tasks_completed = int(p[0].strip())
                                # CRITICAL FIX: Do NOT downgrade tasks_total! Keep the higher value
                                scraped_t = int(p[1].strip())
                                tasks_total = max(tasks_total, scraped_t)
                                log(f"After retry: {tasks_completed}/{tasks_total}")
                    except Exception as e:
                        log(f"Retry error: {e}")
                        # DON'T break! Keep trying!
                        page.wait_for_timeout(2000)
                        continue
                
                # ========== FINAL VERIFICATION ==========
                # Check ACTUAL progress from website one more time
                log("🔍 [FINAL CHECK] Verifying actual completion from website...")
                try:
                    page.goto("https://mba7.com/#/ticket", timeout=30000)
                    page.wait_for_timeout(3000)
                    try_close_popups(page)
                    
                    pe = page.locator(".van-progress__pivot").first
                    if pe.count() > 0:
                        final_txt = pe.text_content(timeout=5000)
                        if final_txt and "/" in final_txt:
                            fp = final_txt.split("/")
                            actual_completed = int(fp[0].strip())
                            actual_total = int(fp[1].strip())
                            log(f"🔍 [FINAL CHECK] Website shows: {actual_completed}/{actual_total}")
                            
                            # Use website's actual completed count
                            tasks_completed = actual_completed
                            # But keep our target if higher
                            tasks_total = max(tasks_total, actual_total)
                            
                            if actual_completed < tasks_total:
                                log(f"⚠️ [WARNING] Website shows incomplete! {actual_completed}/{tasks_total}")
                                log(f"⚠️ [WARNING] Possible issue: Website limit or task availability")
                            else:
                                log(f"🎉 [SUCCESS] All {actual_completed} tasks verified complete!")
                except Exception as ve:
                    log(f"Final verification error: {ve}")
                
    except Exception as e:
        log(f"Could not re-scrape progress: {e}")
        # Keep accumulated value - DON'T reset to 0!
        log(f"Using accumulated progress: {tasks_completed}/{tasks_total}")

    # Final callback
    if progress_callback:
        try: progress_callback(tasks_completed, tasks_total)
        except: pass

    return tasks_completed, tasks_total


def run(playwright: Playwright, phone: str, password: str, headless: bool = False, slow_mo: int = 200, iterations: int = 30, review_text: Optional[str] = None, sync_only: bool = False, progress_callback=None) -> Tuple[int, int, float, float, float, float, list, list]:
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
            return 0, iterations, 0.0, 0.0, 0.0, 0.0, [], []

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
                page.wait_for_timeout(5000)  # Increased wait
                from .scraper import try_close_popups
                try_close_popups(page)
                page.wait_for_timeout(2000)
                
                # Log current URL to verify navigation
                log(f"  Current URL: {page.url}")
                
                # Retry logic for finding progress
                for attempt in range(3):
                    # Look for ALL progress elements and log them
                    progress_elements = page.locator(".van-progress__pivot")
                    count = progress_elements.count()
                    log(f"  Found {count} progress elements (attempt {attempt+1})")
                    
                    progress_found = False
                    # Try each element to find one with X/Y format
                    for i in range(count):
                        try:
                            elem = progress_elements.nth(i)
                            # Wait for element to be visible
                            elem.wait_for(state="visible", timeout=3000)
                            text = elem.text_content(timeout=3000)
                            log(f"    Element {i}: '{text}'")
                            if text and "/" in text:
                                parts = text.split("/")
                                tasks_completed = int(parts[0].strip())
                                scraped_total = int(parts[1].strip())
                                tasks_total = max(tasks_total, scraped_total)
                                log(f"  ✓ Current progress detected: {tasks_completed}/{tasks_total}")
                                progress_found = True
                                break
                        except Exception as e:
                            log(f"    Element {i}: error - {e}")
                    
                    if progress_found:
                        break
                    
                    # If not found, try refreshing the page
                    if attempt < 2:
                        log("  Progress not found, refreshing page...")
                        page.reload(timeout=30000)
                        page.wait_for_timeout(3000)
                        try_close_popups(page)
                else:
                    log("  ✗ No valid progress element found after retries")
                    
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
        
        # ========== SCRAPE DANA AMAL RECORDS ==========
        log("Scraping Dana Amal records from financial page...")
        dana_amal_records = scrape_dana_amal_records(page, timeout)
        log(f"  Found {len(dana_amal_records)} dana amal records")
        
        # Return progress with income, withdrawal, balance, points, calendar, and dana_amal
        log(f"Returning final progress: {tasks_completed}/{tasks_total}, Points: {points}, Calendar days: {len(calendar)}, Dana Amal records: {len(dana_amal_records)}")
        return tasks_completed, tasks_total, income, withdrawal, balance, points, calendar, dana_amal_records

    finally:
        context.close()
        browser.close()



