from playwright.sync_api import Page

def scrape_record_page(page: Page, url_suffix: str, record_type: str, timeout: int = 30) -> float:
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


def scrape_income(page: Page, timeout: int = 30) -> float:
    """
    Scrape 'Deposit Kerja' (Modal) from the deposit record page.
    URL: https://mba7.com/#/amount/deposit/record
    Logic: Sum of amounts where status is 'Dibayar'
    """
    return scrape_record_page(page, "amount/deposit/record", "income", timeout)


def scrape_withdrawal(page: Page, timeout: int = 30) -> float:
    """Scrape total withdrawals from withdrawal record page."""
    return scrape_record_page(page, "amount/withdrawal/record", "withdrawal", timeout)


def scrape_balance(page: Page, timeout: int) -> float:
    """
    Scrapes the user balance from the profile page.
    Selector: .user-balance
    """
    try:
        # Navigate to profile page
        print("  Navigating to profile page: https://mba7.com/#/me")
        page.goto("https://mba7.com/#/me", timeout=timeout*1000)
        # Use simple timeout instead of networkidle for more reliable loading
        page.wait_for_timeout(3000)
        
        balance_el = page.locator(".user-balance").first
        balance_text = balance_el.text_content(timeout=5000)
        
        if balance_text:
            # Format: "370.624,00 " -> 370624.0
            clean_text = balance_text.replace(".", "").replace(",", ".").strip()
            balance = float(clean_text)
            print(f"  ✓ Balance found: {balance_text.strip()} -> {balance:,.0f}")
            return balance
        else:
            print("  ✗ Balance element found but no text content")
            
    except Exception as e:
        print(f"  ✗ Could not scrape balance: {e}")
    
    return 0.0
