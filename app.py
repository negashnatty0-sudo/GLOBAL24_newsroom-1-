from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from datetime import datetime, timezone
import os
import requests

app = Flask(__name__)

# =========================================================
# SETTINGS
# =========================================================

app.secret_key = os.getenv(
    "SECRET_KEY",
    "CHANGE_THIS_SECRET_KEY"
)

ADMIN_PASSWORD = os.getenv(
    "ADMIN_PASSWORD",
    "admin123"
)

# Your API key stays in Railway Variables
NEWS_API_KEY = os.getenv("NEWS_API_KEY")

NEWS_API_URL = "https://newsapi.org/v2/top-headlines"


# =========================================================
# FALLBACK NEWS
# =========================================================

NEWS = [
    {
        "title": "GLOBAL24 Newsroom Is Live",
        "category": "WORLD",
        "summary": "Your 24/7 international news dashboard is ready.",
        "image": "https://images.unsplash.com/photo-1504711434969-e33886168f5c?auto=format&fit=crop&w=1200&q=80",
        "breaking": True,
        "url": ""
    },
    {
        "title": "Africa Desk",
        "category": "AFRICA",
        "summary": "Follow major developments across Africa.",
        "image": "https://images.unsplash.com/photo-1523805009345-7448845a9e53?auto=format&fit=crop&w=1000&q=80",
        "breaking": False,
        "url": ""
    },
    {
        "title": "Ethiopia Focus",
        "category": "ETHIOPIA",
        "summary": "A dedicated section for Ethiopia and regional coverage.",
        "image": "https://images.unsplash.com/photo-1524498250077-390f9e378fc0?auto=format&fit=crop&w=1000&q=80",
        "breaking": False,
        "url": ""
    }
]


# =========================================================
# CATEGORY SEARCHES
# =========================================================

CATEGORY_SEARCH = {
    "WORLD": "world",
    "AFRICA": "Africa",
    "ETHIOPIA": "Ethiopia",
    "BUSINESS": "business",
    "TECHNOLOGY": "technology",
    "SPORT": "sports"
}


# =========================================================
# GET NEWS FROM API
# =========================================================

def get_news(category="WORLD"):

    category = category.upper()

    query = CATEGORY_SEARCH.get(
        category,
        "world"
    )

    # API key has not been configured
    if not NEWS_API_KEY:

        print("NEWS_API_KEY is not configured.")

        return []


    try:

        response = requests.get(
            NEWS_API_URL,
            params={
                "apiKey": NEWS_API_KEY,
                "q": query,
                "language": "en",
                "pageSize": 20
            },
            timeout=10
        )


        print(
            "News API status:",
            response.status_code
        )


        if response.status_code != 200:

            print(
                "News API response:",
                response.text[:500]
            )

            return []


        data = response.json()


        stories = []


        for article in data.get(
            "articles",
            []
        ):

            title = article.get(
                "title"
            )


            if not title:
                continue


            if title == "[Removed]":
                continue


            stories.append({

                "title": title,

                "category": category,

                "summary":
                    article.get("description")
                    or "Read the latest story from GLOBAL24.",

                "image":
                    article.get("urlToImage")
                    or "https://images.unsplash.com/photo-1504711434969-e33886168f5c?auto=format&fit=crop&w=1200&q=80",

                "breaking": False,

                "url":
                    article.get("url")
                    or ""

            })


        return stories


    except requests.RequestException as error:

        print(
            "NEWS API CONNECTION ERROR:",
            error
        )

        return []


    except Exception as error:

        print(
            "NEWS API ERROR:",
            error
        )

        return []


# =========================================================
# HOME PAGE
# =========================================================

@app.route("/")
def home():

    stories = get_news("WORLD")


    if not stories:

        stories = NEWS


    return render_template(
        "index.html",
        news=stories
    )


# =========================================================
# NEWS API ENDPOINT
# =========================================================

@app.get("/api/news")
def api_news():

    category = request.args.get(
        "category",
        "WORLD"
    ).upper()


    valid_categories = [
        "WORLD",
        "AFRICA",
        "ETHIOPIA",
        "BUSINESS",
        "TECHNOLOGY",
        "SPORT"
    ]


    if category not in valid_categories:

        category = "WORLD"


    stories = get_news(
        category
    )


    # Use local fallback if API returns nothing
    if not stories:

        stories = [
            story
            for story in NEWS
            if story["category"] == category
        ]


    return jsonify({

        "updated":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "category":
            category,

        "stories":
            stories

    })


# =========================================================
# HEALTH CHECK
# =========================================================

@app.get("/health")
def health():

    return jsonify({

        "status": "online",

        "news_api_configured":
            bool(NEWS_API_KEY),

        "time":
            datetime.now(
                timezone.utc
            ).isoformat()

    })


# =========================================================
# ADMIN LOGIN
# =========================================================

@app.route(
    "/admin",
    methods=["GET", "POST"]
)
def admin():

    if request.method == "POST":

        password = request.form.get(
            "password",
            ""
        )


        if password == ADMIN_PASSWORD:

            session["admin"] = True

            return redirect(
                url_for("admin")
            )


        return render_template(
            "admin.html",
            error="Incorrect password"
        )


    if not session.get("admin"):

        return render_template(
            "login.html"
        )


    return render_template(
        "admin.html",
        news=NEWS
    )


# =========================================================
# ADD NEWS FROM ADMIN
# =========================================================

@app.post("/admin/add")
def add_news():

    if not session.get("admin"):

        return redirect(
            url_for("admin")
        )


    NEWS.insert(
        0,
        {

            "title":
                request.form.get(
                    "title",
                    "Untitled"
                ),

            "category":
                request.form.get(
                    "category",
                    "WORLD"
                ).upper(),

            "summary":
                request.form.get(
                    "summary",
                    ""
                ),

            "image":
                request.form.get(
                    "image",
                    "https://images.unsplash.com/photo-1504711434969-e33886168f5c?auto=format&fit=crop&w=1200&q=80"
                ),

            "breaking":
                request.form.get(
                    "breaking"
                ) == "on",

            "url":
                ""

        }
    )


    return redirect(
        url_for("admin")
    )


# =========================================================
# ADMIN LOGOUT
# =========================================================

@app.get("/admin/logout")
def logout():

    session.clear()

    return redirect(
        url_for("home")
    )


# =========================================================
# START FLASK
# =========================================================

if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            5000
        )
    )


    app.run(
        host="0.0.0.0",
        port=port
    )
