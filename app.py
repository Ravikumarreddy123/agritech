"""
AgriTech — Refactored Main Application
Offline-first plant disease detection with optional Gemini online mode.
"""
import os
import io
import sys
import json
import sqlite3
from datetime import datetime, timedelta
from collections import Counter

import numpy as np
from PIL import Image
from werkzeug.utils import secure_filename

import tensorflow as tf
from tensorflow.keras.preprocessing import image as keras_image
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Dropout, GlobalAveragePooling2D
from tensorflow.keras.applications import MobileNetV2

from flask import (
    Flask, render_template, request, redirect,
    url_for, session, jsonify, flash
)
from flask_cors import CORS

# ── Config ───────────────────────────────────────────────────────────
import config

# ── Flask ────────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = config.SECRET_KEY
CORS(app)
os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)

# ── Database ─────────────────────────────────────────────────────────
from database.db import (
    init_db, migrate_history_table, migrate_feedback_table,
    save_history, get_connection, hash_password, check_password
)
init_db()
migrate_history_table()
migrate_feedback_table()

# ── ML Model ─────────────────────────────────────────────────────────
MODEL_LOADED = False
keras_model = None
CLASS_NAMES = None

try:
    base_model = MobileNetV2(
        input_shape=config.INPUT_SHAPE,
        include_top=False,
        weights='imagenet'
    )
    base_model.trainable = False

    keras_model = Sequential([
        base_model,
        GlobalAveragePooling2D(),
        Dense(512, activation='relu'),
        Dropout(0.2),
        Dense(config.NUM_CLASSES, activation='softmax')
    ])
    keras_model.load_weights(config.MODEL_PATH)
    keras_model.compile(optimizer='adam', loss='categorical_crossentropy', metrics=['accuracy'])

    # Warm up
    _ = keras_model.predict(np.zeros((1, 224, 224, 3)), verbose=0)
    MODEL_LOADED = True
    print("[OK] Model loaded and ready.")

except Exception as e:
    print(f"[ERROR] Model load failed: {e}")

# Load class names
try:
    with open(config.CLASS_INDICES_PATH, "r", encoding="utf-8") as f:
        class_indices = json.load(f)
    inv = {int(v): k for k, v in class_indices.items()}
    CLASS_NAMES = [inv[i] for i in range(len(inv))]
    print(f"[OK] Loaded {len(CLASS_NAMES)} class names.")
except Exception as e:
    print(f"[WARN] class_indices load failed: {e}")
    CLASS_NAMES = [
        "Pepper__bell___Bacterial_spot", "Pepper__bell___healthy",
        "Potato___Early_blight", "Potato___Late_blight", "Potato___healthy",
        "Tomato_Bacterial_spot", "Tomato_Early_blight", "Tomato_Late_blight",
        "Tomato_Leaf_Mold", "Tomato_Septoria_leaf_spot",
        "Tomato_Spider_mites_Two_spotted_spider_mite", "Tomato__Target_Spot",
        "Tomato__Tomato_YellowLeaf__Curl_Virus", "Tomato__Tomato_mosaic_virus",
        "Tomato_healthy"
    ]

# ── Gemini ───────────────────────────────────────────────────────────
gen_client = None
if config.GEMINI_API_KEY:
    try:
        from google import genai as google_genai
        from google.genai import types as genai_types
        gen_client = google_genai.Client(api_key=config.GEMINI_API_KEY)
        print("[OK] Gemini client ready.")
    except Exception as e:
        print(f"[WARN] Gemini init failed: {e}")
else:
    print("[INFO] GEMINI_API_KEY not set. Offline mode only.")

# ── Advisory & Risk ──────────────────────────────────────────────────
try:
    from advisory.advisory_service import get_advisory, list_diseases
    ADVISORY_LOADED = True
    print("[OK] Advisory service loaded.")
except Exception as e:
    ADVISORY_LOADED = False
    print(f"[WARN] Advisory service failed: {e}")

try:
    from risk.risk_engine import calculate_risk
    RISK_LOADED = True
    print("[OK] Risk engine loaded.")
except Exception as e:
    RISK_LOADED = False
    print(f"[WARN] Risk engine failed: {e}")

try:
    from ml.image_validator import validate_image
    VALIDATOR_LOADED = True
    print("[OK] Image validator loaded.")
except Exception as e:
    VALIDATOR_LOADED = False
    print(f"[WARN] Image validator failed: {e}")

