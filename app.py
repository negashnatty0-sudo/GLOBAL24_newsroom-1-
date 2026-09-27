from flask import Flask, render_template, request, jsonify, session, redirect
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from pathlib import Path
from google import genai
import cloudinary
import cloudinary.uploader
import sqlite3
import os

app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "CHANGE_THIS_SECRET_KEY"
)

BASE_DIR = Path(__file__).resolve().parent
DATABASE = BASE_DIR / "global24.db"

# Maximum upload size: 500 MB
app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024


# =========================================================
# CLOUDINARY
# =========================================================

cloudinary.config(
    cloud_name=os.environ.get("CLOUDINARY_CLOUD_NAME"),
    api_key=os.environ.get("CLOUDINARY_API_KEY"),
    api_secret=os.environ.get("CLOUDINARY_API_SECRET"),
    secure=True
)


# =========================================================
# DATABASE
# =========================================================

def get_db():
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    return db


def init_db():

    db = get_db()

    db.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            headline TEXT NOT NULL,
            category TEXT,
            author TEXT,
            image TEXT,
            video TEXT,
            summary TEXT,
            content TEXT NOT NULL,
            breaking INTEGER DEFAULT 0,
            status TEXT DEFAULT 'Draft',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Add video column to older databases
    columns = [
        row["name"]
        for row in db.execute(
            "PRAGMA table_info(articles)"
        ).fetchall()
    ]

    if "video" not in columns:

        db.execute(
            "ALTER TABLE articles ADD COLUMN video TEXT"
        )

    # Create default admin account
    admin = db.execute(
        "SELECT id FROM admins WHERE username = ?",
        ("admin",)
    ).fetchone()

    if admin is None:

        db.execute(
            """
            INSERT INTO admins
            (username, password_hash)
            VALUES (?, ?)
            """,
            (
                "admin",
                generate_password_hash("change-me")
            )
        )

    db.commit()
    db.close()


# =========================================================
# AUTHENTICATION
# =========================================================

def admin_required(function):

    @wraps(function)
    def decorated(*args, **kwargs):

        if not session.get("admin_logged_in"):

            return jsonify({
                "success": False,
                "error": "Authentication required"
            }), 401

        return function(*args, **kwargs)

    return decorated


# =========================================================
# PAGES
# =========================================================

@app.route("/")
def home():

    return render_template("index.html")


@app.route("/login")
def login_page():

    if session.get("admin_logged_in"):

        return redirect("/admin")

    return render_template("login.html")


@app.route("/admin")
def admin_page():

    if not session.get("admin_logged_in"):

        return redirect("/login")

    return render_template("admin.html")


# =========================================================
# LOGIN
# =========================================================

@app.route("/api/login", methods=["POST"])
def login():

    data = request.get_json(
        silent=True
    ) or {}

    username = data.get(
        "username",
        ""
    ).strip()

    password = data.get(
        "password",
        ""
    )

    if not username or not password:

        return jsonify({
            "success": False,
            "error": "Username and password are required."
        }), 400

    db = get_db()

    admin = db.execute(
        """
        SELECT *
        FROM admins
        WHERE username = ?
        """,
        (username,)
    ).fetchone()

    db.close()

    if admin is None:

        return jsonify({
            "success": False,
            "error": "Invalid username or password."
        }), 401

    if not check_password_hash(
        admin["password_hash"],
        password
    ):

        return jsonify({
            "success": False,
            "error": "Invalid username or password."
        }), 401

    session["admin_logged_in"] = True
    session["admin_id"] = admin["id"]
    session["admin_username"] = admin["username"]

    return jsonify({
        "success": True
    })


# =========================================================
# LOGOUT
# =========================================================

@app.route("/api/logout", methods=["POST"])
def logout():

    session.clear()

    return jsonify({
        "success": True
    })


# =========================================================
# CURRENT ADMIN
# =========================================================

@app.route("/api/me")
def current_admin():

    if not session.get("admin_logged_in"):

        return jsonify({
            "logged_in": False
        })

    return jsonify({
        "logged_in": True,
        "username": session.get(
            "admin_username"
        )
    })


# =========================================================
# PUBLIC ARTICLES
# =========================================================

@app.route("/api/articles")
def get_articles():

    category = request.args.get(
        "category"
    )

    db = get_db()

    if category:

        rows = db.execute(
            """
            SELECT *
            FROM articles
            WHERE status = 'Published'
            AND category = ?
            ORDER BY created_at DESC
            """,
            (category,)
        ).fetchall()

    else:

        rows = db.execute(
            """
            SELECT *
            FROM articles
            WHERE status = 'Published'
            ORDER BY created_at DESC
            """
        ).fetchall()

    db.close()

    articles = [
        dict(row)
        for row in rows
    ]

    for article in articles:

        article["breaking"] = bool(
            article["breaking"]
        )

    return jsonify({
        "success": True,
        "articles": articles
    })


