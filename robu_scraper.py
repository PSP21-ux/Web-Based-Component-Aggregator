from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
import time
import urllib.parse
import random
from pymongo import MongoClient

def get_collection_for_query(search_query):
    """Returns a MongoDB collection for the given search query."""
    client = MongoClient("mongodb://localhost:27017/")
    db = client["robu_db"]
    collection_name = f"{search_query.lower().replace(' ', '_')}_products"
    return db[collection_name]

def scrape_robu(search_query):
    """Scrape product details from Robu.in based on a search query."""
    
    # Setup Chrome options
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--headless")  # Run in headless mode
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")

    # Initialize WebDriver
    driver = webdriver.Chrome(options=chrome_options)
    products_scraped = 0

    try:
        encoded_query = urllib.parse.quote(search_query)
        url = f"https://robu.in/?s={encoded_query}&post_type=product"
        print(f"Searching for: {search_query}")
        print(f"URL: {url}\n{'-' * 50}")

        driver.get(url)

        # Wait for the product grid to load
        wait = WebDriverWait(driver, 15)
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "ul.products")))
        except TimeoutException:
            print("Timeout waiting for product grid. Checking for 'No products' message...")
            try:
                no_results = driver.find_element(By.CSS_SELECTOR, ".woocommerce-info")
                if "No products were found" in no_results.text:
                    print("No products found.")
                    return
            except NoSuchElementException:
                print("Unknown issue. Taking a screenshot for debugging...")
                driver.save_screenshot(f"robu_search_{search_query}.png")
                return

        # Scroll to load more products (if needed)
        last_height = driver.execute_script("return document.body.scrollHeight")
        for _ in range(5):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(random.uniform(1, 2))
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height

        print("Finished scrolling. Extracting products...")

        # Extract product details
        products = driver.find_elements(By.CSS_SELECTOR, "li.product.type-product")
        if not products:
            print("No products found with main selector. Trying alternative selector...")
            products = driver.find_elements(By.CSS_SELECTOR, "ul.products li")
        
        print(f"Found {len(products)} products for '{search_query}'\n{'-' * 50}")
        
        collection = get_collection_for_query(search_query)

        for product in products:
            try:
                try:
                    name_element = product.find_element(By.CSS_SELECTOR, "a.woocommerce-LoopProduct-link h2.woocommerce-loop-product__title")
                    name = name_element.text.strip()
                    if not name:
                         name = name_element.get_attribute("textContent").strip()
                except Exception as e:
                    print("ERROR:", e)
                    name = "Product name not found"

                    print("Product Name:", name)

                # Extract price
                try:
                    price = product.find_element(By.CSS_SELECTOR, "span.price").text.strip()
                except NoSuchElementException:
                    try:
                        price = product.find_element(By.CSS_SELECTOR, ".price").text.strip()
                    except NoSuchElementException:
                        price = "Price not found"

                # Extract product image
                try:
                    image = product.find_element(By.CSS_SELECTOR, "img").get_attribute("src")
                except NoSuchElementException:
                    image = "Image URL not found"

                # Extract product link
                try:
                    link = product.find_element(By.CSS_SELECTOR, "a.woocommerce-LoopProduct-link").get_attribute("href")
                except NoSuchElementException:
                    link = "Link not found"

                # Check stock availability
                try:
                    add_to_cart_button = product.find_element(By.CSS_SELECTOR, "div.add-to-cart-wrap a")
                    button_text = add_to_cart_button.text.strip().lower()

                    if "add to cart" in button_text:
                        availability = "Yes"
                    elif "read more" in button_text:
                        availability = "No"
                    else:
                        availability = "Unknown"
                except NoSuchElementException:
                    availability = "Unknown"


                # Print extracted data
                print(f"Product Name: {name}")
                print(f"Price: {price}")
                print(f"Image URL: {image}")
                print(f"Availability: {availability}")
                print(f"Product Link: {link}")
                print("-" * 50)

                # Save data to MongoDB
                product_data = {
                    "name": name,
                    "price": price,
                    "availability": availability,
                    "image_url": image,
                    "product_link": link,
                    "search_query": search_query,
                    "timestamp": time.time()
                }
                collection.insert_one(product_data)
                products_scraped += 1

            except Exception as e:
                print(f"Error processing product: {e}")
                print(f"Successfully scraped {products_scraped} products before error.")
                break

    except Exception as e:
        print(f"Error during scraping: {e}")
        try:
            driver.save_screenshot(f"robu_error_{search_query}.png")
        except:
            pass

    finally:
        driver.quit()
        print(f"Scraping complete. Total products scraped: {products_scraped}")

# Example usage
if __name__ == "__main__":
    query = input("Enter search term: ")
    scrape_robu(query)
