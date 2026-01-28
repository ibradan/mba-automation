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
    
    # Check for "Data sedang diproses" toast/popup
    try:
        toast = page.locator(".van-toast__text, .van-toast").first
        if toast.is_visible(timeout=500):
            text = toast.text_content()
            if "diproses" in text or "processing" in text.lower():
                print("  'Data processing' popup detected, waiting 3s...")
                page.wait_for_timeout(3000)
    except: pass

    for selector in popups:
        try:
            el = page.locator(selector).first
            if el.is_visible(timeout=500):
                el.click()
                page.wait_for_timeout(500)
        except:
            pass

def scrape_record_page(page: Page, url_suffix: str, record_type: str, timeout: int = 30) -> float:
    """
    Generic function to scrape total amount from a record page.
    For withdrawal: returns NET amount (after applying date-based tax per transaction)
    For income: returns GROSS amount
    
    Tax rules for withdrawal:
    - Before 2026-01-28: 10% tax (multiply by 0.9)
    - From 2026-01-28 onwards: 8% tax (multiply by 0.92)
    """
    from datetime import datetime
    
    # Tax cutoff date: 2026-01-28
    TAX_CUTOFF = datetime(2026, 1, 28)
    
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
                # 1. Check Status
                status = ""
                try: status = cell.locator(".record-status").text_content(timeout=1000)
                except: pass
                
                is_valid = False
                if record_type == "income" and status and "Dibayar" in status:
                    is_valid = True
                elif record_type == "withdrawal" and status and "Kesuksesan" in status:
                    is_valid = True
                
                if is_valid:
                    # 2. Extract Amount
                    amount = 0.0
                    try:
                        amount_el = cell.locator(".amount-change")
                        amount_text = amount_el.text_content(timeout=1000) if amount_el.count() > 0 else "0"
                        if amount_text:
                            # Improved regex cleaning for financial strings
                            cleaned = re.sub(r'[^\d.,]', '', amount_text)
                            # Standardize number format
                            if ',' in cleaned and '.' in cleaned:
                                if cleaned.rfind(',') > cleaned.rfind('.'):
                                    cleaned = cleaned.replace('.', '').replace(',', '.')
                                else:
                                    cleaned = cleaned.replace(',', '')
                            elif ',' in cleaned: 
                                # Comma only: 10,000 or 10,50
                                if cleaned.count(',') > 1 or len(cleaned.split(',')[-1]) == 3:
                                    cleaned = cleaned.replace(',', '') # Assume thousands
                                else:
                                    cleaned = cleaned.replace(',', '.') # Assume decimal
                            elif '.' in cleaned:
                                # Dot only: 10.000 or 10.50
                                if cleaned.count('.') > 1 or len(cleaned.split('.')[-1]) == 3:
                                    cleaned = cleaned.replace('.', '') # Assume thousands
                                # else assume decimal (standard float), do nothing
                            
                            try: amount = float(cleaned)
                            except: pass
                    except: pass
                    
                    if amount > 0:
                        # 3. Apply Tax (Withdrawal only)
                        if record_type == "withdrawal":
                            # Default to 10% (0.9) if date extraction fails
                            multiplier = 0.9
                            date_str = "Unknown"
                            
                            try:
                                # Extract full text from cell to find date
                                full_text = cell.text_content(timeout=1000)
                                # Look for DD/MM/YYYY pattern
                                date_match = re.search(r'(\d{2})/(\d{2})/(\d{4})', full_text)
                                
                                if date_match:
                                    day, month, year = int(date_match.group(1)), int(date_match.group(2)), int(date_match.group(3))
                                    tx_date = datetime(year, month, day)
                                    date_str = tx_date.strftime('%Y-%m-%d')
                                    
                                    # Logic: 8% on or after 2026-01-28
                                    if tx_date >= TAX_CUTOFF:
                                        multiplier = 0.92
                            except Exception as e:
                                print(f"    Date parsing failed: {e}")
                            
                            net_amount = amount * multiplier
                            if multiplier > 0.9:
                                print(f"    Withdrawal {date_str}: Rp {amount:,.0f} -> Rp {net_amount:,.0f} (8% tax)")
                            else:
                                print(f"    Withdrawal {date_str}: Rp {amount:,.0f} -> Rp {net_amount:,.0f} (10% tax)")
                                
                            total_amount += net_amount
                        else:
                            # Income is gross
                            total_amount += amount
                            
            except Exception as e: 
                print(f"Error processing cell: {e}")
                continue
            
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
    # Try /me first (more reliable), then /mine
    urls = ["https://mba7.com/#/me", "https://mba7.com/#/mine"]
    
    for url in urls:
        for attempt in range(3):  # Increased retries
            try:
                print(f"  Scraping balance from {url} (attempt {attempt+1})...")
                page.goto(url, timeout=timeout*1000)
                page.wait_for_timeout(3000)  # Increased wait
                try_close_popups(page)
                page.wait_for_timeout(1000)  # Extra wait after popup close
                
                # Try multiple selectors for balance - expanded list
                selectors = [
                    ".user-balance", 
                    ".balance-amount", 
                    ".amount-value",
                    ".van-cell__value",  # Common mobile framework selector
                    "[class*='balance']",  # Any class containing 'balance'
                ]
                balance_el = None
                for selector in selectors:
                    try:
                        el = page.locator(selector).first
                        if el.count() > 0:
                            # Wait properly for visibility
                            el.wait_for(state="visible", timeout=3000)
                            if el.is_visible():
                                balance_el = el
                                break
                    except:
                        continue
                
                balance_text = None
                
                if balance_el:
                    balance_text = balance_el.text_content(timeout=5000)
                
                # Fallback: look for text "Saldo Rekening" or any financial number pattern
                if not balance_text or not re.search(r'[\d.,]+', balance_text):
                    print("  Primary selectors failed, trying text-based search...")
                    body_text = page.locator("body").text_content(timeout=5000)
                    
                    # Try multiple regex patterns
                    patterns = [
                        r'Saldo Rekening\s*(?:Rp)?\s*([\d.,]+)',
                        r'(?:Rp|IDR)\s*([\d.,]+)',
                        r'Balance[:\s]*([\d.,]+)',
                    ]
                    
                    for pattern in patterns:
                        match = re.search(pattern, body_text, re.IGNORECASE)
                        if match:
                            balance_text = match.group(1)
                            print(f"  Found via pattern: {balance_text}")
                            break
                
                if balance_text:
                    print(f"  Raw balance text: {balance_text}")
                    # Robust cleaning: remove everything except digits, commas and dots
                    cleaned = re.sub(r'[^\d.,]', '', balance_text)
                    
                    if not cleaned:
                        continue
                    
                    # Standardize to dot decimal: handle "1.234.567" or "1,234.56"
                    if ',' in cleaned and '.' in cleaned:
                        if cleaned.rfind(',') > cleaned.rfind('.'):
                            # Format: 1.234,56 -> 1234.56
                            cleaned = cleaned.replace('.', '').replace(',', '.')
                        else:
                            # Format: 1,234.56 -> 1234.56
                            cleaned = cleaned.replace(',', '')
                    elif ',' in cleaned:
                        # Only comma: 1234,56 -> 1234.56
                        cleaned = cleaned.replace(',', '.')
                    elif cleaned.count('.') > 1:
                        # Multiple dots mean they are thousands separators (eg 1.000.000)
                        cleaned = cleaned.replace('.', '')
                        
                    try: 
                        val = float(cleaned)
                        if val > 0: 
                            print(f"  Successfully scraped balance: {val}")
                            return val
                        elif val == 0:
                            print(f"  Balance is 0, will try next URL/attempt")
                    except ValueError as e:
                        print(f"  Could not parse '{cleaned}' as float: {e}")
            except Exception as e:
                print(f"  Attempt {attempt+1} at {url} failed: {e}")
                if attempt < 2:
                    page.wait_for_timeout(1000)
                    try:
                        page.reload()
                    except:
                        pass
            
    print("  WARNING: All balance scraping attempts failed, returning 0")
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


