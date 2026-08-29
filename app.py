from flask import Flask, request, jsonify, render_template
from pymongo import MongoClient
import threading
import time
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from dotenv import load_dotenv


# ============================================================
# ENVIRONMENT VARIABLES
# ============================================================

load_dotenv()


# ============================================================
# EMAIL CONFIGURATION
# ============================================================

EMAIL_USERNAME = os.getenv("EMAIL_USERNAME")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")


# ============================================================
# IMPORT SCRAPING FUNCTIONS
# ============================================================

from robu_scraper import scrape_robu
from robocraze_scraper import scrape_robocraze
from amazon_scraper import scrape_amazon
from alertscraping import scrape_product_availability
from gemini_chatbot import ask_luffybot


# ============================================================
# IMPORT RANKING FUNCTION
# ============================================================

from ml_ranker import rank_scraped_products


# ============================================================
# FLASK APP
# ============================================================

app = Flask(__name__)


# ============================================================
# MONGODB ATLAS CONNECTION
# ============================================================

MONGO_URI = os.getenv("MONGO_URI")

if not MONGO_URI:
    raise ValueError(
        "MONGO_URI not found in .env. "
        "Make sure your .env contains MONGO_URI."
    )


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


# ============================================================
# DATABASES
# ============================================================

robu_db = client["robu_db"]

robocraze_db = client["robocraze_db"]

amazon_db = client["amazon_db"]

alerts_db = client["alerts_db"]

alerts_collection = alerts_db["alerts"]

chatlog_db = client["chatlog_db"]

chatlog_collection = chatlog_db["chat_messages"]


# ============================================================
# DATA FRESHNESS
# ============================================================

# Product results are considered fresh for 24 hours.

DATA_FRESHNESS_HOURS = 24


# ============================================================
# EMAIL CONFIGURATION
# ============================================================

EMAIL_HOST = "smtp.gmail.com"

EMAIL_PORT = 587


# ============================================================
# SEND EMAIL
# ============================================================

def send_email(recipient, subject, message):
    """
    Send an email to the specified recipient.
    """

    try:

        msg = MIMEMultipart()

        msg["From"] = (
            "Multi-Site Product Finder "
            "<multisiteproductfinder@gmail.com>"
        )

        msg["To"] = recipient

        msg["Subject"] = subject

        msg["Reply-To"] = (
            "multisiteproductfinder@gmail.com"
        )

        msg.attach(
            MIMEText(
                message,
                "html"
            )
        )


        server = smtplib.SMTP(
            EMAIL_HOST,
            EMAIL_PORT
        )

        server.starttls()

        server.login(
            EMAIL_USERNAME,
            EMAIL_PASSWORD
        )

        server.send_message(msg)

        server.quit()


        print(
            f"Email sent to {recipient}"
        )

        return True


    except Exception as e:

        print(
            f"Failed to send email: {str(e)}"
        )

        return False


# ============================================================
# GET COLLECTION
# ============================================================

def get_collection_for_query(db, search_query):
    """
    Returns a MongoDB collection for the given search query.
    """

    collection_name = (
        f"{search_query.lower().replace(' ', '_')}_products"
    )

    return db[collection_name]


# ============================================================
# GET EXISTING RESULTS
# ============================================================

def get_existing_results(search_query):
    """
    Check if we have recent results for this search query.

    Returns:
        results if fresh data exists
        None otherwise
    """

    freshness_threshold = (
        time.time()
        - (DATA_FRESHNESS_HOURS * 3600)
    )


    all_products = []

    found_results = False


    # ========================================================
    # ROBU.IN
    # ========================================================

    robu_collection = get_collection_for_query(
        robu_db,
        search_query
    )

    robu_products = list(
        robu_collection.find({
            "timestamp": {
                "$gt": freshness_threshold
            }
        })
    )


    if robu_products:

        found_results = True

        for product in robu_products:

            product["_id"] = str(
                product["_id"]
            )

            product["source"] = "Robu.in"

            all_products.append(
                product
            )


    # ========================================================
    # ROBOCRAZE
    # ========================================================

    robocraze_collection = get_collection_for_query(
        robocraze_db,
        search_query
    )

    robocraze_products = list(
        robocraze_collection.find({
            "timestamp": {
                "$gt": freshness_threshold
            }
        })
    )


    if robocraze_products:

        found_results = True

        for product in robocraze_products:

            product["_id"] = str(
                product["_id"]
            )

            product["source"] = "RoboCraze"

            all_products.append(
                product
            )


    # ========================================================
    # AMAZON
    # ========================================================

    amazon_collection = get_collection_for_query(
        amazon_db,
        search_query
    )

    amazon_products = list(
        amazon_collection.find({
            "timestamp": {
                "$gt": freshness_threshold
            }
        })
    )


    if amazon_products:

        found_results = True

        for product in amazon_products:

            product["_id"] = str(
                product["_id"]
            )

            product["source"] = "Amazon.in"

            all_products.append(
                product
            )


    # ========================================================
    # RETURN RESULTS
    # ========================================================

    if found_results:

        print(
            f"Found fresh existing results "
            f"for: {search_query}"
        )

        return all_products


    return None


