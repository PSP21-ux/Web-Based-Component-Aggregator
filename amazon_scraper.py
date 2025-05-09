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
    """
    Returns a MongoDB collection for the given search query.
    """
    client = MongoClient("mongodb://localhost:27017/")
    db = client["amazon_db"]  # Use the Amazon database
    collection_name = f"{search_query.lower().replace(' ', '_')}_products"  # Create a valid collection name
    return db[collection_name]

def scrape_amazon(search_query):
    """
    Scrape product details from Amazon.in based on a search query.
    Includes both organic and sponsored products.
    """
    # Setup Chrome options
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")  # Bypass detection
    chrome_options.add_argument("--start-maximized")  # Open browser in maximized mode
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")  # Set User-Agent

    # Initialize WebDriver
    driver = webdriver.Chrome(options=chrome_options)
    products_scraped = 0

    try:
        # Encode the search query for URL
        encoded_query = urllib.parse.quote(search_query)
        
        # Target URL with dynamic search query
        url = f"https://www.amazon.in/s?k={encoded_query}"
        
        print(f"Searching for: {search_query}")
        print(f"URL: {url}")
        print("-" * 50)
        
        driver.get(url)

        # Wait for products to load
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.s-main-slot.s-result-list.s-search-results")))

        # Scroll down to load more products (if needed)
        last_height = driver.execute_script("return document.body.scrollHeight")
        while True:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(random.uniform(2, 5))  # Random delay between 2 and 5 seconds
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height

        # Extract product details
        products = driver.find_elements(By.CSS_SELECTOR, "div.s-main-slot.s-result-list.s-search-results > div[data-component-type='s-search-result']")
        
        print(f"Found {len(products)} products for '{search_query}'")
        print("-" * 50)
        
        # Get the collection for the search query
        collection = get_collection_for_query(search_query)
        
        for product in products:
            try:
                # Check if the product is sponsored
                try:
                    is_sponsored = product.find_element(By.CSS_SELECTOR, "span.puis-sponsored-label-text").text == "Sponsored"
                except NoSuchElementException:
                    is_sponsored = False

                # Extract product name (try multiple selectors)
                try:
                    # Try the first selector (new structure)
                    name = product.find_element(By.CSS_SELECTOR, "h2.a-size-medium.a-spacing-none.a-color-base.a-text-normal span").text
                except NoSuchElementException:
                    try:
                        # Fallback to the second selector (previous structure)
                        name = product.find_element(By.CSS_SELECTOR, "h2.a-size-base-plus.a-spacing-none.a-color-base.a-text-normal span").text
                    except NoSuchElementException:
                        name = "Name not found"
                
                # Extract product price
                try:
                    price = product.find_element(By.CSS_SELECTOR, "span.a-price-whole").text
                except NoSuchElementException:
                    price = "Price not found"
                    
                # Extract product image URL
                try:
                    image = product.find_element(By.CSS_SELECTOR, "img.s-image").get_attribute("src")
                except NoSuchElementException:
                    image = "Image URL not found"
                
                # Extract product link
                try:
                    link = product.find_element(By.CSS_SELECTOR, "a.a-link-normal.s-no-outline").get_attribute("href")
                    if not link.startswith("https://"):
                        link = "https://www.amazon.in" + link
                except NoSuchElementException:
                    link = "Link not found"
                
                # Check availability
                try:
                    availability_text = product.text
                    availability = "No" if "Currently unavailable" in availability_text else "Yes"
                except:
                    availability = "Unknown"
                
                # Print the extracted data
                print(f"Product Name: {name}")
                print(f"Price: {price}")
                print(f"Image URL: {image}")
                print(f"Availability: {availability}")
                print(f"Sponsored: {'Yes' if is_sponsored else 'No'}")
                print(f"Product Link: {link}")
                print("-" * 50)
                
                # Save the product data to MongoDB
                product_data = {
                    "name": name,
                    "price": price,
                    "availability": availability,
                    "image_url": image,
                    "product_link": link,
                    "is_sponsored": is_sponsored,  # Add this field to indicate sponsored products
                    "search_query": search_query,
                    "timestamp": time.time()
                }
                collection.insert_one(product_data)  # Insert into MongoDB
                products_scraped += 1

            except Exception as e:
                # If an error occurs, print the error message and continue to the next product
                print(f"Error processing product: {e}")
                continue

    except Exception as e:
        print(f"Error during scraping: {e}")

    finally:
        driver.quit()
        print(f"Scraping complete from amazon. Total products scraped: {products_scraped}")

if __name__ == "__main__":
    # Get search query from user
    query = input("Enter search term: ")
    scrape_amazon(query)