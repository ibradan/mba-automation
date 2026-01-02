from playwright.sync_api import Page
import re

def try_close_popups(page: Page) -> None:
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
        
        # Reduced wait time for fast hardware
        page.wait_for_timeout(2500)
        try_close_popups(page)
        
        # ... logic to scrape records ...
        try:
            page.wait_for_selector(".details-record-cell", timeout=5000)
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
                    try:
                        amount_el = cell.locator(".amount-change")
                        amount_text = amount_el.text_content(timeout=1000) if amount_el.count() > 0 else "0"
                        if amount_text:
                            # Improved regex cleaning for financial strings
                            cleaned = re.sub(r'[^\d.,]', '', amount_text)
                            # Standardize to dot decimal: handle "1.234.567" or "1,234.56"
                            if ',' in cleaned and '.' in cleaned:
                                # Both present (eg 1.234,56 or 1,234.56) -> assume last is decimal
                                if cleaned.rfind(',') > cleaned.rfind('.'):
                                    cleaned = cleaned.replace('.', '').replace(',', '.')
                                else:
                                    cleaned = cleaned.replace(',', '')
                            elif ',' in cleaned: # Only comma eg 1234,56
                                cleaned = cleaned.replace(',', '.')
                            
                            try: total_amount += float(cleaned)
                            except: pass
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
    # Try both /mine and /me as the profile page URL
    urls = ["https://mba7.com/#/mine", "https://mba7.com/#/me"]
    
    for url in urls:
        for attempt in range(2):
            try:
                print(f"  Scraping balance from {url} (attempt {attempt+1})...")
                page.goto(url, timeout=timeout*1000)
                page.wait_for_timeout(2500)
                try_close_popups(page)
                
                # Try multiple selectors for balance
                selectors = [".user-balance", ".balance-amount", ".amount-value"]
                balance_el = None
                for selector in selectors:
                    el = page.locator(selector).first
                    if el.count() > 0 and el.is_visible(timeout=2000):
                        balance_el = el
                        break
                
                if not balance_el:
                    # Fallback: look for text "Saldo Rekening" and get next sibling or parent's child
                    # This is a bit more complex but can be very robust
                    print("  Primary selectors failed, trying text-based search...")
                    if page.get_by_text("Saldo Rekening").count() > 0:
                        # In many mobile sites, the value is near the label
                        balance_text = page.locator("body").text_content()
                        # Use regex to find number after "Saldo Rekening"
                        match = re.search(r'Saldo Rekening\s*Rp\s*([\d.,]+)', balance_text)
                        if match:
                            balance_text = match.group(1)
                        else:
                            continue
                    else:
                        continue
                else:
                    balance_text = balance_el.text_content(timeout=5000)
                
                if balance_text:
                    print(f"  Raw balance text: {balance_text}")
                    # Robust cleaning: remove everything except digits, commas and dots
                    cleaned = re.sub(r'[^\d.,]', '', balance_text)
                    
                    # Standardize to dot decimal: handle "1.234.567" or "1,234.56"
                    if ',' in cleaned and '.' in cleaned:
                        if cleaned.rfind(',') > cleaned.rfind('.'):
                            cleaned = cleaned.replace('.', '').replace(',', '.')
                        else:
                            cleaned = cleaned.replace(',', '')
                    elif ',' in cleaned:
                        cleaned = cleaned.replace(',', '.')
                    elif cleaned.count('.') > 1:
                        # Multiple dots mean they are thousands separators (eg 1.000.000)
                        cleaned = cleaned.replace('.', '')
                        
                    try: 
                        val = float(cleaned)
                        if val > 0: 
                            print(f"  Successfully scraped balance: {val}")
                            return val
                    except: pass
            except Exception as e:
                print(f"  Attempt {attempt+1} at {url} failed: {e}")
                if attempt == 0: page.reload()
            
    return 0.0

def scrape_points(page: Page, timeout: int = 30) -> float:
    """Scrapes point balance from points/shop page. Assumes caller has navigated to correct page."""
    try:
        # Look for points balance (caller should already be on points/shop page)
        # Selector based on user request: <div class="points-balance">80,00 </div>
        el = page.locator(".points-balance").first
        if el.is_visible(timeout=5000):
            text = el.text_content()
            print(f"  Raw points text: {text}")
            if text:
                cleaned = re.sub(r'[^\d.,]', '', text)
                if ',' in cleaned:
                    cleaned = cleaned.replace(',', '.')
                try:
                    val = float(cleaned)
                    print(f"  Successfully scraped points: {val}")
                    return val
                except: pass
        else:
            print("  .points-balance element not visible")
    except Exception as e:
        print(f"  Error scraping points: {e}")
    return 0.0

def scrape_calendar_data(page: Page, timeout: int = 30) -> list:
    """Scrapes calendar attendance status. Assumes calendar popup is already open."""
    calendar_data = []
    try:
        # Check if calendar is actually open
        if not page.locator(".van-calendar__month-title").first.is_visible(timeout=5000):
            print("  Calendar not open, returning empty data")
            return []
        
        month_title = page.locator(".van-calendar__month-title").first.text_content()
        print(f"  Calendar month: {month_title}")
        
        # Iterate over all days
        # User provided snippet shows class "signed-day" is used for attended days
        # Also contains <div class="van-calendar__bottom-info">Masuk</div>
        
        days = page.locator(".van-calendar__day").all()
        
        for day in days:
            try:
                # 1. Check for 'signed-day' class (Faster determination)
                class_attr = day.get_attribute("class") or ""
                
                # 2. Check for "Masuk" text
                text = day.text_content() or ""
                
                is_attended = False
                if "signed-day" in class_attr:
                    is_attended = True
                elif "Masuk" in text:
                    is_attended = True
                    
                if is_attended:
                    # Extract day number
                    # Text often looks like "1Masuk" or "1"
                    # We want the first sequence of digits
                    match = re.search(r'(\d+)', text)
                    if match:
                        day_num = int(match.group(1))
                        # Sanity check: day should be 1-31
                        if 1 <= day_num <= 31:
                            calendar_data.append(day_num)
                            
            except Exception as e: 
                pass
            
        print(f"  Scraped attendance days: {calendar_data}")
        
    except Exception as e:
        print(f"  Error scraping calendar: {e}")
    
    return calendar_data
