import os
import requests
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = "gemini-3.6-flash"

GEMINI_API_URL = (
    "https://generativelanguage.googleapis.com/"
    f"v1beta/models/{GEMINI_MODEL}:generateContent"
)


def ask_luffybot(user_message, bot_type="luffy"):

    if not GEMINI_API_KEY:
        return "❌ Gemini API key is missing. Check your .env file."

    # --------------------------------------------------
    # BOT PERSONALITIES
    # --------------------------------------------------

    if bot_type == "pro":

        system_prompt = (
            "You are Dr. Vegapunk from One Piece, "
            "a genius scientist and professional electronics assistant.\n"
            "Reply concisely and technically.\n"
            "Avoid unnecessary fluff.\n"
            "For projects, provide:\n"
            "1. Project name\n"
            "2. Components\n"
            "3. Steps\n"
            "4. Important notes\n"
        )

    elif bot_type == "debug":

        system_prompt = (
            "You are DebugBot, the official support assistant "
            "for the CirkitRadar website.\n\n"

            "CirkitRadar helps users track and compare electronics "
            "products across Robu.in, RoboCraze, and Amazon.in.\n\n"

            "Features:\n"
            "- Product search\n"
            "- Live scraping / force refresh\n"
            "- Product comparison\n"
            "- Stock alerts via email\n"
            "- My Alerts management\n"
            "- LuffyBot, ProBot and DebugBot\n\n"

            "Help users troubleshoot:\n"
            "- Site not loading\n"
            "- Chatbot not responding\n"
            "- Products not appearing\n"
            "- Emails not received\n"
            "- Buttons not working\n"
            "- Stock alerts\n\n"

            "Be concise, clear and practical.\n"
            "Ask a clarifying question when necessary."
        )

    else:

        system_prompt = (
            "You are LuffyBot from One Piece, "
            "a cheerful pirate who loves electronics!\n"
            "Be energetic, friendly and adventurous.\n"
            "Use a little pirate slang and emojis.\n"
            "Help users with electronics projects step-by-step.\n"
            "Don't overdo the roleplay."
        )

    # --------------------------------------------------
    # GEMINI REQUEST
    # --------------------------------------------------

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text":
                            system_prompt
                            + "\n\nUser: "
                            + user_message
                    }
                ]
            }
        ]
    }

    try:

        response = requests.post(
            GEMINI_API_URL,
            params={
                "key": GEMINI_API_KEY
            },
            json=payload,
            timeout=30
        )

        # Useful when debugging API problems
        if not response.ok:
            return (
                f"❌ Gemini API error "
                f"({response.status_code}):\n"
                f"{response.text[:1000]}"
            )

        data = response.json()

        candidates = data.get(
            "candidates",
            []
        )

        if not candidates:
            return "🤕 Gemini returned no response."

        parts = (
            candidates[0]
            .get("content", {})
            .get("parts", [])
        )

        if not parts:
            return "🤕 Gemini returned an empty response."

        return parts[0].get(
            "text",
            "🤕 Gemini returned no text."
        )

    except requests.exceptions.Timeout:

        return (
            "⏱️ Gemini took too long to respond. "
            "Please try again."
        )

    except requests.exceptions.ConnectionError:

        return (
            "🌐 Could not connect to Gemini. "
            "Check your internet connection."
        )

    except requests.exceptions.RequestException as e:

        return (
            f"🤕 Gemini API request failed:\n{e}"
        )

    except Exception as e:

        return (
            f"🤕 Unexpected chatbot error:\n{e}"
        )