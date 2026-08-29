import os
import time
import random
import urllib.parse

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException

from pymongo import MongoClient
from dotenv import load_dotenv


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")

if not MONGO_URI:
    raise ValueError(
        "MONGO_URI not found in .env. "
        "Make sure your .env file contains MONGO_URI."
    )


# ============================================================
# MONGODB ATLAS
# ============================================================

try:
    client = MongoClient(
        MONGO_URI,
        serverSelectionTimeoutMS=5000
    )

    # Test MongoDB Atlas connection
    client.admin.command("ping")

    print("✅ Connected to MongoDB Atlas")

except Exception as e:
    print("❌ MongoDB Atlas connection failed:")
    print(e)
    raise


db = client["robu_db"]


# ============================================================
# FALLBACK CATEGORY URLS
# ============================================================

# Known cases where Robu's ?s= search returns 0 results
# even though products exist.
#
# Add more terms here as you discover them.

FALLBACK_CATEGORY_URLS = {
    "raspberry pi": "https://robu.in/brand/raspberry-pi/",
    "raspberry": "https://robu.in/brand/raspberry-pi/",
}


# ============================================================
# MONGODB COLLECTION
# ============================================================

def get_collection_for_query(search_query):
    """
    Returns a MongoDB collection for the given search query.

    Example:
        arduino
        -> arduino_products

        raspberry pi
        -> raspberry_pi_products
    """

    collection_name = (
        f"{search_query.lower().replace(' ', '_')}_products"
    )

    return db[collection_name]


# ============================================================
# CHROME DRIVER
# ============================================================

def build_driver(headless=False):
    """
    Creates an undetected-chromedriver instance
    to better evade Cloudflare.
    """

    options = uc.ChromeOptions()

    if headless:
        options.add_argument("--headless=new")

    options.add_argument("--start-maximized")

    driver = uc.Chrome(options=options)

    return driver


# ============================================================
# CLOUDFLARE HANDLING
# ============================================================

def wait_out_cloudflare(driver, max_attempts=4, wait_seconds=5):
    """
    Polls the page title until the Cloudflare
    'Just a moment...' challenge clears.

    Returns:
        True  -> Cloudflare cleared
        False -> still blocked
    """

    for attempt in range(1, max_attempts + 1):

        if "Just a moment" not in driver.title:
            return True

        print(
            f"Cloudflare challenge detected. "
            f"Waiting... ({attempt}/{max_attempts})"
        )

        time.sleep(wait_seconds)

    return "Just a moment" not in driver.title


# ============================================================
# CHECK SEARCH RESULTS
# ============================================================

def get_results_status(driver):
    """
    Returns:

        "results" -> product grid present
        "empty"   -> page explicitly says 'Showing 0 of 0'
        "unknown" -> neither found within timeout
    """

    wait = WebDriverWait(driver, 20)

    try:
        wait.until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, ".product-grid-main")
            )
        )

        return "results"

    except TimeoutException:
        pass

    try:
        showing = driver.find_element(
            By.XPATH,
            "//*[contains(text(),'Showing')]"
        )

        if "Showing 0 of 0" in showing.text:
            return "empty"

    except NoSuchElementException:
        pass

    return "unknown"


# ============================================================
# EXTRACT PRODUCTS
# ============================================================

def extract_products_from_grid(driver):
    """
    Extracts product information from the currently
    loaded Robu product grid.
    """

    products_data = []

    products = driver.find_elements(
        By.CSS_SELECTOR,
        ".product-grid-main .product-block"
    )

    print(f"Extracting {len(products)} products...")

    for product in products:

        # ----------------------------------------------------
        # NAME
        # ----------------------------------------------------

        try:
            name_element = product.find_element(
                By.CSS_SELECTOR,
                ".product-details h4 a"
            )

            name = name_element.text.strip()

            if not name:
                name = (
                    name_element
                    .get_attribute("textContent")
                    .strip()
                )

        except Exception as e:
            print("ERROR getting name:", e)
            name = "Product name not found"


        # ----------------------------------------------------
        # PRICE
        # ----------------------------------------------------

        try:
            price = product.find_element(
                By.CSS_SELECTOR,
                ".product-price .price"
            ).text.strip()

        except NoSuchElementException:
            price = "Price not found"


        # ----------------------------------------------------
        # IMAGE
        # ----------------------------------------------------

        try:
            image = product.find_element(
                By.CSS_SELECTOR,
                ".product-image img"
            ).get_attribute("src")

        except NoSuchElementException:
            image = "Image URL not found"


        # ----------------------------------------------------
        # PRODUCT LINK
        # ----------------------------------------------------

        try:
            link = product.find_element(
                By.CSS_SELECTOR,
                ".product-details h4 a"
            ).get_attribute("href")

        except NoSuchElementException:
            link = "Link not found"


        # ----------------------------------------------------
        # AVAILABILITY
        # ----------------------------------------------------

        availability = "Unknown"

        # Check "Out of Stock" first.
        #
        # When a product is out of stock, Robu doesn't render
        # an Add to Cart button. Instead it renders:
        #
        # .product-out-of-stock
        #
        # Therefore we check this first.

        try:

            out_of_stock_el = product.find_element(
                By.CSS_SELECTOR,
                ".product-out-of-stock"
            )

            if (
                out_of_stock_el.text
                .strip()
                .lower()
                == "out of stock"
            ):
                availability = "Out of Stock"

        except NoSuchElementException:

            # ------------------------------------------------
            # ADD TO CART / BACKORDER
            # ------------------------------------------------

            try:

                add_to_cart_button = product.find_element(
                    By.CSS_SELECTOR,
                    "button.product-button"
                )

                button_text = (
                    add_to_cart_button.text
                    .strip()
                    .lower()
                )

                if "backorder" in button_text:
                    availability = "Backorder"

                elif "add to cart" in button_text:
                    availability = "Yes"

                else:
                    availability = "Unknown"

            except NoSuchElementException:
                availability = "Unknown"


        # ----------------------------------------------------
        # PRINT PRODUCT
        # ----------------------------------------------------

        print(f"Product Name: {name}")
        print(f"Price: {price}")
        print(f"Image URL: {image}")
        print(f"Availability: {availability}")
        print(f"Product Link: {link}")
        print("-" * 50)


        # ----------------------------------------------------
        # STORE PRODUCT
        # ----------------------------------------------------

        products_data.append({
            "name": name,
            "price": price,
            "availability": availability,
            "image_url": image,
            "product_link": link,
        })


    return products_data


