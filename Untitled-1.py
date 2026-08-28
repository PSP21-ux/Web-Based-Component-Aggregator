from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
from selenium.webdriver.chrome.options import Options

# Setup Chrome options
chrome_options = Options()
chrome_options.add_argument("--disable-notifications")
chrome_options.add_argument("--disable-popup-blocking")

# Start browser with options
driver = webdriver.Chrome(options=chrome_options)

try:
    # Open IRCTC train search page
    driver.get("https://www.irctc.co.in/nget/train-search")
    
    # Wait for page to load completely
    WebDriverWait(driver, 30).until(
        EC.presence_of_element_located((By.CLASS_NAME, "search_btn"))
    )
    
    # Additional wait for dynamic content
    time.sleep(3)
    
    # Method 1: Try to find FROM input using multiple selectors
    from_input = None
    selectors_to_try = [
        "input.ui-autocomplete-input[aria-controls*='list']:first-of-type",
        "input.ui-autocomplete-input[role='searchbox']:first-of-type", 
        "input[aria-autocomplete='list']:first-of-type",
        "span.ui-autocomplete input[type='text']:first-of-type",
        "input.ui-inputtext.ui-autocomplete-input:first-of-type"
    ]
    
    for selector in selectors_to_try:
        try:
            from_input = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
            )
            print(f"Found FROM input using selector: {selector}")
            break
        except:
            continue
    
    if not from_input:
        raise Exception("Could not locate FROM input field")
    
    # Clear and enter source station
    from_input.click()
    time.sleep(1)
    from_input.clear()
    from_input.send_keys("csmt")
    
    # Wait for autocomplete dropdown to appear
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "ul[role='listbox'], .ui-autocomplete-panel, .ui-autocomplete-list"))
    )
    
    # Wait a moment for the list to populate
    time.sleep(2)
    
    # Try to click on the first suggestion
    try:
        # Method 1: Click on first list item
        first_option = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "ul[role='listbox'] li:first-child, .ui-autocomplete-panel li:first-child"))
        )
        first_option.click()
        print("Clicked on first autocomplete option")
    except:
        # Method 2: Use keyboard navigation
        from_input.send_keys(Keys.ARROW_DOWN)
        from_input.send_keys(Keys.ENTER)
        print("Used keyboard navigation for FROM field")
    
    time.sleep(2)
    
    # Find TO input field using the specific HTML structure
    to_input = None
    to_selectors = [
        "span.ng-tns-c57-9.ui-autocomplete input[aria-controls='pr_id_2_list']",
        "input[aria-controls='pr_id_2_list']",
        "span.ui-autocomplete input[role='searchbox'][aria-controls*='pr_id_2']",
        "input.ui-autocomplete-input[aria-controls*='pr_id_2']"
    ]
    
    for selector in to_selectors:
        try:
            to_input = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
            )
            print(f"Found TO input using selector: {selector}")
            break
        except:
            continue
    
    if not to_input:
        raise Exception("Could not locate TO input field")
    
    # Clear and enter destination station
    to_input.click()
    time.sleep(1)
    to_input.clear()
    to_input.send_keys("Srisailam")
    
    # Wait for autocomplete dropdown
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "ul[role='listbox'], .ui-autocomplete-panel, .ui-autocomplete-list"))
    )
    
    time.sleep(2)
    
    # Click on first suggestion for TO field
    try:
        # Method 1: Click on first list item
        first_to_option = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "ul[role='listbox'] li:first-child, .ui-autocomplete-panel li:first-child"))
        )
        first_to_option.click()
        print("Clicked on first autocomplete option for TO field")
    except:
        # Method 2: Use keyboard navigation
        to_input.send_keys(Keys.ARROW_DOWN)
        to_input.send_keys(Keys.ENTER)
        print("Used keyboard navigation for TO field")
    
    # Handle date selection
    print("Looking for date input field...")
    time.sleep(2)
    
    try:
        # Find date input using the specific HTML structure
        date_selectors = [
            "span.ng-tns-c58-10.ui-calendar input[type='text']",
            "span.ui-calendar input[type='text']",
            "input.ui-inputtext.ng-tns-c58-10",
            "span.ui-calendar input.ui-inputtext"
        ]
        
        date_input = None
        for selector in date_selectors:
            try:
                date_input = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                )
                print(f"Found date input using selector: {selector}")
                break
            except:
                continue
        
        if date_input:
            date_input.click()
            time.sleep(1)
            # You can modify this date as needed (format might be DD-MM-YYYY or similar)
            # For now, let's try clicking on today's date or leaving it as default
            print("Date field clicked - using default date")
        else:
            print("Could not find date input field, proceeding without date selection")
    
    except Exception as e:
        print(f"Date selection failed: {str(e)}")
    
    # Click search button
    print("Looking for search button...")
    time.sleep(2)
    
    try:
        search_selectors = [
            "button.search_btn",
            ".search_btn",
            "button[type='submit']",
            "input[type='submit']",
            "button.btn.btn-primary",
            "//button[contains(text(), 'Search') or contains(text(), 'SEARCH')]"
        ]
        
        search_button = None
        for selector in search_selectors:
            try:
                if selector.startswith("//"):
                    # XPath selector
                    search_button = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                else:
                    # CSS selector
                    search_button = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                print(f"Found search button using selector: {selector}")
                break
            except:
                continue
        
        if search_button:
            search_button.click()
            print("Search button clicked!")
            
            # Wait for search results to load
            print("Waiting for search results...")
            time.sleep(10)
        else:
            print("Could not find search button")
    
    except Exception as e:
        print(f"Search button click failed: {str(e)}")
    
except Exception as e:
    print(f"An error occurred: {str(e)}")
    
finally:
    # Close the browser
    driver.quit()
    print("Browser closed")