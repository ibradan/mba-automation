from playwright.sync_api import Page

def try_close_popups(page: Page):
    """Helper to dismiss common overlays that might block scraping."""
    popups = [
        ".van-popup__close-icon", 
        "button:has-text('Mengonfirmasi')", 
        "button:has-text('Confirm')",
        ".van-overlay"
    ]
    for selector in popups:
        try:
            el = page.locator(selector).first
            if el.is_visible(timeout=500):
                el.click()
                page.wait_for_timeout(500)
        except:
            pass

def scrape_record_page(page: Page, url_suffix: str, record_type: str, timeout: int = 30) -> float:
    """Generic function to scrape total amount from a record page."""
    try:
        full_url = f"https://mba7.com/#/{url_suffix}"
        print(f"  Navigating to {record_type} page: {full_url}")
        page.goto(full_url, wait_until="domcontentloaded", timeout=timeout * 1000)
        
        # Give extra time for heavy Pi Zero
        page.wait_for_timeout(10000)
        try_close_popups(page)
        
        # ... logic to scrape records ...
        try:
            page.wait_for_selector(".details-record-cell", timeout=10000)
        except Exception:
            print(f"  No {record_type} records found")
            return 0.0
        
        cells = page.locator(".details-record-cell").all()
        total_amount = 0.0
        
        for cell in cells:
            try:
                status = ""
                try: status = cell.locator(".record-status").text_content(timeout=1000)
                except: pass
                
                is_valid = False
                if record_type == "income" and status and "Dibayar" in status:
                    is_valid = True
                elif record_type == "withdrawal" and status and "Kesuksesan" in status:
                    is_valid = True
                
                if is_valid:
                    amount_el = cell.locator(".amount-change")
                    amount_text = amount_el.text_content(timeout=1000) if amount_el.count() > 0 else "0"
                    if amount_text:
                        cleaned = amount_text.strip().replace('+', '').replace('-', '').replace(' ', '').replace('.', '').replace(',', '.')
                        try: total_amount += float(cleaned)
                        except: pass
            except: continue
            
        return total_amount
    except Exception as e:
        print(f"Error scraping {record_type}: {e}")
        return 0.0

def scrape_income(page: Page, timeout: int = 30) -> float:
    return scrape_record_page(page, "amount/deposit/record", "income", timeout)

def scrape_withdrawal(page: Page, timeout: int = 30) -> float:
    return scrape_record_page(page, "amount/withdrawal/record", "withdrawal", timeout)

def scrape_balance(page: Page, timeout: int) -> float:
    """Scrapes balance with retries and popup handling."""
    for attempt in range(2):
        try:
            print(f"  Scraping balance (attempt {attempt+1})...")
            page.goto("https://mba7.com/#/me", timeout=timeout*1000)
            page.wait_for_timeout(7000)
            try_close_popups(page)
            
            balance_el = page.locator(".user-balance").first
            balance_el.wait_for(state="visible", timeout=15000)
            balance_text = balance_el.text_content(timeout=5000)
            
            if balance_text:
                clean_text = balance_text.replace(".", "").replace(",", ".").strip()
                # Remove any remaining non-numeric characters except dot
                import re
                clean_text = re.sub(r'[^\d.]', '', clean_text)
                return float(clean_text)
        except Exception as e:
            print(f"  Attempt {attempt+1} failed: {e}")
            if attempt == 0: page.reload()
            
    return 0.0