# =========================================================
# ADMIN — ALL ARTICLES
# =========================================================

@app.route("/api/admin/articles")
@admin_required
def admin_articles():

    db = get_db()

    rows = db.execute(
        """
        SELECT *
        FROM articles
        ORDER BY created_at DESC
        """
    ).fetchall()

    db.close()

    articles = [
        dict(row)
        for row in rows
    ]

    for article in articles:

        article["breaking"] = bool(
            article["breaking"]
        )

    return jsonify({
        "success": True,
        "articles": articles
    })


# =========================================================
# MEDIA UPLOAD
# =========================================================

@app.route(
    "/api/admin/upload",
    methods=["POST"]
)
@admin_required
def upload_media():

    if "file" not in request.files:

        return jsonify({
            "success": False,
            "error": "No file selected."
        }), 400

    file = request.files["file"]

    if not file or not file.filename:

        return jsonify({
            "success": False,
            "error": "No file selected."
        }), 400

    filename = file.filename.lower()

    image_extensions = (
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
        ".gif"
    )

    video_extensions = (
        ".mp4",
        ".webm",
        ".mov",
        ".m4v"
    )

    if filename.endswith(
        image_extensions
    ):

        resource_type = "image"

    elif filename.endswith(
        video_extensions
    ):

        resource_type = "video"

    else:

        return jsonify({
            "success": False,
            "error": "Unsupported file type."
        }), 400

    try:

        if resource_type == "video":

            result = cloudinary.uploader.upload_large(
                file,
                resource_type="video",
                folder="global24/videos",
                chunk_size=20 * 1024 * 1024
            )

        else:

            result = cloudinary.uploader.upload(
                file,
                resource_type="image",
                folder="global24/images"
            )

        return jsonify({
            "success": True,
            "type": resource_type,
            "url": result.get(
                "secure_url"
            ),
            "public_id": result.get(
                "public_id"
            )
        })

    except Exception:

        app.logger.exception(
            "Media upload failed"
        )

        return jsonify({
            "success": False,
            "error": "Media upload failed."
        }), 500


# =========================================================
# CREATE ARTICLE
# =========================================================

