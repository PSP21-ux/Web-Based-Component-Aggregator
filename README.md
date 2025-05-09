# Web-Based Component Aggregator

A smart web app that tracks electronic components across **Robu.in**, **RoboCraze**, and **Amazon.in**, with ML-powered ranking, chatbot support, and email alerts.

## 🚀 Features

- 🔍 Unified product search
- 📦 Real-time availability scraping
- 🧠 Intelligent product ranking with ML
- 📧 Email alerts when items are back in stock
- 🤖 Chatbots: LuffyBot (fun), ProBot (tech), DebugBot (support)
- 🌐 Frontend with theme switcher and animations

---

## 🛠️ Setup Instructions

### 1. Clone the Repo

```bash
git clone https://github.com/PSP21-ux/Web-Based-Component-Aggregator.git
cd Web-Based-Component-Aggregator
```

### 2. Create a `.env` File

Copy this template:

```env
EMAIL_USERNAME=your-email@gmail.com
EMAIL_PASSWORD=your-app-password
GEMINI_API_KEY=your-gemini-api-key
NGROK_AUTH_TOKEN=your-ngrok-auth-token
```

Save it as `.env` in the root folder.

### 3. Install Requirements

```bash
pip install -r requirements.txt
```

### 4. Run the App

```bash
python app.py
```

The app will start with an `ngrok` public URL for easy access.

---

## 📦 Folder Structure

```
.
├── app.py
├── amazon_scraper.py
├── alertscraping.py
├── gemini_chatbot.py
├── ml_ranker.py
├── robu_scraper.py
├── robocraze_scraper.py
├── templates/
│   └── index.html
├── static/
│   └── [images, CSS, JS]
├── .gitignore
├── requirements.txt
└── README.md
```

---

## 📝 License

MIT License (or your choice)
