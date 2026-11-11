import os, sqlite3
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, g
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "cricket_king.db")
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-before-deploying")

STARTING_COINS = 10000

def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(_error):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        coins INTEGER NOT NULL DEFAULT 10000,
        is_admin INTEGER NOT NULL DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS matches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        team_a TEXT NOT NULL,
        team_b TEXT NOT NULL,
        match_time TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'OPEN',
        winner TEXT
    );
    CREATE TABLE IF NOT EXISTS predictions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        match_id INTEGER NOT NULL,
        team TEXT NOT NULL,
        stake INTEGER NOT NULL,
        settled INTEGER NOT NULL DEFAULT 0,
        UNIQUE(user_id, match_id),
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(match_id) REFERENCES matches(id)
    );
    """)
    admin = conn.execute("SELECT id FROM users WHERE username='admin'").fetchone()
    if not admin:
        conn.execute("INSERT INTO users(username,password_hash,coins,is_admin) VALUES(?,?,?,1)",
                     ("admin", generate_password_hash("ChangeMe123!"), STARTING_COINS))
    count = conn.execute("SELECT COUNT(*) AS n FROM matches").fetchone()["n"]
    if count == 0:
        conn.executemany(
            "INSERT INTO matches(team_a,team_b,match_time,status) VALUES(?,?,?,'OPEN')",
            [("India", "Australia", "Demo match • Today"),
             ("Mumbai", "Chennai", "Demo match • Tomorrow")]
        )
    conn.commit()
    conn.close()

def login_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please login first.", "warning")
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapped

def admin_required(fn):
    @wraps(fn)
    @login_required
    def wrapped(*args, **kwargs):
        user = db().execute("SELECT is_admin FROM users WHERE id=?", (session["user_id"],)).fetchone()
        if not user or not user["is_admin"]:
            flash("Admin access only.", "danger")
            return redirect(url_for("index"))
        return fn(*args, **kwargs)
    return wrapped

@app.route("/")
def index():
    matches = db().execute("SELECT * FROM matches ORDER BY id DESC").fetchall()
    user = None
    if session.get("user_id"):
        user = db().execute("SELECT * FROM users WHERE id=?", (session["user_id"],)).fetchone()
    return render_template("index.html", matches=matches, user=user)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if len(username) < 3 or len(password) < 8:
            flash("Username must be 3+ characters and password 8+ characters.", "danger")
        else:
            try:
                db().execute("INSERT INTO users(username,password_hash,coins) VALUES(?,?,?)",
                             (username, generate_password_hash(password), STARTING_COINS))
                db().commit()
                flash("Account created. Please login.", "success")
                return redirect(url_for("login"))
            except sqlite3.IntegrityError:
                flash("That username is already taken.", "danger")
    return render_template("auth.html", mode="register")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = db().execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            flash("Welcome back!", "success")
            return redirect(url_for("index"))
        flash("Incorrect username or password.", "danger")
    return render_template("auth.html", mode="login")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))

@app.route("/predict/<int:match_id>", methods=["POST"])
@login_required
def predict(match_id):
    conn = db()
    match = conn.execute("SELECT * FROM matches WHERE id=?", (match_id,)).fetchone()
    team = request.form.get("team")
    try:
        stake = int(request.form.get("stake", "0"))
    except ValueError:
        stake = 0
    user = conn.execute("SELECT * FROM users WHERE id=?", (session["user_id"],)).fetchone()
    if not match or match["status"] != "OPEN":
        flash("This demo match is closed.", "danger")
    elif team not in (match["team_a"], match["team_b"]):
        flash("Choose one of the listed teams.", "danger")
    elif stake < 1 or stake > 5000:
        flash("Choose between 1 and 5,000 demo coins.", "danger")
    elif user["coins"] < stake:
        flash("Not enough demo coins.", "danger")
    else:
        try:
            conn.execute("INSERT INTO predictions(user_id,match_id,team,stake) VALUES(?,?,?,?)",
                         (session["user_id"], match_id, team, stake))
            conn.execute("UPDATE users SET coins=coins-? WHERE id=?", (stake, session["user_id"]))
            conn.commit()
            flash("Prediction saved. Demo coins only.", "success")
        except sqlite3.IntegrityError:
            flash("You already predicted on this match.", "warning")
    return redirect(url_for("index"))

@app.route("/my-predictions")
@login_required
def my_predictions():
    rows = db().execute("""
        SELECT p.*, m.team_a, m.team_b, m.status, m.winner
        FROM predictions p JOIN matches m ON m.id=p.match_id
        WHERE p.user_id=? ORDER BY p.id DESC
    """, (session["user_id"],)).fetchall()
    user = db().execute("SELECT * FROM users WHERE id=?", (session["user_id"],)).fetchone()
    return render_template("predictions.html", rows=rows, user=user)

@app.route("/admin")
@admin_required
def admin():
    matches = db().execute("SELECT * FROM matches ORDER BY id DESC").fetchall()
    users = db().execute("SELECT id,username,coins FROM users ORDER BY id").fetchall()
    return render_template("admin.html", matches=matches, users=users)

@app.route("/admin/match", methods=["POST"])
@admin_required
def add_match():
    a = request.form.get("team_a", "").strip()
    b = request.form.get("team_b", "").strip()
    when = request.form.get("match_time", "").strip() or "Demo fixture"
    if not a or not b or a.lower() == b.lower():
        flash("Enter two different team names.", "danger")
    else:
        db().execute("INSERT INTO matches(team_a,team_b,match_time) VALUES(?,?,?)", (a,b,when))
        db().commit()
        flash("Demo match added.", "success")
    return redirect(url_for("admin"))

@app.route("/admin/settle/<int:match_id>", methods=["POST"])
@admin_required
def settle(match_id):
    conn = db()
    match = conn.execute("SELECT * FROM matches WHERE id=?", (match_id,)).fetchone()
    winner = request.form.get("winner")
    if not match or match["status"] != "OPEN" or winner not in (match["team_a"], match["team_b"]):
        flash("Could not settle this match.", "danger")
        return redirect(url_for("admin"))
    picks = conn.execute("SELECT * FROM predictions WHERE match_id=? AND settled=0", (match_id,)).fetchall()
    for pick in picks:
        if pick["team"] == winner:
            # Simple demo game: a correct pick returns twice the stake (stake was deducted at prediction time).
            conn.execute("UPDATE users SET coins=coins+? WHERE id=?", (pick["stake"] * 2, pick["user_id"]))
        conn.execute("UPDATE predictions SET settled=1 WHERE id=?", (pick["id"],))
    conn.execute("UPDATE matches SET status='SETTLED', winner=? WHERE id=?", (winner, match_id))
    conn.commit()
    flash("Result saved and demo coins settled.", "success")
    return redirect(url_for("admin"))

@app.route("/admin/reset-demo-coins", methods=["POST"])
@admin_required
def reset_coins():
    db().execute("UPDATE users SET coins=? WHERE is_admin=0", (STARTING_COINS,))
    db().commit()
    flash("All user demo balances reset to 10,000.", "success")
    return redirect(url_for("admin"))

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
