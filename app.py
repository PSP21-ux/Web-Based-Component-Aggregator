from flask import Flask, request, jsonify, render_template
from pymongo import MongoClient
import threading
import time
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pyngrok import ngrok

# Set your ngrok authtoken (already done)
ngrok.set_auth_token("2wdVzcdEpdvPLc9cYrMmBB0yPxW_6Au8sqE7DSkoQXfPe6pWr")

# Set your reserved/static domain
CUSTOM_DOMAIN = "powerful-maggot-definitely.ngrok-free.app"


# Import scraping functions
from robu_scraper import scrape_robu
from robocraze_scraper import scrape_robocraze
from amazon_scraper import scrape_amazon
from alertscraping import scrape_product_availability
from gemini_chatbot import ask_luffybot



# Import the new ranking function
from ml_ranker import rank_scraped_products

app = Flask(__name__)

# MongoDB connection
client = MongoClient("mongodb://localhost:27017/")

# Define databases
robu_db = client["robu_db"]
robocraze_db = client["robocraze_db"]
amazon_db = client["amazon_db"]

# Combined database for alerts
alerts_db = client["alerts_db"]
alerts_collection = alerts_db["alerts"]

chatlog_db = client["chatlog_db"]
chatlog_collection = chatlog_db["chat_messages"]


# Configuration for data freshness (in hours)
DATA_FRESHNESS_HOURS = 24

# Email configuration
EMAIL_HOST = "smtp.gmail.com"  # Change this to your SMTP server
EMAIL_PORT = 587
EMAIL_USERNAME = "multisiteproductfinder@gmail.com"  # Change to your email
EMAIL_PASSWORD = "sfbw zncq bidv osoa"     # Change to your app password

