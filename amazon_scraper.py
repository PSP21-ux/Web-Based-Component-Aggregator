import os
import time
import urllib.parse
import random

from dotenv import load_dotenv
from pymongo import MongoClient

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException


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


# Amazon database
db = client["amazon_db"]


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
# AMAZON SCRAPER
# ============================================================

def scrape_amazon(search_query):
    """
    Scrape product details from Amazon.in based on a search query.

    Includes both organic and sponsored products.
    """

    # ========================================================
    # CHROME OPTIONS
    # ========================================================

    chrome_options = webdriver.ChromeOptions()

    chrome_options.add_argument(
        "--disable-blink-features=AutomationControlled"
    )

    chrome_options.add_argument(
        "--start-maximized"
    )

    chrome_options.add_argument(
        "--headless"
    )

    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/91.0.4472.124 "
        "Safari/537.36"
    )


    # ========================================================
    # INITIALIZE WEBDRIVER
    # ========================================================

    driver = webdriver.Chrome(
        options=chrome_options
    )

    products_scraped = 0


    try:

        # ====================================================
        # ENCODE SEARCH QUERY
        # ====================================================

        encoded_query = urllib.parse.quote(
            search_query
        )


        # ====================================================
        # AMAZON SEARCH URL
        # ====================================================

        url = (
            f"https://www.amazon.in/s?k={encoded_query}"
        )

        print(
            f"Searching for: {search_query}"
        )

        print(
            f"URL: {url}"
        )

        print("-" * 50)


        # ====================================================
        # OPEN AMAZON
        # ====================================================

        driver.get(url)


        # ====================================================
        # WAIT FOR PRODUCTS
        # ====================================================

        wait = WebDriverWait(
            driver,
            10
        )

        wait.until(
            EC.presence_of_element_located(
                (
                    By.CSS_SELECTOR,
                    "div.s-main-slot.s-result-list."
                    "s-search-results"
                )
            )
        )


        # ====================================================
        # SCROLL TO LOAD PRODUCTS
        # ====================================================

        last_height = driver.execute_script(
            "return document.body.scrollHeight"
        )

        while True:

            driver.execute_script(
                "window.scrollTo("
                "0, document.body.scrollHeight"
                ");"
            )

            time.sleep(
                random.uniform(2, 5)
            )

            new_height = driver.execute_script(
                "return document.body.scrollHeight"
            )

            if new_height == last_height:
                break

            last_height = new_height


        # ====================================================
        # FIND PRODUCTS
        # ====================================================

        products = driver.find_elements(
            By.CSS_SELECTOR,
            "div.s-main-slot.s-result-list."
            "s-search-results > "
            "div[data-component-type='s-search-result']"
        )

        print(
            f"Found {len(products)} products "
            f"for '{search_query}'"
        )

        print("-" * 50)


        # ====================================================
        # GET MONGODB COLLECTION
        # ====================================================

        collection = get_collection_for_query(
            search_query
        )


        # ====================================================
        # PROCESS PRODUCTS
        # ====================================================

        for product in products:

            try:

                # =================================================
                # SPONSORED
                # =================================================

                try:

                    sponsored_text = product.find_element(
                        By.CSS_SELECTOR,
                        "span.puis-sponsored-label-text"
                    ).text

                    is_sponsored = (
                        sponsored_text == "Sponsored"
                    )

                except NoSuchElementException:

                    is_sponsored = False


                # =================================================
                # PRODUCT NAME
                # =================================================

                try:

                    # New Amazon structure
                    name = product.find_element(
                        By.CSS_SELECTOR,
                        "h2.a-size-medium."
                        "a-spacing-none."
                        "a-color-base."
                        "a-text-normal span"
                    ).text

                except NoSuchElementException:

                    try:

                        # Older Amazon structure
                        name = product.find_element(
                            By.CSS_SELECTOR,
                            "h2.a-size-base-plus."
                            "a-spacing-none."
                            "a-color-base."
                            "a-text-normal span"
                        ).text

                    except NoSuchElementException:

                        name = "Name not found"


                # =================================================
                # PRICE
                # =================================================

                try:

                    price = product.find_element(
                        By.CSS_SELECTOR,
                        "span.a-price-whole"
                    ).text

                except NoSuchElementException:

                    price = "Price not found"


                # =================================================
                # IMAGE URL
                # =================================================

                try:

                    image = product.find_element(
                        By.CSS_SELECTOR,
                        "img.s-image"
                    ).get_attribute("src")

                except NoSuchElementException:

                    image = "Image URL not found"


                # =================================================
                # PRODUCT LINK
                # =================================================

                try:

                    link = product.find_element(
                        By.CSS_SELECTOR,
                        "a.a-link-normal.s-no-outline"
                    ).get_attribute("href")


                    if link and not link.startswith(
                        "https://"
                    ):

                        link = (
                            "https://www.amazon.in"
                            + link
                        )

                except NoSuchElementException:

                    link = "Link not found"


                # =================================================
                # AVAILABILITY
                # =================================================

                try:

                    availability_text = product.text

                    if (
                        "Currently unavailable"
                        in availability_text
                    ):

                        availability = "No"

                    else:

                        availability = "Yes"

                except Exception:

                    availability = "Unknown"


                # =================================================
                # PRINT PRODUCT
                # =================================================

                print(
                    f"Product Name: {name}"
                )

                print(
                    f"Price: {price}"
                )

                print(
                    f"Image URL: {image}"
                )

                print(
                    f"Availability: {availability}"
                )

                print(
                    f"Sponsored: "
                    f"{'Yes' if is_sponsored else 'No'}"
                )

                print(
                    f"Product Link: {link}"
                )

                print("-" * 50)


                # =================================================
                # PRODUCT DATA
                # =================================================

                product_data = {

                    "name": name,

                    "price": price,

                    "availability": availability,

                    "image_url": image,

                    "product_link": link,

                    "is_sponsored": is_sponsored,

                    "search_query": search_query,

                    "timestamp": time.time()
                }


                # =================================================
                # SAVE TO MONGODB ATLAS
                # =================================================

                collection.insert_one(
                    product_data
                )

                products_scraped += 1


            except Exception as e:

                print(
                    f"Error processing product: {e}"
                )

                continue


    except TimeoutException:

        print(
            "❌ Amazon product results "
            "did not load within the timeout."
        )

    except Exception as e:

        print(
            f"Error during Amazon scraping: {e}"
        )


    finally:

        try:
            driver.quit()

        except Exception:
            pass

        print(
            "Scraping complete from Amazon. "
            f"Total products scraped: "
            f"{products_scraped}"
        )


# ============================================================
# RUN SCRAPER
# ============================================================

if __name__ == "__main__":

    query = input(
        "Enter search term: "
    )

    scrape_amazon(query)