# ============================================================
# SCRAPE ALL SITES
# ============================================================

def scrape_all_sites(search_query):
    """
    Unified function to scrape all three websites
    for product data.
    """

    print(
        f"Starting unified search for: "
        f"{search_query}"
    )

    print("=" * 60)


    # ========================================================
    # CHECK EXISTING DATA
    # ========================================================

    existing_results = get_existing_results(
        search_query
    )

    if existing_results:

        return existing_results


    # ========================================================
    # COLLECTIONS
    # ========================================================

    robu_collection = get_collection_for_query(
        robu_db,
        search_query
    )

    robocraze_collection = get_collection_for_query(
        robocraze_db,
        search_query
    )

    amazon_collection = get_collection_for_query(
        amazon_db,
        search_query
    )


    # ========================================================
    # CLEAR OLD DATA
    # ========================================================

    robu_collection.delete_many({})

    robocraze_collection.delete_many({})

    amazon_collection.delete_many({})


    # ========================================================
    # SCRAPER STATUS
    # ========================================================

    scraper_status = {

        "robu": "pending",

        "robocraze": "pending",

        "amazon": "pending"
    }


    # ========================================================
    # ROBU THREAD
    # ========================================================

    def run_robu_scraper():

        try:

            print(
                "Starting Robu.in scraper..."
            )

            scraper_status["robu"] = "running"

            scrape_robu(
                search_query
            )

            scraper_status["robu"] = "completed"

            print(
                "Completed Robu.in scraping"
            )


        except Exception as e:

            scraper_status["robu"] = "error"

            print(
                f"Error in Robu.in scraper: {e}"
            )


    # ========================================================
    # ROBOCRAZE THREAD
    # ========================================================

    def run_robocraze_scraper():

        try:

            print(
                "Starting RoboCraze scraper..."
            )

            scraper_status["robocraze"] = "running"

            scrape_robocraze(
                search_query
            )

            scraper_status["robocraze"] = "completed"

            print(
                "Completed RoboCraze scraping"
            )


        except Exception as e:

            scraper_status["robocraze"] = "error"

            print(
                f"Error in RoboCraze scraper: {e}"
            )


    # ========================================================
    # AMAZON THREAD
    # ========================================================

    def run_amazon_scraper():

        try:

            print(
                "Starting Amazon.in scraper..."
            )

            scraper_status["amazon"] = "running"

            scrape_amazon(
                search_query
            )

            scraper_status["amazon"] = "completed"

            print(
                "Completed Amazon.in scraping"
            )


        except Exception as e:

            scraper_status["amazon"] = "error"

            print(
                f"Error in Amazon.in scraper: {e}"
            )


    # ========================================================
    # CREATE THREADS
    # ========================================================

    threads = [

        threading.Thread(
            target=run_robu_scraper
        ),

        threading.Thread(
            target=run_robocraze_scraper
        ),

        threading.Thread(
            target=run_amazon_scraper
        )
    ]


    # ========================================================
    # START THREADS
    # ========================================================

    for thread in threads:

        thread.start()


    # ========================================================
    # WAIT FOR THREADS
    # ========================================================

    for thread in threads:

        thread.join()


    print("=" * 60)

    print(
        f"Completed unified search "
        f"for: {search_query}"
    )


    # ========================================================
    # COLLECT RESULTS
    # ========================================================

    all_products = []


    # ========================================================
    # ROBU RESULTS
    # ========================================================

    robu_products = list(
        robu_collection.find({})
    )

    for product in robu_products:

        product["_id"] = str(
            product["_id"]
        )

        product["source"] = "Robu.in"

        all_products.append(
            product
        )


    # ========================================================
    # ROBOCRAZE RESULTS
    # ========================================================

    robocraze_products = list(
        robocraze_collection.find({})
    )

    for product in robocraze_products:

        product["_id"] = str(
            product["_id"]
        )

        product["source"] = "RoboCraze"

        all_products.append(
            product
        )


    # ========================================================
    # AMAZON RESULTS
    # ========================================================

    amazon_products = list(
        amazon_collection.find({})
    )

    for product in amazon_products:

        product["_id"] = str(
            product["_id"]
        )

        product["source"] = "Amazon.in"

        all_products.append(
            product
        )


    return all_products


# ============================================================
# CHECK PRODUCT AVAILABILITY
# ============================================================

