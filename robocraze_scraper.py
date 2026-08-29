import os
import time
import urllib.parse
import re

from dotenv import load_dotenv
from pymongo import MongoClient

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


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

    # Test the connection
    client.admin.command("ping")

    print("✅ Connected to MongoDB Atlas")

except Exception as e:
    print("❌ MongoDB Atlas connection failed:")
    print(e)
    raise


db = client["robocraze_db"]


# ============================================================
# GET COLLECTION
# ============================================================

def get_collection_for_query(search_query):
    """
    Returns a MongoDB collection for the given search query.
    """

    collection_name = (
        f"{search_query.lower().replace(' ', '_')}_products"
    )

    return db[collection_name]


# ============================================================
# IMAGE URL EXTRACTION
# ============================================================

def extract_clean_image_url(product_element):
    """
    Extract a clean image URL from the product element
    using multiple strategies.
    """

    try:

        # ----------------------------------------------------
        # Strategy 1: Find image elements
        # ----------------------------------------------------

        img_selectors = [
            "img.motion-reduce",
            "img.lazyloaded",
            "img.lazyload",
            "img",
            ".card-media img",
            "div[class*='media'] img",
            "div[class*='image'] img"
        ]

        for selector in img_selectors:

            try:

                img_elements = product_element.find_elements(
                    By.CSS_SELECTOR,
                    selector
                )

                for img_elem in img_elements:

                    # Try different image attributes
                    attributes = [
                        "src",
                        "data-src",
                        "data-original",
                        "data-lazy-src"
                    ]

                    for attr in attributes:

                        url = img_elem.get_attribute(attr)

                        if (
                            url
                            and url != "None"
                            and not url.endswith(".gif")
                            and len(url) > 10
                        ):

                            if url.startswith("//"):
                                return "https:" + url

                            return url


                    # Try srcset
                    srcset = img_elem.get_attribute("srcset")

                    if srcset:

                        first_image = (
                            srcset
                            .split(",")[0]
                            .strip()
                            .split(" ")[0]
                        )

                        if (
                            first_image
                            and not first_image.endswith(".gif")
                        ):

                            if first_image.startswith("//"):
                                return "https:" + first_image

                            return first_image

            except Exception:
                continue


        # ----------------------------------------------------
        # Strategy 2: Search product HTML
        # ----------------------------------------------------

        try:

            product_html = product_element.get_attribute(
                "outerHTML"
            )

            patterns = [
                r'src="(//robocraze\.com/cdn/shop/[^"]+\.(jpg|jpeg|png|webp)[^"]*)"',
                r'data-src="(//robocraze\.com/cdn/shop/[^"]+\.(jpg|jpeg|png|webp)[^"]*)"',
                r'srcset="([^"]*robocraze\.com/cdn/shop/[^"]+\.(jpg|jpeg|png|webp)[^"]*)"',
            ]

            for pattern in patterns:

                matches = re.findall(
                    pattern,
                    product_html
                )

                if matches:

                    url_match = (
                        matches[0][0]
                        if isinstance(matches[0], tuple)
                        else matches[0]
                    )

                    # If srcset, extract first URL
                    if " " in url_match:

                        first_url = (
                            url_match
                            .split(",")[0]
                            .split(" ")[0]
                            .strip()
                        )

                        if (
                            first_url
                            and not first_url.endswith(".gif")
                        ):

                            if first_url.startswith("//"):
                                return "https:" + first_url

                            return first_url

                    else:

                        if not url_match.endswith(".gif"):

                            if url_match.startswith("//"):
                                return "https:" + url_match

                            return url_match

        except Exception:
            pass


        return "Not found"


    except Exception as e:

        print(
            f"Error extracting image URL: {e}"
        )

        return "Not found"


# ============================================================
# ROBOCRAZE SCRAPER
# ============================================================

