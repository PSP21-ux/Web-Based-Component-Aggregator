from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.chrome.options import Options
import time
import random

def scrape_product_availability(product_url):
    """Use headless Selenium to check if a product is in stock."""
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("start-maximized")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0 Safari/537.36")

    driver = webdriver.Chrome(options=chrome_options)
    time.sleep(random.uniform(1, 2))

    try:
        driver.get(product_url)
        time.sleep(2)  # Give time to load dynamic content

        #### ROBU.IN
        if "robu.in" in product_url:
            try:
                in_stock_element = driver.find_element(By.CSS_SELECTOR, "p.stock.in-stock")
                if "in stock" in in_stock_element.text.lower():
                    return True
            except NoSuchElementException:
                pass
            return False

        #### ROBOCRAZE
        if "robocraze.com" in product_url:
            try:
                # Check for Sold Out badge
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
        driver.quit()