def scrape_dana_amal_records(page: Page, timeout: int = 30) -> list:
    """
    Scrapes dana amal (financial) records from the /financial/record page.
    Returns a list of dicts with: period, product, amount, rate, days, profit
    """
    records = []
    try:
        full_url = "https://mba7.com/#/financial/record"
        print(f"  Navigating to Dana Amal page: {full_url}")
        page.goto(full_url, wait_until="domcontentloaded", timeout=timeout * 1000)
        
        # Handle "Data sedang diproses" or other popups that block loading
        for i in range(5): # Wait up to 15 seconds for busy popup to clear
            page.wait_for_timeout(2000)
            try_close_popups(page)
            
            # Check for "Data sedang diproses" text in body as well
            if "diproses" not in page.locator("body").text_content().lower():
                break
            print(f"  System still busy (attempt {i+1}/5), waiting...")
        
        # Wait for records to load - the site uses .van-cell for each record
        try:
            # First look for empty state
            if "tidak ada data" in page.locator("body").text_content().lower():
                print("  Confirmed: No dana amal records (Empty Page)")
                return []
                
            page.wait_for_selector(".van-cell", timeout=10000)
        except Exception:
            print("  No dana amal records found (.van-cell selector timed out)")
            return []
        
        # Get all van-cell elements (each represents one investment record)
        cells = page.locator(".van-cell").all()
        print(f"  Found {len(cells)} .van-cell elements")
        
        for idx, cell in enumerate(cells):
            try:
                # Get full text content of the cell
                text = cell.text_content(timeout=2000)
                if not text:
                    continue
                
                record = {
                    'period': '',
                    'product': '',
                    'amount': 0,
                    'rate': 0,
                    'days': 0,
                    'profit': 0,
                }
                
                # Parse the text content
                # Format: "01/16/2026 12:12:21 ~ 02/05/2026 12:13:21Invesco US Shariah EquityPeriode Investasi:20Return (hari):15.0000 %Jumlah investasi:80.000,00 Laba:wait...menerima"
                
                # Extract period (date range)
                period_match = re.search(r'(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2}\s*~\s*\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2})', text)
                if period_match:
                    record['period'] = period_match.group(1).strip()
                
                # Extract product name (between period and "Periode Investasi")
                if 'Periode Investasi' in text:
                    if period_match:
                        after_period = text[period_match.end():]
                        product_end = after_period.find('Periode Investasi')
                        if product_end > 0:
                            record['product'] = after_period[:product_end].strip()
                
                # Extract days (Periode Investasi:XX)
                days_match = re.search(r'Periode Investasi[:\s]*(\d+)', text)
                if days_match:
                    record['days'] = int(days_match.group(1))
                
                # Extract rate (Return (hari):XX.XXXX %)
                rate_match = re.search(r'Return\s*\(?hari\)?[:\s]*(\d+[\.,]?\d*)\s*%', text)
                if rate_match:
                    rate_str = rate_match.group(1).replace(',', '.')
                    record['rate'] = float(rate_str)
                
                # Extract amount (Jumlah investasi:XX.XXX,XX)
                amount_match = re.search(r'Jumlah investasi[:\s]*([\d.,]+)', text)
                if amount_match:
                    amount_str = amount_match.group(1)
                    # Convert Indonesian format (80.000,00) to float
                    amount_str = amount_str.replace('.', '').replace(',', '.')
                    try:
                        record['amount'] = float(amount_str)
                    except:
                        pass
                
                # Calculate profit: amount × (rate/100) × days
                if record['amount'] > 0 and record['rate'] > 0 and record['days'] > 0:
                    record['profit'] = record['amount'] * (record['rate'] / 100) * record['days']
                
                # Only add if we got meaningful data
                if record['amount'] > 0 or record['period']:
                    records.append(record)
                    print(f"  Record {idx+1}: {record['product'][:30]}... Amt={record['amount']}, Rate={record['rate']}%, Days={record['days']}, Profit={record['profit']:.0f}")
                
            except Exception as e:
                print(f"  Error parsing record {idx}: {e}")
                continue
        
        print(f"  Successfully scraped {len(records)} dana amal records")
        
    except Exception as e:
        print(f"  Error in scrape_dana_amal_records: {e}")
    
    return records
