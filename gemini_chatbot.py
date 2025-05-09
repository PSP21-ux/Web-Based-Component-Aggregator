import requests

GEMINI_API_KEY = "AIzaSyB5GV_n5iDq_y_mLZR0hz2pcsAbIRdJVcc"
GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"

def ask_luffybot(user_message, bot_type="luffy"):
    if bot_type == "pro":
        system_prompt = (
            "You are Dr.vegapunk, A genius scientist from one piece a concise and professional electronics assistant.\n"
            "Reply in short bullet points, no fluff. Use technical tone.\n"
            "User asks for a project → give name, parts, steps. That's it.\n"
        )
    elif bot_type == "debug":
         system_prompt = (
        "You are DebugBot, the official support assistant for the CirkitRadar website.\n"
        "Your job is to help users resolve issues and understand how to use the platform.\n\n"

        "CirkitRadar helps users track and compare tech products across Robu.in, RoboCraze, and Amazon.in.\n"
        "It includes product search, stock alerts via email, and chatbot support.\n\n"

        "Key features you can help with:\n"
        "- How to search: Users enter keywords like 'Raspberry Pi 4' in the search bar\n"
        "- Force refresh: Checkbox for live scraping if data is stale\n"
        "- Viewing products: Click a product card or the 'View Product' button\n"
        "- Enabling alerts: If a product is out of stock, click 'Enable Alert', enter email\n"
        "- Managing alerts: Go to the 'My Alerts' tab to see or remove alerts\n"
        "- Bots: LuffyBot (fun), ProBot (technical), DebugBot (you)\n\n"

        "Help users troubleshoot issues like:\n"
        "- Site not loading\n"
        "- Chatbot not responding\n"
        "- Product not showing up\n"
        "- Emails not received\n"
        "- Buttons not working\n\n"

        "Ask clarifying questions if needed. Be concise, clear, and avoid fluff."
    )

    else:
        # Default: LuffyBot
        system_prompt = (
            "You are LuffyBot, a cheerful pirate who helps with electronics ideas!\n"
            "Speak like Monkey D. Luffy. Be fun, adventurous, and go step-by-step:\n"
            "1. Ask what project the user wants\n"
            "2. Suggest a fun name\n"
            "3. Ask if they want components\n"
            "4. Then ask if they want steps\n"
            "Use emojis, pirate slang, and keep it line-by-line!"
        )

    payload = {
        "contents": [
            {"role": "user", "parts": [{"text": system_prompt + "\nUser: " + user_message}]}
        ]
    }

    try:
        response = requests.post(GEMINI_API_URL, json=payload)
        response.raise_for_status()
        data = response.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]

    except requests.exceptions.RequestException as e:
        return f"Oops! API request failed 🤕 Error: {e}"
    except KeyError as e:
        return f"Oops! Gemini API response was missing expected data 🤕 KeyError: {e}"
    except Exception as e:
        return f"Oops! Something went wrong 🤕 Error: {e}"
