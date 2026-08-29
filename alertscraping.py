import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
import time
import random


def build_driver(headless=False):
    """Creates an undetected-chromedriver instance to better evade Cloudflare."""
    options = uc.ChromeOptions()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--start-maximized")
    driver = uc.Chrome(options=options)
    return driver


def wait_out_cloudflare(driver, max_attempts=4, wait_seconds=5):
    """Polls the page title until the Cloudflare 'Just a moment...' challenge clears."""
    for attempt in range(1, max_attempts + 1):
        if "Just a moment" not in driver.title:
            return True
        time.sleep(wait_seconds)
    return "Just a moment" not in driver.title


def scrape_product_availability(product_url, headless=False):
    """
    Uses undetected-chromedriver to check if a product is in stock.
    headless=False by default since plain headless Chrome gets blocked
    by Cloudflare on robu.in — same issue the main scraper hit. If you're
    running this on a headless server, use Xvfb rather than headless=True.
    """
    driver = build_driver(headless=headless)
    time.sleep(random.uniform(1, 2))

    try:
        driver.get(product_url)
        wait_out_cloudflare(driver)
        time.sleep(2)  # give dynamic content a moment to render after the challenge clears

        #### ROBU.IN
        if "robu.in" in product_url:
            page_text = driver.page_source.lower()

            # Explicit out-of-stock / backorder signals take priority
            if "out of stock" in page_text:
                return False

            # Try the specific in-stock element first, but don't treat its
            # absence as proof of unavailability — the selector may be
            # stale against the current site markup (unverified).
            try:
                in_stock_element = driver.find_element(By.CSS_SELECTOR, "p.stock.in-stock")
                if "in stock" in in_stock_element.text.lower():
                    return True
            except NoSuchElementException:
                pass

            # Fall back to checking for an active Add to Cart button/text,
            # since we've confirmed elsewhere that robu.in renders
            # "Add to Cart" / "Backorder" text rather than WooCommerce
            # stock classes on listing pages — detail pages likely follow
            # a similar custom pattern rather than p.stock.in-stock.
            if "add to cart" in page_text and "out of stock" not in page_text:
                return True

            return False

        #### ROBOCRAZE
        if "robocraze.com" in product_url:
            try:
                driver.find_element(By.CSS_SELECTOR, "span.price__badge-sold-out")
                return False
            except NoSuchElementException:
                pass
            try:
                add_btn = driver.find_element(By.CSS_SELECTOR, "button.product-form__submit")
                if "add to cart" in add_btn.text.lower():
                    return True
            except NoSuchElementException:
                pass
            return False

        #### FALLBACK (for Amazon or other domains)
        page_text = driver.page_source.lower()
        if any(term in page_text for term in ["out of stock", "sold out", "currently unavailable"]):
            return False
        return True

    except Exception as e:
        print(f"[ERROR] Selenium check failed for {product_url}: {e}")
        return False
    finally:
        try:
            driver.quit()
        except Exception:
            pass