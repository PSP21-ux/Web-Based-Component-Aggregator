from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import urllib.parse
import random
from pymongo import MongoClient

def get_collection_for_query(search_query):
    """
    Returns a MongoDB collection for the given search query.
    """
    client = MongoClient("mongodb://localhost:27017/")  # Connect to MongoDB
    db = client["robocraze_db"]  # Database name
    collection_name = f"{search_query.lower().replace(' ', '_')}_products"  # Create a valid collection name
    return db[collection_name]

def scrape_robocraze(search_query):
    """
    Scrape product details from RoboCraze based on a search query.
    
    Args:
        search_query (str): The search term to look for.
    """
    # Setup Chrome options
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")  # Bypass detection
    chrome_options.add_argument("--start-maximized")  # Open browser in maximized mode
    chrome_options.add_argument("--headless")  # Run in headless mode (comment this line to see the browser)
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")  # Set User-Agent

    # Initialize WebDriver
    driver = webdriver.Chrome(options=chrome_options)
    products_scraped = 0  # Initialize the variable here

    try:
        # Encode the search query for URL
        encoded_query = urllib.parse.quote(search_query)
        
        # Target URL with dynamic search query
        url = f"https://robocraze.com/search?q={encoded_query}&options%5Bprefix%5D=last"
        
        print(f"Searching for: {search_query}")
        print(f"URL: {url}")
        print("-" * 50)
        
        driver.get(url)

        # Wait for the product grid to load
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "ul.grid.product-grid")))

        # Scroll down to load more products (if needed)
        last_height = driver.execute_script("return document.body.scrollHeight")
        while True:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(random.uniform(2, 5))  # Random delay between 2 and 5 seconds
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height

        # Extract product details from the specific <ul> element
        product_grid = driver.find_element(By.CSS_SELECTOR, "ul.grid.product-grid")
        products = product_grid.find_elements(By.CSS_SELECTOR, "li.grid__item")
        
        print(f"Found {len(products)} products for '{search_query}'")
        print("-" * 50)

        collection = get_collection_for_query(search_query)
        
        for product in products:
            try:
                # Extract product name
                name = product.find_element(By.CSS_SELECTOR, "h3.card__heading a").text.strip()
                
                # Extract product price
                try:
                    price = product.find_element(By.CSS_SELECTOR, ".price-item--sale").text.strip()
                except:
                    price = "Price not found"
                    
                # Extract product image URL
                try:
                    image = product.find_element(By.CSS_SELECTOR, "img.motion-reduce").get_attribute("src")
                except:
                    image = "Image URL not found"
                
                # Extract product link
                try:
                    link = product.find_element(By.CSS_SELECTOR, "h3.card__heading a").get_attribute("href")
                    # Ensure the link is a full URL
                    if not link.startswith("https://"):
                        link = "https://robocraze.com" + link
                except:
                    link = "Link not found"
                
                # Extract availability
                try:
                    availability_text = product.find_element(By.CSS_SELECTOR, ".quick-add__submit").text.strip()
                    availability = "Yes" if "Add" in availability_text else "No"
                except:
                    availability = "Unknown"
                
                # Print the extracted data
                print(f"Product Name: {name}")
                print(f"Price: {price}")
                print(f"Image URL: {image}")
                print(f"Availability: {availability}")
                print(f"Product Link: {link}")
                print("-" * 50)
                
                # Save the product data to MongoDB
                product_data = {
                    "name": name,
                    "price": price,
                    "availability": availability,
                    "image_url": image,
                    "product_link": link,  # Add product link to the data
                    "search_query": search_query,
                    "timestamp": time.time()
                }
                collection.insert_one(product_data)  # Insert into MongoDB
                products_scraped += 1  # Increment the counter

            except Exception as e:
                # Silent error handling - just move to the next product
                print(f"Error processing product: {e}")
                continue

    except Exception as e:
        print("Error:", e)

    finally:
        # Close the browser after scraping
        driver.quit()
        print(f"Scraping complete from RoboCraze. Total products scraped: {products_scraped}")

# Example usage
if __name__ == "__main__":
    # Get search query from user
    query = input("Enter search term: ")
    scrape_robocraze(query)