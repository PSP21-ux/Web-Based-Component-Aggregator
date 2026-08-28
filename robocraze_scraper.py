from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import urllib.parse
import random
from pymongo import MongoClient
import re

def get_collection_for_query(search_query):
    """
    Returns a MongoDB collection for the given search query.
    """
    client = MongoClient("mongodb://localhost:27017/")  # Connect to MongoDB
    db = client["robocraze_db"]  # Database name
    collection_name = f"{search_query.lower().replace(' ', '_')}_products"  # Create a valid collection name
    return db[collection_name]

def extract_clean_image_url(product_element):
    """
    Extract a clean image URL from the product element using multiple strategies.
    """
    try:
        # Strategy 1: Try to find img element with multiple selectors
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
                img_elements = product_element.find_elements(By.CSS_SELECTOR, selector)
                for img_elem in img_elements:
                    # Try different attributes
                    attributes = ['src', 'data-src', 'data-original', 'data-lazy-src']
                    for attr in attributes:
                        url = img_elem.get_attribute(attr)
                        if url and url != "None" and not url.endswith(".gif") and len(url) > 10:
                            if url.startswith("//"):
                                return "https:" + url
                            return url
                    
                    # Try srcset
                    srcset = img_elem.get_attribute("srcset")
                    if srcset:
                        first_image = srcset.split(',')[0].strip().split(' ')[0]
                        if first_image and not first_image.endswith(".gif"):
                            if first_image.startswith("//"):
                                return "https:" + first_image
                            return first_image
            except:
                continue
        
        # Strategy 2: Look for image URLs in the product element's HTML
        try:
            product_html = product_element.get_attribute('outerHTML')
            
            # Pattern to match image URLs from robocraze CDN
            patterns = [
                r'src="(//robocraze\.com/cdn/shop/[^"]+\.(jpg|jpeg|png|webp)[^"]*)"',
                r'data-src="(//robocraze\.com/cdn/shop/[^"]+\.(jpg|jpeg|png|webp)[^"]*)"',
                r'srcset="([^"]*robocraze\.com/cdn/shop/[^"]+\.(jpg|jpeg|png|webp)[^"]*)"',
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, product_html)
                if matches:
                    # Get the first URL from the first match
                    url_match = matches[0][0] if isinstance(matches[0], tuple) else matches[0]
                    
                    # If it's srcset, extract first URL
                    if ' ' in url_match:
                        first_url = url_match.split(',')[0].split(' ')[0].strip()
                        if first_url and not first_url.endswith(".gif"):
                            if first_url.startswith("//"):
                                return "https:" + first_url
                            return first_url
                    else:
                        if not url_match.endswith(".gif"):
                            if url_match.startswith("//"):
                                return "https:" + url_match
                            return url_match
        except:
            pass
        
        return "Not found"
        
    except Exception as e:
        print(f"Error extracting image URL: {e}")
        return "Not found"

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
    chrome_options.add_argument("--headless")  # Comment out headless for debugging
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")

    # Initialize WebDriver
    driver = webdriver.Chrome(options=chrome_options)
    products_scraped = 0

    try:
        # Encode the search query for URL
        encoded_query = urllib.parse.quote(search_query)
        
        # Scrape multiple pages (2-3 pages)
        for page in range(1, 3):  # Pages 1, 2, 3
            if page == 1:
                url = f"https://robocraze.com/search?q={encoded_query}&options%5Bprefix%5D=last"
            else:
                url = f"https://robocraze.com/search?page={page}&q={encoded_query}&options%5Bprefix%5D=last"
            
            print(f"Scraping Page {page}: {url}")
            print("-" * 50)
            
            driver.get(url)

            # Wait for page to load
            wait = WebDriverWait(driver, 15)
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".product, .product-item, [data-product-id]")))

            # Scroll to load products
            last_height = driver.execute_script("return document.body.scrollHeight")
            for i in range(2):
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
                new_height = driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    break
                last_height = new_height

            # Find products
            products = driver.find_elements(By.CSS_SELECTOR, "li.product")
            
            if not products:
                print(f"No products found on page {page}")
                if page == 1:
                    break  # Stop if no products on first page
                continue

            print(f"Found {len(products)} products on page {page}")
            
            collection = get_collection_for_query(search_query)
            
            for product in products:
                try:
                    # Extract data
                    name = "Not found"
                    actual_price = "Not found"  # This will be the current price (Rs. 699)
                    original_price = "Not found"  # This will be the crossed out price (Rs. 869)
                    image = "Not found"
                    link = "Not found"
                    availability = "No"
                    
                    # Get product name
                    name_selectors = [".card-title", "h3", "[data-product-title]"]
                    for selector in name_selectors:
                        try:
                            name_elem = product.find_element(By.CSS_SELECTOR, selector)
                            name = name_elem.text.strip()
                            if name and name != "Not found":
                                break
                        except:
                            continue
                    
                    # Get prices - extract actual price and original price separately
                    try:
                        # Try to get the actual price (sale price)
                        actual_price_elem = product.find_element(By.CSS_SELECTOR, ".price-item--sale")
                        actual_price = actual_price_elem.text.strip()
                    except:
                        try:
                            # If no sale price, get regular price
                            actual_price_elem = product.find_element(By.CSS_SELECTOR, ".price-item--regular")
                            actual_price = actual_price_elem.text.strip()
                        except:
                            actual_price = "Not found"
                    
                    # Get original price (crossed out price)
                    try:
                        original_price_elem = product.find_element(By.CSS_SELECTOR, ".price__compare .price-item--regular")
                        original_price = original_price_elem.text.strip()
                    except:
                        original_price = "Not found"
                    
                    # Clean up prices - remove "Save Rs." text if present
                    if "Save Rs." in actual_price:
                        actual_price = actual_price.replace("Save Rs.", "").strip()
                    if "Save Rs." in original_price:
                        original_price = original_price.replace("Save Rs.", "").strip()
                    
                    # Get image URL using our improved extraction function
                    try:
                        image = extract_clean_image_url(product)
                    except:
                        image = "Not found"
                    
                    # Get product link
                    link_selectors = ["a[href*='/products/']", "a.card-link"]
                    for selector in link_selectors:
                        try:
                            link_elem = product.find_element(By.CSS_SELECTOR, selector)
                            href = link_elem.get_attribute("href")
                            if href and "/products/" in href:
                                link = href if href.startswith("http") else "https://robocraze.com" + href
                                break
                        except:
                            continue
                    
                    # Check availability - look for "Add to cart" or "Notify me" buttons
                    try:
                        # Look for add to cart button
                        add_to_cart_btn = product.find_element(By.CSS_SELECTOR, ".product-form__submit, .quick-add__submit, [data-btn-addtocart]")
                        btn_text = add_to_cart_btn.text.strip().lower()
                        if "add to cart" in btn_text:
                            availability = "Yes"
                        elif "notify me" in btn_text or "sold out" in btn_text:
                            availability = "No"
                        else:
                            availability = "Unknown"
                    except:
                        availability = "Unknown"
                    
                    # Print the extracted data
                    print(f"Product Name: {name}")
                    print(f"Rs: {actual_price}")
                    if original_price != "Not found":
                        print(f"Original Price: {original_price}")
                    print(f"Availability: {availability}")
                    print(f"Image URL: {image}")
                    print(f"Product Link: {link}")
                    print("-" * 50)
                    
                    # Save to MongoDB
                    product_data = {
                        "name": name,
                        "price": actual_price,
                    
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
                    continue

            print(f"Completed page {page}. Scraped {products_scraped} products so far.")
            time.sleep(2)  # Wait before next page

    except Exception as e:
        print(f"Error during scraping: {e}")

    finally:
        driver.quit()
        print(f"Scraping complete. Total products scraped: {products_scraped}")

# Example usage
if __name__ == "__main__":
    query = input("Enter search term: ")
    scrape_robocraze(query)