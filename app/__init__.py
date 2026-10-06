"""Application de suivi des demandes de livraison."""

import hmac
import logging
import os
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, abort, g, jsonify, redirect, render_template, request, session, url_for

STATUSES = {"pending": "À préparer", "ready": "Prête", "delivered": "Livrée"}
ENVIRONMENTS = {"development": "Développement", "staging": "Préproduction", "production": "Production"}


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(g.app_database, timeout=10)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.logger.setLevel(logging.INFO)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY") or secrets.token_hex(32),
        DATABASE=os.environ.get("DATABASE_PATH", str(Path(app.instance_path) / "delivery.db")),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "false").lower() == "true",
        MAX_CONTENT_LENGTH=16 * 1024,
        APP_VERSION=os.environ.get("APP_VERSION", "0.1.0"),
    )
    if test_config:
        app.config.update(test_config)
    Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)

    @app.before_request
    def prepare_request():
        g.app_database = app.config["DATABASE"]
        if request.method == "POST":
            expected = session.get("csrf_token", "")
            supplied = request.form.get("csrf_token", "")
            if not expected or not hmac.compare_digest(expected.encode(), supplied.encode()):
                abort(400, description="Formulaire expiré. Rechargez la page et réessayez.")

    @app.teardown_appcontext
    def close_db(error=None):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    @app.context_processor
    def template_context():
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_hex(32)
        return dict(statuses=STATUSES, environments=ENVIRONMENTS, version=app.config["APP_VERSION"])

    @app.after_request
    def secure_headers(response):
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; style-src 'self'; script-src 'none'; "
            "img-src 'self'; object-src 'none'; base-uri 'none'; "
            "frame-ancestors 'none'; form-action 'self'"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Cache-Control"] = "no-store"
        return response

    def record_event(db, delivery_id, action):
        db.execute(
            "INSERT INTO events (delivery_id, action, created_at) VALUES (?, ?, ?)",
            (delivery_id, action, datetime.now(timezone.utc).isoformat(timespec="seconds")),
        )
        app.logger.info("delivery_id=%s action=%s", delivery_id, action)

    @app.get("/")
    def index():
        status = request.args.get("status", "")
        if status and status not in STATUSES:
            abort(400, description="Statut inconnu.")
        db = get_db()
        deliveries = db.execute(
            "SELECT * FROM deliveries WHERE (? = '' OR status = ?) ORDER BY id DESC",
            (status, status),
        ).fetchall()
        counts = {key: 0 for key in STATUSES}
        for row in db.execute("SELECT status, COUNT(*) AS count FROM deliveries GROUP BY status"):
            counts[row["status"]] = row["count"]
        return render_template("index.html", deliveries=deliveries, counts=counts, selected_status=status)

    @app.route("/deliveries/new", methods=["GET", "POST"])
    def new_delivery():
        errors = []
        values = {}
        if request.method == "POST":
            for key in ("name", "release", "environment", "description"):
                values[key] = request.form.get(key, "").strip()
            if not 1 <= len(values["name"]) <= 80:
                errors.append("Le nom doit contenir entre 1 et 80 caractères.")
            if not 1 <= len(values["release"]) <= 40:
                errors.append("La version doit contenir entre 1 et 40 caractères.")
            if values["environment"] not in ENVIRONMENTS:
                errors.append("Choisissez un environnement valide.")
            if len(values["description"]) > 1000:
                errors.append("La description est limitée à 1 000 caractères.")
            if not errors:
                db = get_db()
                with db:
                    cursor = db.execute(
                        "INSERT INTO deliveries (name, release, environment, description, created_at) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (values["name"], values["release"], values["environment"], values["description"],
                         datetime.now(timezone.utc).isoformat(timespec="seconds")),
                    )
                    record_event(db, cursor.lastrowid, "Demande créée")
                return redirect(url_for("detail", delivery_id=cursor.lastrowid), code=303)
        return render_template("new.html", errors=errors, values=values), 422 if errors else 200

    def find_delivery(delivery_id):
        row = get_db().execute("SELECT * FROM deliveries WHERE id = ?", (delivery_id,)).fetchone()
        if row is None:
            abort(404, description="Cette demande n'existe pas.")
        return row

    @app.get("/deliveries/<int:delivery_id>")
    def detail(delivery_id):
        delivery = find_delivery(delivery_id)
        events = get_db().execute(
            "SELECT * FROM events WHERE delivery_id = ? ORDER BY id DESC", (delivery_id,)
        ).fetchall()
        return render_template("detail.html", delivery=delivery, events=events)

    @app.post("/deliveries/<int:delivery_id>/status")
    def update_status(delivery_id):
        delivery = find_delivery(delivery_id)
        status = request.form.get("status", "")
        if status not in STATUSES:
            abort(400, description="Statut inconnu.")
        if status != delivery["status"]:
            db = get_db()
            with db:
                db.execute("UPDATE deliveries SET status = ? WHERE id = ?", (status, delivery_id))
                record_event(db, delivery_id, "Statut : " + STATUSES[status])
        return redirect(url_for("detail", delivery_id=delivery_id), code=303)

    @app.get("/healthz")
    def health():
        return jsonify(status="ok", version=app.config["APP_VERSION"])

    @app.get("/readyz")
    def ready():
        try:
            get_db().execute("SELECT id FROM deliveries LIMIT 1").fetchone()
        except sqlite3.Error:
            return jsonify(status="unavailable"), 503
        return jsonify(status="ready")

    @app.errorhandler(400)
    @app.errorhandler(404)
    @app.errorhandler(413)
    def error_page(error):
        return render_template("error.html", error=error), error.code

    with app.app_context():
        g.app_database = app.config["DATABASE"]
        with get_db() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS deliveries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    release TEXT NOT NULL,
                    environment TEXT NOT NULL CHECK(environment IN ('development','staging','production')),
                    description TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','ready','delivered')),
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    delivery_id INTEGER NOT NULL REFERENCES deliveries(id),
                    action TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
            """)
    return app