def send_email(recipient, subject, message):
    """Send an email to the specified recipient."""
    try:
        msg = MIMEMultipart()
        msg['From'] = "Multi-Site Product Finder <multisiteproductfinder@gmail.com>"
        msg['To'] = recipient
        msg['Subject'] = subject
        msg['Reply-To'] = "multisiteproductfinder@gmail.com"

        msg.attach(MIMEText(message, 'html'))

        server = smtplib.SMTP(EMAIL_HOST, EMAIL_PORT)
        server.starttls()
        server.login(EMAIL_USERNAME, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()

        print(f"Email sent to {recipient}")
        return True
    except Exception as e:
        print(f"Failed to send email: {str(e)}")
        return False


def get_collection_for_query(db, search_query):
    """
    Returns a MongoDB collection for the given search query.
    """
    collection_name = f"{search_query.lower().replace(' ', '_')}_products"  # Create a valid collection name
    return db[collection_name]

def get_existing_results(search_query):
    """
    Check if we have recent results for this search query.
    Returns results if found and still fresh, None otherwise.
    """
    # Calculate the timestamp threshold for fresh data
    freshness_threshold = time.time() - (DATA_FRESHNESS_HOURS * 3600)
    
    all_products = []
    found_results = False
    
    # Check if we have recent data from Robu.in
    robu_collection = get_collection_for_query(robu_db, search_query)
    robu_products = list(robu_collection.find({
        "timestamp": {"$gt": freshness_threshold}
    }))
    
    if robu_products:
        found_results = True
        for product in robu_products:
            product["_id"] = str(product["_id"])
            product["source"] = "Robu.in"
            all_products.append(product)
    
    # Check if we have recent data from RoboCraze
    robocraze_collection = get_collection_for_query(robocraze_db, search_query)
    robocraze_products = list(robocraze_collection.find({
        "timestamp": {"$gt": freshness_threshold}
    }))
    
    if robocraze_products:
        found_results = True
        for product in robocraze_products:
            product["_id"] = str(product["_id"])
            product["source"] = "RoboCraze"
            all_products.append(product)
    
    # Check if we have recent data from Amazon
    amazon_collection = get_collection_for_query(amazon_db, search_query)
    amazon_products = list(amazon_collection.find({
        "timestamp": {"$gt": freshness_threshold}
    }))
    
    if amazon_products:
        found_results = True
        for product in amazon_products:
            product["_id"] = str(product["_id"])
            product["source"] = "Amazon.in"
            all_products.append(product)
    
    # If we have fresh results from all sources, return them
    if found_results:
        print(f"Found fresh existing results for: {search_query}")
        return all_products
    
    # Otherwise return None to indicate we need to scrape
    return None

def scrape_all_sites(search_query):
    """
    Unified function to scrape all three websites for product data.
    Returns status for frontend updates.
    """
    print(f"Starting unified search for: {search_query}")
    print("=" * 60)
    
    # First, check if we already have fresh results
    existing_results = get_existing_results(search_query)
    if existing_results:
        return existing_results
    
    # If we don't have fresh results, clear any old results for this query
    # to prevent mixing of old and new data
    robu_collection = get_collection_for_query(robu_db, search_query)
    robocraze_collection = get_collection_for_query(robocraze_db, search_query)
    amazon_collection = get_collection_for_query(amazon_db, search_query)
    
    robu_collection.delete_many({})
    robocraze_collection.delete_many({})
    amazon_collection.delete_many({})
    
    # Dictionary to track status of each scraper
    scraper_status = {
        "robu": "pending",
        "robocraze": "pending",
        "amazon": "pending"
    }
    
    # Thread function for robu.in
    def run_robu_scraper():
        try:
            print("Starting Robu.in scraper...")
            scraper_status["robu"] = "running"
            # Call the scrape_robu function - it will save to its own database
            scrape_robu(search_query)
            scraper_status["robu"] = "completed"
            print("Completed Robu.in scraping")
        except Exception as e:
            scraper_status["robu"] = "error"
            print(f"Error in Robu.in scraper: {e}")

    # Thread function for robocraze.com
    def run_robocraze_scraper():
        try:
            print("Starting RoboCraze scraper...")
            scraper_status["robocraze"] = "running"
            # Call the scrape_robocraze function - it will save to its own database
            scrape_robocraze(search_query)
            scraper_status["robocraze"] = "completed"
            print("Completed RoboCraze scraping")
        except Exception as e:
            scraper_status["robocraze"] = "error"
            print(f"Error in RoboCraze scraper: {e}")

    # Thread function for amazon.in
    def run_amazon_scraper():
        try:
            print("Starting Amazon.in scraper...")
            scraper_status["amazon"] = "running"
            # Call the scrape_amazon function - it will save to its own database
            scrape_amazon(search_query)
            scraper_status["amazon"] = "completed"
            print("Completed Amazon.in scraping")
        except Exception as e:
            scraper_status["amazon"] = "error"
            print(f"Error in Amazon.in scraper: {e}")

    # Create and start threads
    threads = [
        threading.Thread(target=run_robu_scraper),
        threading.Thread(target=run_robocraze_scraper),
        threading.Thread(target=run_amazon_scraper)
    ]

    # Start all threads
    for thread in threads:
        thread.start()

    # Wait for all threads to complete
    for thread in threads:
        thread.join()

    print("=" * 60)
    print(f"Completed unified search for: {search_query}")

    # Retrieve all results from MongoDB - from all three databases
    all_products = []
    
    # Get products from Robu.in
    robu_products = list(robu_collection.find({}))
    for product in robu_products:
        product["_id"] = str(product["_id"])  # Convert ObjectId to string
        product["source"] = "Robu.in"
        all_products.append(product)
    
    # Get products from RoboCraze
    robocraze_products = list(robocraze_collection.find({}))
    for product in robocraze_products:
        product["_id"] = str(product["_id"])  # Convert ObjectId to string
        product["source"] = "RoboCraze"
        all_products.append(product)
    
    # Get products from Amazon
    amazon_products = list(amazon_collection.find({}))
    for product in amazon_products:
        product["_id"] = str(product["_id"])  # Convert ObjectId to string
        product["source"] = "Amazon.in"
        all_products.append(product)
    
    return all_products

def check_product_availability():
    """
    Daily job: Check all alerts by scraping product URLs for availability.
    """
    print("🔁 Running daily product availability check...")

    # Get all alerts that are still active
    alerts = list(alerts_collection.find({"alert_enabled": True}))

    for alert in alerts:
        product_name = alert["product_name"]
        product_url = alert.get("product_url", "#")
        source = alert.get("source", "Unknown")
        email = alert["email"]
        price = alert.get("price", "N/A")
        image_url = alert.get("image_url", "")

        print(f"🧐 Checking availability for {product_name} ({source})")

        try:
            is_available = scrape_product_availability(product_url)
        except Exception as e:
            print(f"⚠️ Error checking product: {e}")
            continue

        if is_available:
            print(f"✅ Available: {product_name}")

            # Send alert email
            subject = f"🎉 {product_name} is now available!"
            message = f"""
            <html>
            <body>
                <h2>Product Alert: Item Now Available!</h2>
                <p>Good news! The product you were waiting for is now available:</p>
                <p><strong>{product_name}</strong> from {source}</p>
                <p>Price: {price}</p>
                <p><a href="{product_url}">Click here to view the product</a></p>
                {'<img src="' + image_url + '" width="300"/>' if image_url else ''}
                <p>Thank you for using our service!</p>
            </body>
            </html>
            """
            send_email(email, subject, message)

            # Mark the alert as sent (disabled)
            alerts_collection.update_one(
                {"_id": alert["_id"]},
                {"$set": {"alert_enabled": False, "availability": "Yes"}}
            )

        else:
            print(f"🚫 Still not available: {product_name}")


# Schedule the availability check to run periodically
def start_availability_checker():
    """Start the availability checker in a background thread."""
    check_thread = threading.Thread(target=availability_checker_loop)
    check_thread.daemon = True
    check_thread.start()

def availability_checker_loop():
    """Run the availability checker in a loop."""
    while True:
        try:
            check_product_availability()
        except Exception as e:
            print(f"Error in availability checker: {e}")
        
        # Sleep for 1 hour before checking again
        time.sleep(86400)  # 3600 seconds = 1 hour

@app.route("/")
def home():
    return render_template("index.html")

# Only one search route - the more complete version with ranking
@app.route("/search", methods=["POST"])
def search():
    search_query = request.form.get("query")
    if not search_query:
        return jsonify({"error": "Search query is required"}), 400
    
    # Check for force_refresh parameter
    force_refresh = request.form.get("force_refresh") == "true"

    # Get user preferences for ranking weights (optional)
    weights = {
        'relevance': float(request.form.get("relevance_weight", 0.4)),
        'price': float(request.form.get("price_weight", 0.3)),
        'availability': float(request.form.get("availability_weight", 0.3))
    }
    limit = int(request.form.get("limit", 10))  # Default to 10 if none provided


    # Use the unified scraper function with force_refresh option

    if force_refresh:
        # Clear existing data for this query
        robu_collection = get_collection_for_query(robu_db, search_query)
        robocraze_collection = get_collection_for_query(robocraze_db, search_query)
        amazon_collection = get_collection_for_query(amazon_db, search_query)
        
        robu_collection.delete_many({})
        robocraze_collection.delete_many({})
        amazon_collection.delete_many({})
        
        # Get fresh results
        results = scrape_all_sites(search_query)
    else:
        # Use existing results if available, otherwise scrape
        results = get_existing_results(search_query)
        if not results:
            results = scrape_all_sites(search_query)
    
    # Apply Hugging Face RAG-based ranking to the results
    ranked_results = rank_scraped_products(results, search_query)
    ranked_results = rank_scraped_products(results, search_query)
    return jsonify(ranked_results)

@app.route("/status", methods=["GET"])
def get_status():
    # This endpoint could be used to check the status of scraping operations
    # For now, we'll just return a simple status
    return jsonify({"status": "ready"})

@app.route("/enable_alert", methods=["POST"])
def enable_alert():
    product_name = request.form.get("product_name")
    product_url = request.form.get("product_url")
    availability = request.form.get("availability")
    source = request.form.get("source")
    email = request.form.get("email")
    alert_id = request.form.get("alert_id")
    image_url = request.form.get("image_url", "")  # NEW FIELD

    if not product_name or not product_url or not availability or not email:
        return jsonify({"error": "Product details and email are required"}), 400

    alerts_collection.insert_one({
        "alert_id": alert_id,
        "product_name": product_name,
        "product_url": product_url,
        "availability": availability,
        "source": source,
        "email": email,
        "image_url": image_url,
        "alert_enabled": True,
        "timestamp": time.time()
    })

    subject = f"Alert Enabled for {product_name}"
    message = f"""
    <html>
    <body>
    <h2>Product Alert Confirmation</h2>
    <p>You have successfully enabled an alert for:</p>
    <p><strong>{product_name}</strong> from {source}</p>
    <p>We will notify you when this product becomes available.</p>
    <p>Thank you for using our service!</p>
    </body>
    </html>
    """
    send_email(email, subject, message)

    return jsonify({"message": "Alert enabled for product. You will receive an email confirmation."})

@app.route("/remove_alert", methods=["POST"])
def remove_alert():
    alert_id = request.form.get("alert_id")
    
    if not alert_id:
        return jsonify({"error": "Alert ID is required"}), 400
    
    # Remove from database
    alerts_collection.delete_one({"alert_id": alert_id})
    
    return jsonify({"message": "Alert removed successfully"})

@app.route("/get_alerts", methods=["POST"])
def get_alerts():
    email = request.form.get("email")
    
    if not email:
        return jsonify({"error": "Email is required"}), 400
    
    # Get alerts for this email
    alerts = list(alerts_collection.find({"email": email}))
    
    # Convert ObjectId to string
    for alert in alerts:
        alert["_id"] = str(alert["_id"])
    
    return jsonify(alerts)

@app.route("/chatbot", methods=["POST"])
def chatbot():
    data = request.get_json()
    user_message = data.get("message", "")
    bot_type = data.get("bot", "luffy")

    if not user_message:
        return jsonify({"error": "Message is required"}), 400

    # Log to terminal
    print(f"[CHATBOT] User ({bot_type}): {user_message}")

    # Get response from Gemini
    reply = ask_luffybot(user_message, bot_type)

    # Save to MongoDB
    chatlog_collection.insert_one({
        "bot_type": bot_type,
        "user_message": user_message,
        "bot_reply": reply,
        "timestamp": time.time()
    })

    return jsonify({"reply": reply})



if __name__ == "__main__":
    # Start availability checker in background
    start_availability_checker()

    # Start ngrok tunnel with your reserved domain
    try:
        public_url = ngrok.connect(
            addr=80,
            bind_tls=True,
            domain=CUSTOM_DOMAIN
        )
        print(f"\n🚀 Your app is live at: https://{CUSTOM_DOMAIN}\n")
    except Exception as e:
        print(f"❌ Failed to open tunnel on static domain: {e}")
        public_url = None

    # Start Flask
    try:
        app.run(host="0.0.0.0", port=80)
    finally:
        # Ensure tunnel is killed cleanly
        if public_url:
            ngrok.disconnect(public_url)
        ngrok.kill()