@app.route(
    "/api/admin/articles",
    methods=["POST"]
)
@admin_required
def create_article():

    data = request.get_json(
        silent=True
    ) or {}

    headline = data.get(
        "headline",
        ""
    ).strip()

    category = data.get(
        "category",
        ""
    ).strip()

    author = data.get(
        "author",
        "GLOBAL24"
    ).strip()

    image = data.get(
        "image",
        ""
    ).strip()

    video = data.get(
        "video",
        ""
    ).strip()

    summary = data.get(
        "summary",
        ""
    ).strip()

    content = data.get(
        "content",
        ""
    ).strip()

    breaking = bool(
        data.get(
            "breaking",
            False
        )
    )

    status = data.get(
        "status",
        "Draft"
    )

    if not headline:

        return jsonify({
            "success": False,
            "error": "Headline is required."
        }), 400

    if not content:

        return jsonify({
            "success": False,
            "error": "Article content is required."
        }), 400

    if status not in [
        "Draft",
        "Published"
    ]:

        status = "Draft"

    db = get_db()

    cursor = db.execute(
        """
        INSERT INTO articles
        (
            headline,
            category,
            author,
            image,
            video,
            summary,
            content,
            breaking,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            headline,
            category,
            author,
            image,
            video,
            summary,
            content,
            int(breaking),
            status
        )
    )

    article_id = cursor.lastrowid

    db.commit()
    db.close()

    return jsonify({
        "success": True,
        "id": article_id
    }), 201


# =========================================================
# UPDATE ARTICLE
# =========================================================

@app.route(
    "/api/admin/articles/<int:article_id>",
    methods=["PUT"]
)
@admin_required
def update_article(article_id):

    data = request.get_json(
        silent=True
    ) or {}

    headline = data.get(
        "headline",
        ""
    ).strip()

    category = data.get(
        "category",
        ""
    ).strip()

    author = data.get(
        "author",
        "GLOBAL24"
    ).strip()

    image = data.get(
        "image",
        ""
    ).strip()

    video = data.get(
        "video",
        ""
    ).strip()

    summary = data.get(
        "summary",
        ""
    ).strip()

    content = data.get(
        "content",
        ""
    ).strip()

    breaking = bool(
        data.get(
            "breaking",
            False
        )
    )

    status = data.get(
        "status",
        "Draft"
    )

    if not headline:

        return jsonify({
            "success": False,
            "error": "Headline is required."
        }), 400

    if not content:

        return jsonify({
            "success": False,
            "error": "Article content is required."
        }), 400

    if status not in [
        "Draft",
        "Published"
    ]:

        status = "Draft"

    db = get_db()

    existing = db.execute(
        """
        SELECT id
        FROM articles
        WHERE id = ?
        """,
        (article_id,)
    ).fetchone()

    if existing is None:

        db.close()

        return jsonify({
            "success": False,
            "error": "Article not found."
        }), 404

    db.execute(
        """
        UPDATE articles
        SET
            headline = ?,
            category = ?,
            author = ?,
            image = ?,
            video = ?,
            summary = ?,
            content = ?,
            breaking = ?,
            status = ?
        WHERE id = ?
        """,
        (
            headline,
            category,
            author,
            image,
            video,
            summary,
            content,
            int(breaking),
            status,
            article_id
        )
    )

    db.commit()
    db.close()

    return jsonify({
        "success": True
    })


# =========================================================
# DELETE ARTICLE
# =========================================================

@app.route(
    "/api/admin/articles/<int:article_id>",
    methods=["DELETE"]
)
@admin_required
def delete_article(article_id):

    db = get_db()

    cursor = db.execute(
        """
        DELETE FROM articles
        WHERE id = ?
        """,
        (article_id,)
    )

    db.commit()
    db.close()

    if cursor.rowcount == 0:

        return jsonify({
            "success": False,
            "error": "Article not found."
        }), 404

    return jsonify({
        "success": True
    })


# =========================================================
# ADMIN STATS
# =========================================================

@app.route("/api/admin/stats")
@admin_required
def admin_stats():

    db = get_db()

    total = db.execute(
        """
        SELECT COUNT(*)
        FROM articles
        """
    ).fetchone()[0]

    published = db.execute(
        """
        SELECT COUNT(*)
        FROM articles
        WHERE status = 'Published'
        """
    ).fetchone()[0]

    drafts = db.execute(
        """
        SELECT COUNT(*)
        FROM articles
        WHERE status = 'Draft'
        """
    ).fetchone()[0]

    breaking = db.execute(
        """
        SELECT COUNT(*)
        FROM articles
        WHERE breaking = 1
        """
    ).fetchone()[0]

    db.close()

    return jsonify({
        "success": True,
        "total": total,
        "published": published,
        "drafts": drafts,
        "breaking": breaking
    })


# =========================================================
# GEMINI AI NEWS ASSISTANT
# =========================================================

@app.route(
    "/api/admin/ai",
    methods=["POST"]
)
@admin_required
def ai_assistant():

    api_key = os.environ.get(
        "GEMINI_API_KEY"
    )

    if not api_key:

        return jsonify({
            "success": False,
            "error": "GEMINI_API_KEY is not configured."
        }), 500

    data = request.get_json(
        silent=True
    ) or {}

    action = data.get(
        "action",
        "draft"
    )

    text = data.get(
        "text",
        ""
    ).strip()

    if not text:

        return jsonify({
            "success": False,
            "error": "Enter some information for the AI assistant."
        }), 400

    instructions = """
You are the GLOBAL24 newsroom writing assistant.

Help a human editor prepare professional news content.

Rules:
- Do not invent facts.
- Do not invent quotes.
- Do not present guesses as facts.
- Use only information supplied by the editor.
- Write clear professional newsroom English.
- Keep factual claims faithful to the supplied material.
- The human editor must review the result before publication.
"""

    if action == "headline":

        prompt = f"""
{instructions}

Suggest 5 clear and factual news headlines
based only on this material:

{text}
"""

    elif action == "summary":

        prompt = f"""
{instructions}

Write a concise news summary based only
on this material:

{text}
"""

    elif action == "rewrite":

        prompt = f"""
{instructions}

Rewrite this material in professional
news style without adding facts:

{text}
"""

    elif action == "translate":

        prompt = f"""
{instructions}

Translate the following material into
clear English without adding facts:

{text}
"""

    else:

        prompt = f"""
{instructions}

Create a professional news article draft
from these notes.

Include:

1. Headline
2. Summary
3. Article body

Do not add facts that are not supplied.

Notes:

{text}
"""

    try:

        client = genai.Client(
            api_key=api_key
        )

        response = client.models.generate_content(
            model="gemini-3.8-flash",
            contents=prompt
        )

        result = response.text

        if not result:

            return jsonify({
                "success": False,
                "error": "Gemini returned an empty response."
            }), 500

        return jsonify({
            "success": True,
            "result": result
        })

    except Exception as e:

        app.logger.exception(
            "Gemini AI request failed"
        )

        return jsonify({
            "success": False,
            "error": f"Gemini request failed: {str(e)}"
        }), 500


# =========================================================
# HEALTH CHECK
# =========================================================

@app.route("/api/health")
def health():

    return jsonify({
        "status": "online",
        "service": "GLOBAL24"
    })


# =========================================================
# DATABASE INITIALIZATION
# =========================================================

init_db()


# =========================================================
# RUN
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
        port=port,
        debug=False
    )
