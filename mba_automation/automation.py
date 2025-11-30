from typing import Optional
from playwright.sync_api import Playwright, TimeoutError as PlaywrightTimeoutError


def run(playwright: Playwright, phone: str, password: str, headless: bool = False, slow_mo: int = 200, iterations: int = 30, review_text: Optional[str] = None) -> int:
    browser = playwright.chromium.launch(headless=headless, slow_mo=slow_mo)
    context = browser.new_context(viewport={"width": 375, "height": 812})
    page = context.new_page()

    # Reduce default timeout from 30s to something faster for automation
    page.set_default_timeout(5000)

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
        try:
            page.get_by_role("button", name="Mendapatkan").click()
            print("Klik Mendapatkan (list) OK")
        except PlaywrightTimeoutError:
            print("Tombol 'Mendapatkan' di halaman list nggak ketemu, stop.")
            # Return current progress if available
            return tasks_completed if tasks_completed > 0 else 0

        page.wait_for_url("**/work**", timeout=10000)

        try:
            page.get_by_role("button", name="Mendapatkan").click()
            print("Klik Mendapatkan (detail) OK")
        except PlaywrightTimeoutError:
            print("Tombol 'Mendapatkan' di halaman detail nggak ketemu.")
            return 0

        try:
            page.get_by_text("Sedang Berlangsung").nth(1).click()
        except PlaywrightTimeoutError:
            print("'Sedang Berlangsung' ke-2 nggak ketemu, stop.")
            return 0

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
        loop_count = 0
        for i in range(iterations):
            print(f"Loop ke-{i+1}")
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

        print(f"Selesai loop. {loop_count} iterations completed")
        
        # Return initial scraped progress (more accurate than loop count)
        # If scraped progress was 60/60 before we started, that's the real status
        if tasks_completed > 0:
            print(f"Returning scraped progress: {tasks_completed}/{tasks_total}")
            return tasks_completed
        else:
            # Fallback to loop count if scraping failed
            print(f"Returning loop count: {loop_count}")
            return loop_count

    finally:
        context.close()
        browser.close()
