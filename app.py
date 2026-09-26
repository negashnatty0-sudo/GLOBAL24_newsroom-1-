
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from pathlib import Path
from datetime import datetime

app = Flask(__name__)
app.secret_key = "CHANGE_THIS_SECRET_KEY"
ADMIN_PASSWORD = "admin123"  # change in Railway environment variables

NEWS = [
    {"title":"Global Newsroom Is Live","category":"WORLD","summary":"Your 24/7 international news dashboard is ready for publishing.","image":"https://images.unsplash.com/photo-1504711434969-e33886168f5c?auto=format&fit=crop&w=1200&q=80","breaking":True},
    {"title":"Africa Desk","category":"AFRICA","summary":"Follow major developments across Africa from your newsroom.","image":"https://images.unsplash.com/photo-1523805009345-7448845a9e53?auto=format&fit=crop&w=1000&q=80","breaking":False},
    {"title":"Ethiopia Focus","category":"ETHIOPIA","summary":"A dedicated section for Ethiopia and regional coverage.","image":"https://images.unsplash.com/photo-1524498250077-390f9e378fc0?auto=format&fit=crop&w=1000&q=80","breaking":False},
]

@app.route("/")
def home():
    return render_template("index.html", news=NEWS)

@app.route("/admin", methods=["GET","POST"])
def admin():
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["admin"] = True
            return redirect(url_for("admin"))
        return render_template("admin.html", error="Incorrect password")
    if not session.get("admin"):
        return render_template("login.html")
    return render_template("admin.html", news=NEWS)

@app.post("/admin/add")
def add_news():
    if not session.get("admin"):
        return redirect(url_for("admin"))
    NEWS.insert(0, {
        "title": request.form.get("title","Untitled"),
        "category": request.form.get("category","WORLD").upper(),
        "summary": request.form.get("summary",""),
        "image": request.form.get("image","https://images.unsplash.com/photo-1504711434969-e33886168f5c?auto=format&fit=crop&w=1200&q=80"),
        "breaking": request.form.get("breaking") == "on"
    })
    return redirect(url_for("admin"))

@app.get("/admin/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

@app.get("/api/news")
def api_news():
    return jsonify({"updated": datetime.utcnow().isoformat()+"Z", "stories": NEWS})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