# ── Utilities ────────────────────────────────────────────────────────
def format_disease_name(name):
    """Convert raw class name to readable disease name."""
    name = name.replace("___", " ").replace("__", " ").replace("_", " ")
    # Clean up multiple spaces
    name = " ".join(name.split())
    return name.title()

def extract_crop(disease_name):
    """Extract crop name from disease name."""
    dl = disease_name.lower()
    if "tomato" in dl:
        return "Tomato"
    elif "potato" in dl:
        return "Potato"
    elif "pepper" in dl:
        return "Bell Pepper"
    return "Unknown"

def get_gemini_info(disease_name):
    """Get detailed disease info from Gemini AI (online mode)."""
    if gen_client is None:
        return None
    try:
        from google.genai import types as genai_types
        prompt = (
            f"Give causes, cure, prevention and farmer recommendations for '{disease_name}' in plants.\n"
            "Return JSON with keys: causes, cure, prevention, recommendations (each a list of strings, max 3 items each)."
        )
        response = gen_client.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=prompt,
            config=genai_types.GenerateContentConfig(
                temperature=0.7,
                max_output_tokens=1024,
                response_mime_type="application/json",
            ),
        )
        return json.loads(response.text.strip())
    except Exception as e:
        print(f"[Gemini Error] {e}")
        return None

def parse_env(form):
    """Parse and validate optional environmental conditions from form.
    Accepts either:
      - Individual form fields: temperature, humidity, soil_moisture, leaf_wetness
      - JSON string in 'env' field (sent by detect.js)
    """
    env = {}
    errors = []
    fields = {
        "temperature":   (0.0, 60.0),
        "humidity":      (0.0, 100.0),
        "soil_moisture": (0.0, 100.0),
        "leaf_wetness":  (0.0, 100.0),
    }

    # Check for JSON env string first (detect.js sends this)
    env_json = form.get("env", "").strip()
    if env_json:
        try:
            parsed = json.loads(env_json)
            if isinstance(parsed, dict):
                for field, (mn, mx) in fields.items():
                    if field in parsed and parsed[field] is not None:
                        try:
                            fval = float(parsed[field])
                            if mn <= fval <= mx:
                                env[field] = fval
                            else:
                                errors.append(f"{field} must be between {mn} and {mx}")
                        except (ValueError, TypeError):
                            errors.append(f"{field} must be a number")
                return env, errors
        except json.JSONDecodeError:
            pass  # Fall through to individual field parsing

    # Individual form fields
    for field, (mn, mx) in fields.items():
        val = form.get(field, "").strip()
        if val:
            try:
                fval = float(val)
                if not (mn <= fval <= mx):
                    errors.append(f"{field} must be between {mn} and {mx}")
                else:
                    env[field] = fval
            except ValueError:
                errors.append(f"{field} must be a number")
    return env, errors

# ── Routes ───────────────────────────────────────────────────────────
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/contact")
def contact():
    return render_template("contact.html")

@app.route("/detect")
def detect():
    return render_template("Agri_tech.html")

