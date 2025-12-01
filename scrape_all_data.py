#!/usr/bin/env python3
"""
Quick script to scrape BOTH income AND withdrawal for all accounts.
"""

import json
from playwright.sync_api import sync_playwright
from mba_automation.automation import scrape_income, scrape_withdrawal

def main():
    # Load accounts
    with open('accounts.json', 'r') as f:
        accounts = json.load(f)
    
    print(f"Found {len(accounts)} accounts. Scraping income & withdrawal...")
    
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        
        for idx, acc in enumerate(accounts, 1):
            phone = acc.get('phone', '')
            password = acc.get('password', '')
            
            if not phone or not password:
                print(f"{idx}. Skipping account (missing phone/password)")
                continue
            
            phone_display = phone[2:] if phone.startswith('62') else phone
            print(f"\n{idx}. Processing +62{phone_display}...")
            
            try:
                # Login
                context = browser.new_context(viewport={"width": 390, "height": 844})
                page = context.new_page()
                page.set_default_timeout(30000)
                
                page.goto("https://mba7.com/#/login", wait_until="domcontentloaded")
                page.get_by_role("textbox", name="Nomor Telepon").fill(phone_display)
                page.get_by_role("textbox", name="Kata Sandi").fill(password)
                page.get_by_role("button", name="Masuk").click()
                
                # Wait for login
                page.wait_for_timeout(3000)
                
                # Scrape income
                print("  Scraping income...")
                income = scrape_income(page, timeout=30)
                
                # Scrape withdrawal
                print("  Scraping withdrawal...")
                withdrawal = scrape_withdrawal(page, timeout=30)
                
                # Save to account
                import datetime
                today = datetime.datetime.now().strftime('%Y-%m-%d')
                
                if 'daily_progress' not in acc:
                    acc['daily_progress'] = {}
                
                if today not in acc['daily_progress']:
                    acc['daily_progress'][today] = {
                        'completed': 0,
                        'total': 0,
                        'percentage': 0
                    }
                
                acc['daily_progress'][today]['income'] = income
                acc['daily_progress'][today]['withdrawal'] = withdrawal
                
                print(f"   ✓ TOTAL Income: Rp {income:,.0f}")
                print(f"   ✓ TOTAL Withdrawal: Rp {withdrawal:,.0f}")
                
                context.close()
                
            except Exception as e:
                print(f"   ✗ Error: {e}")
                import traceback
                traceback.print_exc()
                continue
        
        browser.close()
    
    # Save updated accounts
    with open('accounts.json', 'w') as f:
        json.dump(accounts, f, indent=2)
    
    print("\n✅ All done! Income & withdrawal saved to accounts.json")
    print("🔄 Refresh your browser to see both income and withdrawal displayed!")

if __name__ == "__main__":
    main()