# ============================================================
# SCROLL PAGE
# ============================================================

def scroll_to_load_all(driver, max_scrolls=5):
    """
    Scrolls down the page to load additional products.
    """

    last_height = driver.execute_script(
        "return document.body.scrollHeight"
    )

    for _ in range(max_scrolls):

        driver.execute_script(
            "window.scrollTo(0, document.body.scrollHeight);"
        )

        time.sleep(random.uniform(1, 2))

        new_height = driver.execute_script(
            "return document.body.scrollHeight"
        )

        if new_height == last_height:
            break

        last_height = new_height


# ============================================================
# MAIN SCRAPER
# ============================================================

def scrape_robu(search_query, headless=False):
    """
    Scrape product details from Robu.in based on
    a search query.

    Falls back to a known category/brand page if
    the search genuinely returns 0 results.
    """

    driver = build_driver(headless=headless)

    products_scraped = 0

    try:

        # ----------------------------------------------------
        # BUILD SEARCH URL
        # ----------------------------------------------------

        encoded_query = urllib.parse.quote(search_query)

        url = (
            f"https://robu.in/?s={encoded_query}"
            f"&post_type=product"
        )

        print(f"Searching for: {search_query}")
        print(f"URL: {url}")
        print("-" * 50)


        # ----------------------------------------------------
        # OPEN PAGE
        # ----------------------------------------------------

        driver.get(url)

        wait_out_cloudflare(driver)


        # ----------------------------------------------------
        # CHECK RESULTS
        # ----------------------------------------------------

        status = get_results_status(driver)


        # ----------------------------------------------------
        # FALLBACK
        # ----------------------------------------------------

        if status == "empty":

            fallback_url = FALLBACK_CATEGORY_URLS.get(
                search_query.lower()
            )

            if fallback_url:

                print(
                    f"Site search returned 0 results for "
                    f"'{search_query}'."
                )

                print(
                    f"Falling back to category page: "
                    f"{fallback_url}"
                )

                driver.get(fallback_url)

                wait_out_cloudflare(driver)

                status = get_results_status(driver)

            else:

                print(
                    f"Site search returned 0 results for "
                    f"'{search_query}', and no fallback URL "
                    f"is configured for this term."
                )

                return


        # ----------------------------------------------------
        # UNKNOWN RESULT
        # ----------------------------------------------------

        if status == "unknown":

            print(
                "Unknown issue — neither product grid nor "
                "'Showing 0 of 0' found."
            )

            print(
                "Taking a screenshot for debugging..."
            )

            driver.save_screenshot(
                f"robu_search_{search_query}.png"
            )

            return


        # ----------------------------------------------------
        # SCROLL
        # ----------------------------------------------------

        print("Finished checking results.")
        print("Scrolling to load all products...")

        scroll_to_load_all(driver)

        print(
            "Finished scrolling. Extracting products..."
        )


        # ----------------------------------------------------
        # EXTRACT PRODUCTS
        # ----------------------------------------------------

        products_data = extract_products_from_grid(
            driver
        )

        print(
            f"Found {len(products_data)} products "
            f"for '{search_query}'"
        )

        print("-" * 50)


        # ----------------------------------------------------
        # SAVE TO MONGODB ATLAS
        # ----------------------------------------------------

        collection = get_collection_for_query(
            search_query
        )

        for product_data in products_data:

            product_data["search_query"] = search_query

            product_data["timestamp"] = time.time()

            collection.insert_one(product_data)

            products_scraped += 1


    except Exception as e:

        print(
            f"Error during scraping: {e}"
        )

        try:
            driver.save_screenshot(
                f"robu_error_{search_query}.png"
            )

        except Exception:
            pass


    finally:

        try:
            driver.quit()

        except Exception:
            pass

        print(
            f"Scraping complete. "
            f"Total products scraped: {products_scraped}"
        )


# ============================================================
# RUN SCRAPER
# ============================================================

if __name__ == "__main__":

    query = input(
        "Enter search term: "
    )

    scrape_robu(query)