def scrape_robocraze(search_query):
    """
    Scrape product details from RoboCraze based on
    a search query.
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
    # START CHROME
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
        # SCRAPE MULTIPLE PAGES
        # ====================================================

        for page in range(1, 3):

            if page == 1:

                url = (
                    "https://robocraze.com/search"
                    f"?q={encoded_query}"
                    "&options%5Bprefix%5D=last"
                )

            else:

                url = (
                    "https://robocraze.com/search"
                    f"?page={page}"
                    f"&q={encoded_query}"
                    "&options%5Bprefix%5D=last"
                )


            print(
                f"Scraping Page {page}: {url}"
            )

            print("-" * 50)


            # =================================================
            # OPEN PAGE
            # =================================================

            driver.get(url)


            # =================================================
            # WAIT FOR PAGE
            # =================================================

            wait = WebDriverWait(
                driver,
                15
            )

            wait.until(
                EC.presence_of_element_located(
                    (
                        By.CSS_SELECTOR,
                        ".product, "
                        ".product-item, "
                        "[data-product-id]"
                    )
                )
            )


            # =================================================
            # SCROLL
            # =================================================

            last_height = driver.execute_script(
                "return document.body.scrollHeight"
            )

            for i in range(2):

                driver.execute_script(
                    "window.scrollTo("
                    "0, document.body.scrollHeight"
                    ");"
                )

                time.sleep(2)

                new_height = driver.execute_script(
                    "return document.body.scrollHeight"
                )

                if new_height == last_height:
                    break

                last_height = new_height


            # =================================================
            # FIND PRODUCTS
            # =================================================

            products = driver.find_elements(
                By.CSS_SELECTOR,
                "li.product"
            )


            if not products:

                print(
                    f"No products found on page {page}"
                )

                if page == 1:
                    break

                continue


            print(
                f"Found {len(products)} products "
                f"on page {page}"
            )


            # =================================================
            # GET MONGODB COLLECTION
            # =================================================

            collection = get_collection_for_query(
                search_query
            )


            # =================================================
            # PROCESS PRODUCTS
            # =================================================

            for product in products:

                try:

                    # ------------------------------------------------
                    # DEFAULT VALUES
                    # ------------------------------------------------

                    name = "Not found"

                    actual_price = "Not found"

                    original_price = "Not found"

                    image = "Not found"

                    link = "Not found"

                    availability = "No"


                    # =================================================
                    # PRODUCT NAME
                    # =================================================

                    name_selectors = [
                        ".card-title",
                        "h3",
                        "[data-product-title]"
                    ]

                    for selector in name_selectors:

                        try:

                            name_elem = product.find_element(
                                By.CSS_SELECTOR,
                                selector
                            )

                            name = name_elem.text.strip()

                            if (
                                name
                                and name != "Not found"
                            ):
                                break

                        except Exception:
                            continue


                    # =================================================
                    # ACTUAL PRICE
                    # =================================================

                    try:

                        actual_price_elem = (
                            product.find_element(
                                By.CSS_SELECTOR,
                                ".price-item--sale"
                            )
                        )

                        actual_price = (
                            actual_price_elem
                            .text
                            .strip()
                        )

                    except Exception:

                        try:

                            actual_price_elem = (
                                product.find_element(
                                    By.CSS_SELECTOR,
                                    ".price-item--regular"
                                )
                            )

                            actual_price = (
                                actual_price_elem
                                .text
                                .strip()
                            )

                        except Exception:

                            actual_price = "Not found"


                    # =================================================
                    # ORIGINAL PRICE
                    # =================================================

                    try:

                        original_price_elem = (
                            product.find_element(
                                By.CSS_SELECTOR,
                                ".price__compare "
                                ".price-item--regular"
                            )
                        )

                        original_price = (
                            original_price_elem
                            .text
                            .strip()
                        )

                    except Exception:

                        original_price = "Not found"


                    # =================================================
                    # CLEAN PRICES
                    # =================================================

                    if "Save Rs." in actual_price:

                        actual_price = (
                            actual_price
                            .replace("Save Rs.", "")
                            .strip()
                        )


                    if "Save Rs." in original_price:

                        original_price = (
                            original_price
                            .replace("Save Rs.", "")
                            .strip()
                        )


                    # =================================================
                    # IMAGE
                    # =================================================

                    try:

                        image = extract_clean_image_url(
                            product
                        )

                    except Exception:

                        image = "Not found"


                    # =================================================
                    # PRODUCT LINK
                    # =================================================

                    link_selectors = [
                        "a[href*='/products/']",
                        "a.card-link"
                    ]

                    for selector in link_selectors:

                        try:

                            link_elem = product.find_element(
                                By.CSS_SELECTOR,
                                selector
                            )

                            href = link_elem.get_attribute(
                                "href"
                            )

                            if (
                                href
                                and "/products/" in href
                            ):

                                if href.startswith("http"):
                                    link = href

                                else:
                                    link = (
                                        "https://robocraze.com"
                                        + href
                                    )

                                break

                        except Exception:
                            continue


                    # =================================================
                    # AVAILABILITY
                    # =================================================

                    try:

                        add_to_cart_btn = (
                            product.find_element(
                                By.CSS_SELECTOR,
                                ".product-form__submit, "
                                ".quick-add__submit, "
                                "[data-btn-addtocart]"
                            )
                        )

                        btn_text = (
                            add_to_cart_btn
                            .text
                            .strip()
                            .lower()
                        )


                        if "add to cart" in btn_text:

                            availability = "Yes"

                        elif (
                            "notify me" in btn_text
                            or "sold out" in btn_text
                        ):

                            availability = "No"

                        else:

                            availability = "Unknown"


                    except Exception:

                        availability = "Unknown"


                    # =================================================
                    # PRINT DATA
                    # =================================================

                    print(
                        f"Product Name: {name}"
                    )

                    print(
                        f"Rs: {actual_price}"
                    )

                    if original_price != "Not found":

                        print(
                            f"Original Price: "
                            f"{original_price}"
                        )

                    print(
                        f"Availability: "
                        f"{availability}"
                    )

                    print(
                        f"Image URL: {image}"
                    )

                    print(
                        f"Product Link: {link}"
                    )

                    print("-" * 50)


                    # =================================================
                    # PRODUCT DOCUMENT
                    # =================================================

                    product_data = {

                        "name": name,

                        "price": actual_price,

                        "availability": availability,

                        "image_url": image,

                        "product_link": link,

                        "search_query": search_query,

                        "timestamp": time.time()
                    }


                    # =================================================
                    # INSERT INTO ATLAS
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


            print(
                f"Completed page {page}. "
                f"Scraped {products_scraped} "
                f"products so far."
            )

            time.sleep(2)


    except Exception as e:

        print(
            f"Error during scraping: {e}"
        )


    finally:

        driver.quit()

        print(
            f"Scraping complete. "
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

    scrape_robocraze(query)