# ── Auth ──────────────────────────────────────────────────────────────
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        if not email or not password:
            return render_template("login.html", error="Please enter email and password.")

        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT id, name, email, password FROM users WHERE email=?", (email,))
        user = c.fetchone()
        conn.close()

        if user and check_password(password, user[3]):
            # Re-hash if legacy plaintext password detected
            if not user[3].startswith("pbkdf2:") and not user[3].startswith("scrypt:"):
                conn2 = get_connection()
                c2 = conn2.cursor()
                c2.execute("UPDATE users SET password=? WHERE email=?", (hash_password(password), email))
                conn2.commit()
                conn2.close()

            session["user_email"] = user[2]
            session["user_name"] = user[1]
            return redirect(url_for("home"))
        else:
            return render_template("login.html", error="Invalid email or password.")

    return render_template("login.html")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        if not name or not email or not password:
            return render_template("signup.html", error="All fields are required.")
        if len(password) < 6:
            return render_template("signup.html", error="Password must be at least 6 characters.")

        conn = get_connection()
        c = conn.cursor()
        try:
            c.execute(
                "INSERT INTO users (name, email, password) VALUES (?, ?, ?)",
                (name, email, hash_password(password))
            )
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            return render_template("signup.html", error="Email already registered.")
        finally:
            conn.close()
        flash("Account created! Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("signup.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

# ── Predict ───────────────────────────────────────────────────────────
@app.route("/predict", methods=["POST"])
def predict():
    if not MODEL_LOADED or keras_model is None:
        return jsonify({"error": "ML model is not available. Please restart the server."}), 503

    if "file" not in request.files:
        return jsonify({"error": "No file uploaded."}), 400

    fp = request.files["file"]
    if fp.filename == "":
        return jsonify({"error": "No file selected."}), 400

    try:
        img_bytes = fp.read()
    except Exception:
        return jsonify({"error": "Could not read uploaded file."}), 400

    # ── Image Validation ──
    validation_error = None
    if VALIDATOR_LOADED:
        val_result = validate_image(img_bytes, fp.filename)
        if not val_result["valid"]:
            return jsonify({
                "error": "validation",
                "validation_error": val_result["reason"],
                "message": val_result["reason"]
            }), 422
    else:
        # Basic fallback validation
        ext = os.path.splitext(fp.filename)[1].lower().lstrip(".")
        if ext not in config.ALLOWED_EXTENSIONS:
            return jsonify({"error": "Unsupported file type. Please upload a PNG or JPEG image."}), 422
        if len(img_bytes) > config.MAX_UPLOAD_SIZE_BYTES:
            return jsonify({"error": f"File too large. Maximum size is {config.MAX_UPLOAD_SIZE_BYTES // (1024*1024)}MB."}), 422

    # ── Parse request options ──
    mode = request.form.get("mode", "offline").lower()
    # detect.js sends 'lang', also accept 'language' for compatibility
    language = request.form.get("lang") or request.form.get("language", config.DEFAULT_LANGUAGE)
    if language not in config.SUPPORTED_LANGUAGES:
        language = config.DEFAULT_LANGUAGE

    env, env_errors = parse_env(request.form)
    if env_errors:
        return jsonify({"error": "Invalid environmental values: " + "; ".join(env_errors)}), 422

    # ── Preprocess & Predict ──
    try:
        pil_img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        pil_img_resized = pil_img.resize((224, 224))
        arr = keras_image.img_to_array(pil_img_resized)
        arr = (arr / 127.5) - 1.0
        arr = np.expand_dims(arr, axis=0)

        preds = keras_model.predict(arr, verbose=0)
        idx = int(np.argmax(preds, axis=1)[0])
        confidence = float(preds[0][idx])
        low_confidence = confidence < config.CONFIDENCE_THRESHOLD

        if 0 <= idx < len(CLASS_NAMES):
            disease_raw = CLASS_NAMES[idx]
        else:
            disease_raw = f"Unknown_class_{idx}"

        disease = format_disease_name(disease_raw)
        crop = extract_crop(disease_raw)

    except Exception as e:
        print(f"[PREDICT ERROR] {e}")
        return jsonify({"error": "Image processing failed. Please try a different image."}), 500

    # ── Save Image ──
    try:
        safe_name = secure_filename(f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
        file_path = os.path.join(config.UPLOAD_FOLDER, safe_name)
        pil_img.save(file_path)
    except Exception as e:
        print(f"[SAVE ERROR] {e}")
        file_path = ""

    # ── Advisory ──
    is_healthy = "healthy" in disease.lower()

    if mode == "online" and gen_client is not None and not is_healthy:
        gemini_data = get_gemini_info(disease)
        if gemini_data:
            advisory = {
                "symptoms": "; ".join(gemini_data.get("causes", ["See local resources"])),
                "cause": "; ".join(gemini_data.get("causes", ["Information not available"])),
                "treatment": "; ".join(gemini_data.get("cure", ["Consult local agricultural officer"])),
                "prevention": "; ".join(gemini_data.get("prevention", ["Practice good agricultural practices"])),
                "risk_factors": gemini_data.get("recommendations", []),
                "safety": "Use only products approved in your region. Follow local agricultural guidance.",
                "language_used": "en",
                "fallback": False,
                "source": "gemini"
            }
            actual_mode = "online"
        else:
            # Gemini failed, fall back to offline
            advisory = _get_local_advisory(disease, is_healthy, language)
            actual_mode = "offline"
            advisory["gemini_failed"] = True
    else:
        advisory = _get_local_advisory(disease, is_healthy, language)
        actual_mode = "offline"

    # ── Risk Estimation ──
    if RISK_LOADED:
        risk = calculate_risk(disease_raw, env)
    else:
        if env:
            risk = {"level": "GENERAL", "score": 0, "reasons": ["Risk engine unavailable"], "env_provided": True}
        else:
            risk = {"level": "GENERAL", "score": 0, "reasons": ["Environmental conditions not provided. This is a general disease risk assessment."], "env_provided": False}

    # ── Save to Database ──
    try:
        user_email = session.get("user_email", "guest")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        save_history(
            user_email=user_email,
            disease=disease,
            crop=crop,
            confidence=round(confidence, 4),
            file_path=file_path,
            timestamp=timestamp,
            temperature=env.get("temperature"),
            humidity=env.get("humidity"),
            soil_moisture=env.get("soil_moisture"),
            leaf_wetness=env.get("leaf_wetness"),
            risk_level=risk.get("level"),
            mode=actual_mode,
            language=language
        )
    except Exception as e:
        print(f"[DB SAVE ERROR] {e}")

    # ── Build Response ──
    return jsonify({
        "disease": disease,
        "crop": crop,
        "confidence": round(confidence, 4),
        "low_confidence": low_confidence,
        "advisory": advisory,
        "risk": risk,
        "mode": actual_mode,
        "language": language,
        "image_path": os.path.basename(file_path) if file_path else None
    })

def _get_local_advisory(disease, is_healthy, language):
    """Get advisory from local advisory.json database."""
    if is_healthy:
        return {
            "symptoms": "No disease symptoms detected. Plant appears healthy.",
            "cause": "N/A",
            "treatment": "No treatment needed. Continue regular care.",
            "prevention": "Continue regular watering, adequate sunlight, and monitor for any new symptoms.",
            "risk_factors": ["Overwatering", "Poor drainage", "Insufficient sunlight"],
            "safety": "No chemical treatment required.",
            "language_used": language,
            "fallback": False,
            "source": "local"
        }

    if ADVISORY_LOADED:
        advisory = get_advisory(disease, language)
        advisory["source"] = "local"
        return advisory
    else:
        return {
            "symptoms": "Advisory database not available.",
            "cause": "Please consult your local agricultural extension officer.",
            "treatment": "Contact local agricultural guidance for treatment advice.",
            "prevention": "Practice general good agricultural practices.",
            "risk_factors": [],
            "safety": "Always follow local agricultural guidance and approved product labels.",
            "language_used": "en",
            "fallback": True,
            "source": "fallback"
        }

# ── API: Advisory ─────────────────────────────────────────────────────
@app.route("/api/advisory/<path:disease_name>")
def api_advisory(disease_name):
    language = request.args.get("lang", config.DEFAULT_LANGUAGE)
    if language not in config.SUPPORTED_LANGUAGES:
        language = config.DEFAULT_LANGUAGE

    is_healthy = "healthy" in disease_name.lower()
    advisory = _get_local_advisory(disease_name, is_healthy, language)
    return jsonify(advisory)

# ── API: Risk ─────────────────────────────────────────────────────────
@app.route("/api/risk", methods=["POST"])
def api_risk():
    data = request.get_json(force=True) or {}
    disease = data.get("disease", "")
    env = data.get("env", {})

    if not RISK_LOADED:
        return jsonify({"level": "GENERAL", "score": 0, "reasons": ["Risk engine not available"], "env_provided": bool(env)})

    # Find raw disease name
    disease_raw = disease
    for cn in (CLASS_NAMES or []):
        if format_disease_name(cn).lower() == disease.lower():
            disease_raw = cn
            break

    result = calculate_risk(disease_raw, env)
    return jsonify(result)

# ── API: Languages ────────────────────────────────────────────────────
@app.route("/api/languages")
def api_languages():
    return jsonify(config.SUPPORTED_LANGUAGES)

# ── History ───────────────────────────────────────────────────────────
@app.route("/history")
def history():
    conn = get_connection()
    c = conn.cursor()

    per_page = 15
    page = int(request.args.get("page", 1))
    offset = (page - 1) * per_page

    user_history = []
    if "user_email" in session:
        user_email = session["user_email"]
        c.execute("""SELECT id, user_email, disease, crop, confidence, file_path, timestamp,
                         temperature, humidity, soil_moisture, leaf_wetness, risk_level, mode, language
                     FROM history WHERE user_email=? ORDER BY timestamp DESC""", (user_email,))
        rows = c.fetchall()
        user_history = [_row_to_dict(row) for row in rows]

    c.execute("SELECT COUNT(*) FROM history")
    total_records = c.fetchone()[0]
    total_pages = max(1, (total_records + per_page - 1) // per_page)

    c.execute("""SELECT id, user_email, disease, crop, confidence, file_path, timestamp,
                     temperature, humidity, soil_moisture, leaf_wetness, risk_level, mode, language
                 FROM history ORDER BY timestamp DESC LIMIT ? OFFSET ?""", (per_page, offset))
    rows = c.fetchall()

    c.execute("SELECT email, name FROM users")
    user_map = dict(c.fetchall())

    total_history = []
    for row in rows:
        d = _row_to_dict(row)
        d["user"] = user_map.get(row[1], "Guest") if row[1] != "guest" else "Guest"
        total_history.append(d)

    conn.close()

    return render_template("history.html",
                           user_history=user_history,
                           total_history=total_history,
                           current_page=page,
                           total_pages=total_pages)

def _row_to_dict(row):
    """Convert a history DB row to a display dict."""
    return {
        "id": row[0],
        "user": row[1],
        "disease": row[2] or "Unknown",
        "crop": row[3] or "Unknown",
        "confidence": f"{round((row[4] or 0) * 100, 1)}%" if row[4] else "N/A",
        "image_filename": os.path.basename(row[5]) if row[5] else "",
        "timestamp": row[6] or "",
        "temperature": row[7],
        "humidity": row[8],
        "soil_moisture": row[9],
        "leaf_wetness": row[10],
        "risk_level": row[11] or "GENERAL",
        "mode": row[12] or "offline",
        "language": row[13] or "en",
    }

# ── Dashboard ─────────────────────────────────────────────────────────
@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")

# ── API: History (for dashboard charts) ──────────────────────────────
@app.route("/api/history")
def api_history():
    conn = get_connection()
    c = conn.cursor()

    # User-specific data
    user_data = []
    if "user_email" in session:
        user_email = session["user_email"]
        c.execute("SELECT disease FROM history WHERE user_email=?", (user_email,))
        user_diseases = [row[0] for row in c.fetchall() if row[0]]
        user_counter = Counter(user_diseases)
        user_data = [{"disease": k, "count": v} for k, v in user_counter.most_common(10)]

    # Total data
    c.execute("SELECT disease FROM history")
    all_diseases = [row[0] for row in c.fetchall() if row[0]]
    total_counter = Counter(all_diseases)
    total_data = [{"disease": k, "count": v} for k, v in total_counter.most_common(10)]

    # Stats
    c.execute("SELECT COUNT(*), AVG(confidence) FROM history")
    stats_row = c.fetchone()
    total_count = stats_row[0] or 0
    avg_confidence = round((stats_row[1] or 0) * 100, 1)

    # Risk distribution
    c.execute("SELECT risk_level, COUNT(*) FROM history WHERE risk_level IS NOT NULL GROUP BY risk_level")
    risk_dist = {row[0]: row[1] for row in c.fetchall()}

    # Recent detections (last 5)
    c.execute("""SELECT disease, crop, confidence, risk_level, timestamp, mode
                 FROM history ORDER BY timestamp DESC LIMIT 5""")
    recent = [
        {
            "disease": row[0], "crop": row[1],
            "confidence": f"{round((row[2] or 0) * 100, 1)}%",
            "risk_level": row[3] or "GENERAL",
            "timestamp": row[4], "mode": row[5]
        }
        for row in c.fetchall()
    ]

    # Most common disease
    most_common = total_data[0]["disease"] if total_data else "N/A"

    conn.close()

    return jsonify({
        "total": total_data,
        "user": user_data,
        "stats": {
            "total_detections": total_count,
            "avg_confidence": avg_confidence,
            "most_common": most_common,
            "risk_distribution": risk_dist,
            "recent": recent
        }
    })

# ── Feedback ──────────────────────────────────────────────────────────
@app.route("/feedback", methods=["GET", "POST"])
def feedback():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        message = request.form.get("feedword", "").strip()
        rating = int(request.form.get("rating", 0))
        email = session.get("user_email", "guest")

        if not name or not message:
            return render_template("feedback.html", success=False, error="Name and message are required.")

        conn = get_connection()
        c = conn.cursor()

        if email == "guest":
            c.execute("SELECT timestamp FROM feedback WHERE user_email='guest' ORDER BY id DESC LIMIT 1")
            last = c.fetchone()
            if last and last[0]:
                try:
                    last_time = datetime.strptime(last[0], "%Y-%m-%d %H:%M:%S")
                    if datetime.now() - last_time < timedelta(seconds=60):
                        conn.close()
                        return render_template("feedback.html", success=False, error="Please wait before submitting again.")
                except ValueError:
                    pass

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c.execute(
            "INSERT INTO feedback (user_email, name, message, rating, timestamp) VALUES (?, ?, ?, ?, ?)",
            (email, name, message, rating, timestamp)
        )
        conn.commit()
        conn.close()
        return render_template("feedback.html", success=True)

    return render_template("feedback.html", success=False)

@app.route("/feedback-history")
def feedback_history():
    conn = get_connection()
    c = conn.cursor()

    user_email = session.get("user_email")
    user_feedback = []
    if user_email:
        c.execute("SELECT name, message, rating, timestamp FROM feedback WHERE user_email=? ORDER BY id DESC", (user_email,))
        user_feedback = [{"name": r[0], "message": r[1], "rating": r[2], "timestamp": r[3]} for r in c.fetchall()]

    c.execute("SELECT name, message, rating, timestamp FROM feedback ORDER BY id DESC")
    all_feedback = [{"name": r[0], "message": r[1], "rating": r[2], "timestamp": r[3]} for r in c.fetchall()]

    c.execute("SELECT COUNT(*), AVG(rating) FROM feedback")
    stats = c.fetchone()
    conn.close()

    return render_template("feedback_history.html",
                           user_feedback=user_feedback,
                           all_feedback=all_feedback,
                           total_count=stats[0] or 0,
                           avg_rating=round(stats[1] or 0, 2))

@app.route("/api/feedback-ratings")
def feedback_ratings():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT rating, COUNT(*) FROM feedback GROUP BY rating")
    rows = c.fetchall()
    conn.close()
    return jsonify({str(r): cnt for r, cnt in rows})

# ── ESP32-CAM Endpoint ────────────────────────────────────────────────
@app.route("/esp32/predict", methods=["POST"])
def esp32_predict():
    """
    Lightweight endpoint for ESP32-CAM hardware integration.
    Accepts raw image bytes via POST body or multipart form.
    Returns minimal JSON: disease, confidence, crop, risk_level.
    """
    if not MODEL_LOADED:
        return jsonify({"error": "Model not ready"}), 503

    try:
        # Accept raw bytes (Content-Type: image/jpeg) OR multipart form
        if request.content_type and request.content_type.startswith("image/"):
            img_bytes = request.data
        elif "file" in request.files:
            img_bytes = request.files["file"].read()
        else:
            img_bytes = request.data  # fallback: raw body

        if not img_bytes:
            return jsonify({"error": "No image data received"}), 400

        # Preprocess — same pipeline as /predict
        pil_img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        pil_img_resized = pil_img.resize((224, 224))
        arr = keras_image.img_to_array(pil_img_resized)
        arr = (arr / 127.5) - 1.0
        arr = np.expand_dims(arr, axis=0)

        preds = keras_model.predict(arr, verbose=0)
        idx = int(np.argmax(preds, axis=1)[0])
        confidence = float(preds[0][idx])

        disease_raw = CLASS_NAMES[idx] if CLASS_NAMES else f"class_{idx}"
        disease_name = format_disease_name(disease_raw)
        crop = extract_crop(disease_raw)
        confidence_pct = round(confidence * 100, 1)
        low_conf = confidence < config.CONFIDENCE_THRESHOLD

        # Risk calculation (no env data from ESP32 — defaults apply)
        risk_level = "UNKNOWN"
        if RISK_LOADED:
            try:
                risk_result = calculate_risk(disease_raw, {})
                risk_level = risk_result.get("level", "UNKNOWN")
            except Exception:
                pass

        # Compact OLED-friendly response (short strings)
        response = {
            "disease":    disease_name,
            "crop":       crop,
            "confidence": confidence_pct,
            "risk":       risk_level,
            "low_conf":   low_conf,
            # OLED 2-line version (max ~21 chars per line for 128x64)
            "oled_line1": disease_name[:21],
            "oled_line2": f"Conf: {confidence_pct}% {risk_level}"[:21]
        }

        print(f"[ESP32] Detected: {disease_name} ({confidence_pct}%) | Risk: {risk_level}")
        return jsonify(response), 200

    except Exception as e:
        print(f"[ESP32] Error: {e}")
        return jsonify({"error": str(e)}), 500


# ── Run ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("[OK] Starting AgriTech Flask app...")
    app.run(host='0.0.0.0', port=5050, debug=True)
