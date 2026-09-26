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

NEWS_API_KEY = os.getenv("NEWS_API_KEY")

TOP_HEADLINES_URL = "https://newsapi.org/v2/top-headlines"
EVERYTHING_URL = "https://newsapi.org/v2/everything"


# =========================================================
# FALLBACK NEWS
# =========================================================

NEWS = [
    {
        "title": "GLOBAL24 Newsroom Is Live",
        "category": "WORLD",
        "summary": "Your international news dashboard is ready.",
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
    "WORLD": "world OR international",
    "AFRICA": "Africa",
    "ETHIOPIA": "Ethiopia",
    "BUSINESS": "business OR economy OR finance",
    "TECHNOLOGY": "technology OR tech",
    "SPORT": "sports OR football OR soccer"
}


# =========================================================
# FALLBACK IMAGE
# =========================================================

DEFAULT_IMAGE = (
    "https://images.unsplash.com/"
    "photo-1504711434969-e33886168f5c"
    "?auto=format&fit=crop&w=1200&q=80"
)


# =========================================================
# CONVERT ARTICLE
# =========================================================

def convert_article(article, category):

    title = article.get("title")

    if not title:
        return None

    if title == "[Removed]":
        return None

    return {
        "title": title,

        "category": category,

        "summary": (
            article.get("description")
            or "Read the latest story from GLOBAL24."
        ),

        "image": (
            article.get("urlToImage")
            or DEFAULT_IMAGE
        ),

        "breaking": False,

        "url": article.get("url") or "",

        "publishedAt": (
            article.get("publishedAt")
            or ""
        ),

        "source": (
            article.get("source", {})
            .get("name")
            or ""
        )
    }


# =========================================================
# GET NEWS
# =========================================================

def get_news(category="WORLD"):

    category = category.upper()

    query = CATEGORY_SEARCH.get(
        category,
        "world OR international"
    )

    if not NEWS_API_KEY:

        print("NEWS_API_KEY is not configured.")

        return []


    try:

        # -------------------------------------------------
        # AFRICA / ETHIOPIA / WORLD / BUSINESS /
        # TECHNOLOGY / SPORT
        #
        # Use EVERYTHING for topic searches.
        # -------------------------------------------------

        response = requests.get(
            EVERYTHING_URL,
            headers={
                "X-Api-Key": NEWS_API_KEY,
                "X-No-Cache": "true"
            },
            params={
                "q": query,
                "language": "en",
                "sortBy": "publishedAt",
                "pageSize": 20
            },
            timeout=15
        )


        print(
            "News API status:",
            response.status_code
        )


        if response.status_code != 200:

            print(
                "News API response:",
                response.text[:1000]
            )

            return []


        data = response.json()


        if data.get("status") != "ok":

            print(
                "News API error:",
                data
            )

            return []


        stories = []


        for article in data.get(
            "articles",
            []
        ):

        story = convert_article(
    article,
    category
)

            if story:

                stories.append(story)


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

        stories = [
            story
            for story in NEWS
            if story["category"] == "WORLD"
        ]


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
                    DEFAULT_IMAGE
                ),

            "breaking":
                request.form.get(
                    "breaking"
                ) == "on",

            "url":
                request.form.get(
                    "url",
                    ""
                )
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