def check_product_availability():
    """
    Check all active alerts by scraping product URLs
    for availability.
    """

    print(
        "🔁 Running daily product availability check..."
    )


    # ========================================================
    # GET ACTIVE ALERTS
    # ========================================================

    alerts = list(
        alerts_collection.find({
            "alert_enabled": True
        })
    )


    for alert in alerts:

        product_name = alert[
            "product_name"
        ]

        product_url = alert.get(
            "product_url",
            "#"
        )

        source = alert.get(
            "source",
            "Unknown"
        )

        email = alert[
            "email"
        ]

        price = alert.get(
            "price",
            "N/A"
        )

        image_url = alert.get(
            "image_url",
            ""
        )


        print(
            f"🧐 Checking availability for "
            f"{product_name} ({source})"
        )


        # ====================================================
        # CHECK PRODUCT
        # ====================================================

        try:

            is_available = (
                scrape_product_availability(
                    product_url
                )
            )


        except Exception as e:

            print(
                f"⚠️ Error checking product: {e}"
            )

            continue


        # ====================================================
        # PRODUCT AVAILABLE
        # ====================================================

        if is_available:

            print(
                f"✅ Available: {product_name}"
            )


            # =================================================
            # EMAIL
            # =================================================

            subject = (
                f"🎉 {product_name} "
                f"is now available!"
            )


            message = f"""
            <html>
            <body>

                <h2>
                    Product Alert:
                    Item Now Available!
                </h2>

                <p>
                    Good news! The product you were
                    waiting for is now available:
                </p>

                <p>
                    <strong>
                        {product_name}
                    </strong>
                    from {source}
                </p>

                <p>
                    Price: {price}
                </p>

                <p>
                    <a href="{product_url}">
                        Click here to view the product
                    </a>
                </p>

                {
                    '<img src="'
                    + image_url
                    + '" width="300"/>'
                    if image_url
                    else ''
                }

                <p>
                    Thank you for using our service!
                </p>

            </body>
            </html>
            """


            send_email(
                email,
                subject,
                message
            )


            # =================================================
            # DISABLE ALERT
            # =================================================

            alerts_collection.update_one(

                {
                    "_id": alert["_id"]
                },

                {
                    "$set": {
                        "alert_enabled": False,
                        "availability": "Yes"
                    }
                }
            )


        # ====================================================
        # STILL UNAVAILABLE
        # ====================================================

        else:

            print(
                f"🚫 Still not available: "
                f"{product_name}"
            )


# ============================================================
# AVAILABILITY CHECKER
# ============================================================

def start_availability_checker():
    """
    Start the availability checker
    in a background thread.
    """

    check_thread = threading.Thread(
        target=availability_checker_loop
    )

    check_thread.daemon = True

    check_thread.start()


def availability_checker_loop():
    """
    Run the availability checker once every 24 hours.
    """

    while True:

        try:

            check_product_availability()


        except Exception as e:

            print(
                f"Error in availability checker: {e}"
            )


        # 24 hours
        time.sleep(86400)


# ============================================================
# HOME ROUTE
# ============================================================

@app.route("/")
def home():

    return render_template(
        "index.html"
    )


# ============================================================
# SEARCH ROUTE
# ============================================================

@app.route(
    "/search",
    methods=["POST"]
)
def search():

    search_query = request.form.get(
        "query"
    )


    if not search_query:

        return jsonify({
            "error": "Search query is required"
        }), 400


    # ========================================================
    # FORCE REFRESH
    # ========================================================

    force_refresh = (
        request.form.get(
            "force_refresh"
        )
        == "true"
    )


    # ========================================================
    # RANKING WEIGHTS
    # ========================================================

    weights = {

        "relevance": float(
            request.form.get(
                "relevance_weight",
                0.4
            )
        ),

        "price": float(
            request.form.get(
                "price_weight",
                0.3
            )
        ),

        "availability": float(
            request.form.get(
                "availability_weight",
                0.3
            )
        )
    }


    # Keep this variable because your frontend
    # may send it even though the ranking function
    # currently controls the final result count.

    limit = int(
        request.form.get(
            "limit",
            10
        )
    )


    # ========================================================
    # FORCE REFRESH
    # ========================================================

    if force_refresh:

        robu_collection = get_collection_for_query(
            robu_db,
            search_query
        )

        robocraze_collection = get_collection_for_query(
            robocraze_db,
            search_query
        )

        amazon_collection = get_collection_for_query(
            amazon_db,
            search_query
        )


        robu_collection.delete_many({})

        robocraze_collection.delete_many({})

        amazon_collection.delete_many({})


        results = scrape_all_sites(
            search_query
        )


    # ========================================================
    # EXISTING RESULTS
    # ========================================================

    else:

        results = get_existing_results(
            search_query
        )


        if not results:

            results = scrape_all_sites(
                search_query
            )


    # ========================================================
    # RANK RESULTS
    # ========================================================

    ranked_results = rank_scraped_products(
        results,
        search_query
    )


    return jsonify(
        ranked_results
    )


