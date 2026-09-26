from flask import Flask, render_template, request, jsonify, session, redirect
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from pathlib import Path
import sqlite3
import os

app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "CHANGE_THIS_SECRET_KEY"
)

BASE_DIR = Path(__file__).resolve().parent
DATABASE = BASE_DIR / "global24.db"


# =========================
# DATABASE
# =========================

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
            summary TEXT,
            content TEXT NOT NULL,
            breaking INTEGER DEFAULT 0,
            status TEXT DEFAULT 'Draft',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

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


# =========================
# AUTH
# =========================

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


# =========================
# HTML PAGES
# =========================

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/login")
def login_page():
    return render_template("login.html")


@app.route("/admin")
def admin_page():

    if not session.get("admin_logged_in"):
        return redirect("/login")

    return render_template("admin.html")


# =========================
# LOGIN
# =========================

@app.route("/api/login", methods=["POST"])
def login():

    data = request.get_json(silent=True) or {}

    username = data.get("username", "").strip()
    password = data.get("password", "")

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


# =========================
# LOGOUT
# =========================

@app.route("/api/logout", methods=["POST"])
def logout():

    session.clear()

    return jsonify({
        "success": True
    })


# =========================
# CURRENT USER
# =========================

@app.route("/api/me")
def current_admin():

    if not session.get("admin_logged_in"):
        return jsonify({
            "logged_in": False
        })

    return jsonify({
        "logged_in": True,
        "username": session.get("admin_username")
    })


# =========================
# PUBLIC ARTICLES
# =========================

@app.route("/api/articles")
def get_articles():

    category = request.args.get("category")

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

    articles = [dict(row) for row in rows]

    for article in articles:
        article["breaking"] = bool(article["breaking"])

    return jsonify({
        "success": True,
        "articles": articles
    })


# =========================
# ADMIN ARTICLES
# =========================

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

    articles = [dict(row) for row in rows]

    for article in articles:
        article["breaking"] = bool(article["breaking"])

    return jsonify({
        "success": True,
        "articles": articles
    })


# =========================
# CREATE ARTICLE
# =========================

@app.route("/api/admin/articles", methods=["POST"])
@admin_required
def create_article():

    data = request.get_json(silent=True) or {}

    headline = data.get("headline", "").strip()
    category = data.get("category", "").strip()
    author = data.get("author", "GLOBAL24").strip()
    image = data.get("image", "").strip()
    summary = data.get("summary", "").strip()
    content = data.get("content", "").strip()

    breaking = bool(data.get("breaking", False))

    status = data.get("status", "Draft")

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

    if status not in ["Draft", "Published"]:
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
            summary,
            content,
            breaking,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            headline,
            category,
            author,
            image,
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


# =========================
# UPDATE ARTICLE
# =========================

@app.route(
    "/api/admin/articles/<int:article_id>",
    methods=["PUT"]
)
@admin_required
def update_article(article_id):

    data = request.get_json(silent=True) or {}

    headline = data.get("headline", "").strip()
    category = data.get("category", "").strip()
    author = data.get("author", "GLOBAL24").strip()
    image = data.get("image", "").strip()
    summary = data.get("summary", "").strip()
    content = data.get("content", "").strip()

    breaking = bool(data.get("breaking", False))

    status = data.get("status", "Draft")

    if status not in ["Draft", "Published"]:
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


# =========================
# DELETE ARTICLE
# =========================

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


# =========================
# ADMIN STATS
# =========================

@app.route("/api/admin/stats")
@admin_required
def admin_stats():

    db = get_db()

    total = db.execute(
        "SELECT COUNT(*) FROM articles"
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


# =========================
# HEALTH CHECK
# =========================

@app.route("/api/health")
def health():

    return jsonify({
        "status": "online",
        "service": "GLOBAL24"
    })


# =========================
# START
# =========================

init_db()


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
