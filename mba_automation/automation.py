from typing import Optional, Tuple
from playwright.sync_api import Playwright, Page, TimeoutError as PlaywrightTimeoutError


VIEWPORTS = {
    "iPhone 12": {"width": 390, "height": 844},
    "Pixel 5": {"width": 393, "height": 851},
    "Samsung S21": {"width": 360, "height": 800}
}


def scrape_record_page(page, url_suffix: str, record_type: str, timeout: int = 30) -> float:
    """
    Generic function to scrape total amount from a record page (deposit or withdrawal).
    
    Args:
        page: Playwright page object
        url_suffix: URL suffix (e.g., "amount/deposit/record")
        record_type: "income" or "withdrawal" to determine specific selectors/logic if needed
        timeout: Timeout in seconds
    """
    try:
        full_url = f"https://mba7.com/#/{url_suffix}"
        print(f"  Navigating to {record_type} page: {full_url}")
        page.goto(full_url, wait_until="domcontentloaded", timeout=timeout * 1000)
        
        # Wait for dynamic content
        page.wait_for_timeout(5000)
        
        # Check if any records exist
        try:
            page.wait_for_selector(".details-record-cell", timeout=5000)
        except Exception:
            print(f"  No {record_type} records found on page")
            return 0.0
        
        # Find all record cells
        cells = page.locator(".details-record-cell").all()
        print(f"  Found {len(cells)} total {record_type} records")
        
        total_amount = 0.0
        valid_count = 0
        
        for idx, cell in enumerate(cells, 1):
            try:
                # Try to get status
                status = ""
                try:
                    # Try primary selector
                    status = cell.locator(".record-status span").text_content(timeout=1000)
                except Exception:
                    try:
                        # Try secondary selector
                        status = cell.locator(".record-status").text_content(timeout=1000)
                    except Exception:
                        pass
                
                # Check if status indicates success
                is_valid = False
                if record_type == "income":
                    if status and "Dibayar" in status:
                        is_valid = True
                elif record_type == "withdrawal":
                    # Original code checked for "Kesuksesan"
                    if status and "Kesuksesan" in status:
                        is_valid = True
                
                if is_valid:
                    valid_count += 1
                    amount_el = cell.locator(".amount-change")
                    amount_text = amount_el.text_content(timeout=1000) if amount_el.count() > 0 else "0"
                    
                    if amount_text:
                        # Parse "+4.500.000,00" -> 4500000.00 or "200.000,00" -> 200000.00
                        cleaned = amount_text.strip().replace('+', '').replace('-', '').replace(' ', '').replace('.', '').replace(',', '.')
                        try:
                            amount = float(cleaned)
                            total_amount += amount
                            print(f"  ✓ {record_type.capitalize()}: {amount_text} -> {amount:,.0f}")
                        except ValueError:
                            print(f"  ✗ Failed to parse: {amount_text}")
                else:
                    # print(f"  -> SKIPPED (Status: {status})")
                    pass

            except Exception as e:
                print(f"  Error processing record {idx}: {e}")
                continue
        
        print(f"  Total valid {record_type} records: {valid_count}")
        print(f"  Total {record_type}: Rp {total_amount:,.2f}")
        return total_amount

    except Exception as e:
        print(f"Error scraping {record_type}: {e}")
        return 0.0


def scrape_income(page, timeout: int = 30) -> float:
    """Scrape total income from deposit record page."""
    return scrape_record_page(page, "amount/deposit/record", "income", timeout)


def scrape_withdrawal(page, timeout: int = 30) -> float:
    """Scrape total withdrawals from withdrawal record page."""
    return scrape_record_page(page, "amount/withdrawal/record", "withdrawal", timeout)



def run(playwright: Playwright, phone: str, password: str, headless: bool = False, slow_mo: int = 200, iterations: int = 30, review_text: Optional[str] = None, viewport_name: str = "iPhone 12", timeout: int = 30) -> Tuple[int, int, float, float]:
    browser = playwright.chromium.launch(headless=headless, slow_mo=slow_mo)
    
    vp = VIEWPORTS.get(viewport_name, VIEWPORTS["iPhone 12"])
    context = browser.new_context(viewport=vp)
    page = context.new_page()

    # Set timeout (convert to ms)
    page.set_default_timeout(timeout * 1000)

    try:
        # ========== LOGIN ==========
        page.goto("https://mba7.com/#/login", wait_until="domcontentloaded")

        page.get_by_role("textbox", name="Nomor Telepon").click()
        page.get_by_role("textbox", name="Nomor Telepon").fill(phone)

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

        # Navigate UI (kept as-is from original script)
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
        tasks_completed = 0
        tasks_total = iterations  # default to expected iterations
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
            # Navigate back to ticket page if needed, or just look for element
            # Usually we are still on the detail page or list page.
            # Let's try to find the progress element again.
            # If we are on detail page, we might need to go back? 
            # The progress bar is usually on the "Ticket" page (list).
            
            # Go to ticket page to be sure
            page.locator(".van-badge__wrapper.van-icon.van-icon-undefined.item-icon.iconfont.icon-ticket").click()
            page.wait_for_timeout(2000)
            
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

        # Scrape income and withdrawal before returning
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

def scrape_balance(page: Page, timeout: int) -> float:
    """
    Scrapes the user balance from the profile page.
    Selector: .user-balance
    """
    try:
        # Navigate to profile page
        page.goto("https://mba7.com/#/me", timeout=timeout*1000)
        page.wait_for_load_state("networkidle", timeout=timeout*1000)
        
        balance_el = page.locator(".user-balance").first
        balance_text = balance_el.text_content(timeout=5000)
        
        if balance_text:
            # Format: "370.624,00 " -> 370624.0
            clean_text = balance_text.replace(".", "").replace(",", ".").strip()
            balance = float(clean_text)
            print(f"✓ Balance found: {balance_text} -> {balance}")
            return balance
            
    except Exception as e:
        print(f"Could not scrape balance: {e}")
    
    return 0.0