# ============================================================
# STATUS ROUTE
# ============================================================

@app.route(
    "/status",
    methods=["GET"]
)
def get_status():

    return jsonify({
        "status": "ready"
    })


# ============================================================
# ENABLE ALERT
# ============================================================

@app.route(
    "/enable_alert",
    methods=["POST"]
)
def enable_alert():

    product_name = request.form.get(
        "product_name"
    )

    product_url = request.form.get(
        "product_url"
    )

    availability = request.form.get(
        "availability"
    )

    source = request.form.get(
        "source"
    )

    email = request.form.get(
        "email"
    )

    alert_id = request.form.get(
        "alert_id"
    )

    image_url = request.form.get(
        "image_url",
        ""
    )


    if (
        not product_name
        or not product_url
        or not availability
        or not email
    ):

        return jsonify({
            "error":
            "Product details and email are required"
        }), 400


    # ========================================================
    # SAVE ALERT TO ATLAS
    # ========================================================

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


    # ========================================================
    # CONFIRMATION EMAIL
    # ========================================================

    subject = (
        f"Alert Enabled for {product_name}"
    )


    message = f"""
    <html>
    <body>

        <h2>
            Product Alert Confirmation
        </h2>

        <p>
            You have successfully enabled an alert for:
        </p>

        <p>
            <strong>
                {product_name}
            </strong>
            from {source}
        </p>

        <p>
            We will notify you when this product
            becomes available.
        </p>

        <p>
            Thank you for using our service!
        </p>

    </body>
    </html>
    """


    send_email(
        email,
        subject,
        message
    )


    return jsonify({
        "message":
        "Alert enabled for product. "
        "You will receive an email confirmation."
    })


# ============================================================
# REMOVE ALERT
# ============================================================

@app.route(
    "/remove_alert",
    methods=["POST"]
)
def remove_alert():

    alert_id = request.form.get(
        "alert_id"
    )


    if not alert_id:

        return jsonify({
            "error": "Alert ID is required"
        }), 400


    # ========================================================
    # REMOVE FROM ATLAS
    # ========================================================

    alerts_collection.delete_one({
        "alert_id": alert_id
    })


    return jsonify({
        "message":
        "Alert removed successfully"
    })


# ============================================================
# GET ALERTS
# ============================================================

@app.route(
    "/get_alerts",
    methods=["POST"]
)
def get_alerts():

    email = request.form.get(
        "email"
    )


    if not email:

        return jsonify({
            "error": "Email is required"
        }), 400


    # ========================================================
    # GET ALERTS FROM ATLAS
    # ========================================================

    alerts = list(
        alerts_collection.find({
            "email": email
        })
    )


    # ========================================================
    # CONVERT OBJECTID
    # ========================================================

    for alert in alerts:

        alert["_id"] = str(
            alert["_id"]
        )


    return jsonify(
        alerts
    )


# ============================================================
# CHATBOT
# ============================================================

@app.route(
    "/chatbot",
    methods=["POST"]
)
def chatbot():

    data = request.get_json()

    user_message = data.get(
        "message",
        ""
    )

    bot_type = data.get(
        "bot",
        "luffy"
    )


    if not user_message:

        return jsonify({
            "error": "Message is required"
        }), 400


    # ========================================================
    # TERMINAL LOG
    # ========================================================

    print(
        f"[CHATBOT] User "
        f"({bot_type}): "
        f"{user_message}"
    )


    # ========================================================
    # GEMINI RESPONSE
    # ========================================================

    reply = ask_luffybot(
        user_message,
        bot_type
    )


    # ========================================================
    # SAVE CHAT TO ATLAS
    # ========================================================

    chatlog_collection.insert_one({

        "bot_type": bot_type,

        "user_message": user_message,

        "bot_reply": reply,

        "timestamp": time.time()
    })


    return jsonify({
        "reply": reply
    })


# ============================================================
# RUN APPLICATION
# ============================================================

if __name__ == "__main__":

    # ========================================================
    # START AVAILABILITY CHECKER
    # ========================================================

    start_availability_checker()


    # ========================================================
    # START FLASK
    # ========================================================

    # Render provides the PORT environment variable.
    # 5000 is used as the local development fallback.
    port = int(os.environ.get("PORT", 5000))

    print(
        f"🚀 Starting Flask server on port {port}"
    )

    app.run(
        host="0.0.0.0",
        port=port
    )
