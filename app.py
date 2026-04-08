"""
=============================================================
  רויאל-מד | ROYAL-MED AI SYSTEM
  מערכת AI פנימית למרכז אסתטיקה רפואית
  גרסה: 1.0
=============================================================
  הרצה: python app.py
  כתובת: http://localhost:5000
=============================================================
"""

import json
import os
import uuid
from datetime import datetime
from functools import wraps
from pathlib import Path

from dotenv import load_dotenv
from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, jsonify, send_from_directory
)
from werkzeug.utils import secure_filename

# טעינת משתני סביבה
load_dotenv()

# אתחול מסד נתונים
from database.models import init_database, get_stats, get_recent_consultations, \
    get_all_patients, create_patient, get_patient, search_patients, \
    save_consultation, save_visualization, get_patient_consultations, \
    get_patient_visualizations, save_chat_message, get_chat_history, \
    create_custom_agent, get_all_custom_agents, get_custom_agent, \
    update_custom_agent, delete_custom_agent, save_agent_message, get_agent_conversation

from agents.diagnosis_agent import run_diagnosis_agent
from agents.visualization_agent import run_visualization_agent

# ─────────────────────────────────────────────
#  הגדרות האפליקציה
# ─────────────────────────────────────────────

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "royal-med-secret-2024-change-this")

# אתחול מסד נתונים — רץ תמיד (גם עם gunicorn)
init_database()

UPLOAD_FOLDER = Path(__file__).parent / "static" / "uploads"
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
app.config["UPLOAD_FOLDER"] = str(UPLOAD_FOLDER)
app.config["MAX_CONTENT_LENGTH"] = 15 * 1024 * 1024  # 15MB

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}

# סיסמת כניסה (ניתן לשנות ב-.env)
SYSTEM_PASSWORD = os.getenv("SYSTEM_PASSWORD", "royalmed2024")


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# ─────────────────────────────────────────────
#  הגנת כניסה
# ─────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


# ─────────────────────────────────────────────
#  עמודי כניסה
# ─────────────────────────────────────────────

@app.route("/", methods=["GET"])
def index():
    if session.get("logged_in"):
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        password = request.form.get("password", "")
        if password == SYSTEM_PASSWORD:
            session["logged_in"] = True
            session["session_id"] = str(uuid.uuid4())
            return redirect(url_for("dashboard"))
        else:
            error = "סיסמה שגויה. אנא נסה שנית."
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ─────────────────────────────────────────────
#  דאשבורד ראשי
# ─────────────────────────────────────────────

@app.route("/dashboard")
@login_required
def dashboard():
    stats = get_stats()
    recent = get_recent_consultations(5)
    return render_template("dashboard.html", stats=stats, recent=recent)


# ─────────────────────────────────────────────
#  Agent 1 — פענוח ואבחון
# ─────────────────────────────────────────────

@app.route("/diagnosis", methods=["GET"])
@login_required
def diagnosis():
    treatments = load_treatments_flat()
    patients = get_all_patients()
    return render_template("diagnosis.html", treatments=treatments, patients=patients)


@app.route("/api/diagnose", methods=["POST"])
@login_required
def api_diagnose():
    patient_name = request.form.get("patient_name", "").strip()
    patient_id = request.form.get("patient_id") or None
    additional_info = request.form.get("additional_info", "")
    preferred_model = request.form.get("model", "openai")

    if "image" not in request.files:
        return jsonify({"success": False, "error": "לא הועלתה תמונה"})

    file = request.files["image"]
    if not file or not allowed_file(file.filename):
        return jsonify({"success": False, "error": "סוג קובץ לא נתמך"})

    # שמירת תמונה
    filename = secure_filename(f"diag_{uuid.uuid4().hex[:8]}_{file.filename}")
    image_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(image_path)

    # הרצת Agent
    result = run_diagnosis_agent(
        image_path=image_path,
        additional_info=additional_info,
        preferred_model=preferred_model,
        openai_key=os.getenv("OPENAI_API_KEY", ""),
        gemini_key=os.getenv("GEMINI_API_KEY", ""),
    )

    if result["success"]:
        # שמירה במסד נתונים
        save_consultation(
            patient_id=int(patient_id) if patient_id else None,
            patient_name=patient_name,
            consultation_type="diagnosis",
            image_path=f"uploads/{filename}",
            additional_info=additional_info,
            ai_result=result["result"],
            model_used=result.get("model", ""),
            tokens_used=result.get("tokens_used", 0),
        )
        return jsonify({"success": True, "result": result["result"], "model": result.get("model")})
    else:
        return jsonify({"success": False, "error": result.get("error", "שגיאה לא ידועה")})


# ─────────────────────────────────────────────
#  Agent 2 — הדמיית לפני/אחרי
# ─────────────────────────────────────────────

@app.route("/visualization", methods=["GET"])
@login_required
def visualization():
    treatments = load_treatments_flat()
    patients = get_all_patients()
    return render_template("visualization.html", treatments=treatments, patients=patients)


@app.route("/api/visualize", methods=["POST"])
@login_required
def api_visualize():
    patient_name = request.form.get("patient_name", "").strip()
    patient_id = request.form.get("patient_id") or None
    treatment_id = request.form.get("treatment_id", "")

    if not treatment_id:
        return jsonify({"success": False, "error": "יש לבחור טיפול"})

    if "image" not in request.files:
        return jsonify({"success": False, "error": "לא הועלתה תמונה"})

    file = request.files["image"]
    if not file or not allowed_file(file.filename):
        return jsonify({"success": False, "error": "סוג קובץ לא נתמך"})

    # שמירת תמונת לפני
    filename = secure_filename(f"before_{uuid.uuid4().hex[:8]}_{file.filename}")
    image_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(image_path)

    # הרצת Agent
    result = run_visualization_agent(
        image_path=image_path,
        treatment_id=treatment_id,
        save_dir=str(UPLOAD_FOLDER),
        openai_key=os.getenv("OPENAI_API_KEY", ""),
        gemini_key=os.getenv("GEMINI_API_KEY", ""),
    )

    if result["success"]:
        after_path = result.get("after_path", "")
        after_filename = os.path.basename(after_path) if after_path else ""

        # שמירה במסד נתונים
        save_visualization(
            patient_id=int(patient_id) if patient_id else None,
            patient_name=patient_name,
            before_image_path=f"uploads/{filename}",
            after_image_path=f"uploads/{after_filename}" if after_filename else "",
            after_image_url=result.get("after_url", ""),
            treatment_id=treatment_id,
            treatment_name=result["treatment"].get("name", ""),
            prompt_used=result.get("prompt_used", ""),
        )

        return jsonify({
            "success": True,
            "before_url": url_for("static", filename=f"uploads/{filename}"),
            "after_url": (
                url_for("static", filename=f"uploads/{after_filename}")
                if after_filename else result.get("after_url", "")
            ),
            "treatment": result["treatment"],
        })
    else:
        return jsonify({"success": False, "error": result.get("error", "שגיאה ביצירת הדמיה")})


# ─────────────────────────────────────────────
#  ניהול מטופלים
# ─────────────────────────────────────────────

@app.route("/patients")
@login_required
def patients():
    query = request.args.get("q", "")
    if query:
        patient_list = search_patients(query)
    else:
        patient_list = get_all_patients()
    return render_template("patients.html", patients=patient_list, query=query)


@app.route("/patients/new", methods=["POST"])
@login_required
def new_patient():
    name = request.form.get("name", "").strip()
    phone = request.form.get("phone", "").strip()
    birth_year_str = request.form.get("birth_year", "")
    notes = request.form.get("notes", "")

    if not name:
        flash("שם מטופל הוא שדה חובה", "error")
        return redirect(url_for("patients"))

    birth_year = int(birth_year_str) if birth_year_str.isdigit() else None
    patient_id = create_patient(name, phone, birth_year, notes)
    flash(f"מטופל {name} נוסף בהצלחה", "success")
    return redirect(url_for("patient_history", patient_id=patient_id))


@app.route("/patients/<int:patient_id>")
@login_required
def patient_history(patient_id):
    patient = get_patient(patient_id)
    if not patient:
        flash("מטופל לא נמצא", "error")
        return redirect(url_for("patients"))
    consultations = get_patient_consultations(patient_id)
    visualizations = get_patient_visualizations(patient_id)
    return render_template(
        "patient_history.html",
        patient=patient,
        consultations=consultations,
        visualizations=visualizations,
    )


# ─────────────────────────────────────────────
#  צ'אט AI
# ─────────────────────────────────────────────

@app.route("/chat")
@login_required
def chat():
    return render_template("chat.html")


@app.route("/api/chat", methods=["POST"])
@login_required
def api_chat():
    data = request.json
    user_message = data.get("message", "").strip()
    preferred_model = data.get("model", "openai")
    session_id = session.get("session_id", str(uuid.uuid4()))

    if not user_message:
        return jsonify({"success": False, "error": "הודעה ריקה"})

    # שמירת הודעת משתמש
    save_chat_message(session_id, "user", user_message)

    # טעינת היסטוריה
    history = get_chat_history(session_id, limit=20)

    try:
        if preferred_model == "openai":
            response_text = chat_with_openai(user_message, history)
        else:
            response_text = chat_with_gemini(user_message, history)

        # שמירת תשובת AI
        save_chat_message(session_id, "assistant", response_text, model_used=preferred_model)

        return jsonify({"success": True, "response": response_text})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


def chat_with_openai(message: str, history: list) -> str:
    from openai import OpenAI
    from agents.prompts import CHAT_SYSTEM_PROMPT, OPENAI_MODEL_CHAT

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    treatments = load_treatments_list_text()

    messages = [{"role": "system", "content": CHAT_SYSTEM_PROMPT.format(treatments_list=treatments)}]
    for h in history[-16:]:  # 8 הודעות אחרונות
        messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": message})

    response = client.chat.completions.create(
        model=OPENAI_MODEL_CHAT,
        messages=messages,
        max_tokens=1500,
        temperature=0.5,
    )
    return response.choices[0].message.content


def chat_with_gemini(message: str, history: list) -> str:
    import google.generativeai as genai
    from agents.prompts import CHAT_SYSTEM_PROMPT, GEMINI_MODEL_CHAT

    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    model = genai.GenerativeModel(GEMINI_MODEL_CHAT)
    treatments = load_treatments_list_text()

    # בניית היסטוריה עבור Gemini
    chat_session = model.start_chat(history=[
        {"role": "user" if h["role"] == "user" else "model", "parts": [h["content"]]}
        for h in history[-16:]
    ])

    system_context = CHAT_SYSTEM_PROMPT.format(treatments_list=treatments)
    full_message = f"{system_context}\n\nשאלת המשתמש: {message}"

    response = chat_session.send_message(full_message)
    return response.text


# ─────────────────────────────────────────────
#  Agents מותאמים אישית
# ─────────────────────────────────────────────

@app.route("/agents")
@login_required
def agents_list():
    agents = get_all_custom_agents()
    return render_template("agents.html", agents=agents)


@app.route("/agents/new", methods=["GET"])
@login_required
def agent_new():
    return render_template("agent_builder.html", agent=None, mode="new")


@app.route("/agents/<int:agent_id>/edit", methods=["GET"])
@login_required
def agent_edit(agent_id):
    agent = get_custom_agent(agent_id)
    if not agent:
        flash("Agent לא נמצא", "error")
        return redirect(url_for("agents_list"))
    return render_template("agent_builder.html", agent=agent, mode="edit")


@app.route("/api/agents/save", methods=["POST"])
@login_required
def api_agent_save():
    data = request.json
    agent_id = data.get("id")
    name = data.get("name", "").strip()
    description = data.get("description", "").strip()
    icon = data.get("icon", "🤖").strip()
    system_prompt = data.get("system_prompt", "").strip()
    knowledge = data.get("knowledge", "").strip()
    model = data.get("model", "gpt-4o")
    active = data.get("active", 1)

    if not name or not system_prompt:
        return jsonify({"success": False, "error": "שם ופרומפט הם שדות חובה"})

    if agent_id:
        update_custom_agent(agent_id, name, description, icon, system_prompt, knowledge, model, active)
        return jsonify({"success": True, "id": agent_id, "message": "Agent עודכן"})
    else:
        new_id = create_custom_agent(name, description, icon, system_prompt, knowledge, model)
        return jsonify({"success": True, "id": new_id, "message": "Agent נוצר בהצלחה"})


@app.route("/api/agents/<int:agent_id>/delete", methods=["POST"])
@login_required
def api_agent_delete(agent_id):
    delete_custom_agent(agent_id)
    return jsonify({"success": True})


@app.route("/agents/<int:agent_id>/chat")
@login_required
def agent_chat(agent_id):
    agent = get_custom_agent(agent_id)
    if not agent:
        flash("Agent לא נמצא", "error")
        return redirect(url_for("agents_list"))
    patients = get_all_patients()
    return render_template("agent_chat.html", agent=agent, patients=patients)


@app.route("/api/agents/<int:agent_id>/chat", methods=["POST"])
@login_required
def api_agent_chat(agent_id):
    agent = get_custom_agent(agent_id)
    if not agent:
        return jsonify({"success": False, "error": "Agent לא נמצא"})

    data = request.json
    user_message = data.get("message", "").strip()
    session_id = data.get("session_id", session.get("session_id", str(uuid.uuid4())))
    patient_name = data.get("patient_name", "")

    if not user_message:
        return jsonify({"success": False, "error": "הודעה ריקה"})

    # שמור הודעת משתמש
    save_agent_message(agent_id, session_id, "user", user_message, patient_name=patient_name)

    # טען היסטוריה
    history = get_agent_conversation(agent_id, session_id, limit=20)

    try:
        response_text = run_custom_agent(agent, user_message, history)
        save_agent_message(agent_id, session_id, "assistant", response_text)
        return jsonify({"success": True, "response": response_text})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


def run_custom_agent(agent: dict, message: str, history: list) -> str:
    """מריץ Agent מותאם אישית עם GPT או Gemini"""
    model = agent.get("model", "gpt-4o")
    system_prompt = agent.get("system_prompt", "")
    knowledge = agent.get("knowledge", "")

    # בניית system prompt מלא
    full_system = system_prompt
    if knowledge:
        full_system += f"\n\n--- ידע ובסיס מידע ---\n{knowledge}"
    full_system += "\n\nתמיד השב בעברית בצורה מקצועית וברורה."

    if model.startswith("gemini"):
        import google.generativeai as genai
        genai.configure(api_key=os.getenv("GEMINI_API_KEY", ""))
        gmodel = genai.GenerativeModel("gemini-2.0-flash")
        msgs = []
        for h in history[-16:]:
            msgs.append({
                "role": "user" if h["role"] == "user" else "model",
                "parts": [h["content"]]
            })
        chat = gmodel.start_chat(history=msgs)
        resp = chat.send_message(f"{full_system}\n\n{message}")
        return resp.text
    else:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))
        messages = [{"role": "system", "content": full_system}]
        for h in history[-16:]:
            messages.append({"role": h["role"], "content": h["content"]})
        messages.append({"role": "user", "content": message})
        resp = client.chat.completions.create(
            model=model, messages=messages, max_tokens=1500, temperature=0.5
        )
        return resp.choices[0].message.content


# ─────────────────────────────────────────────
#  הגדרות — ניהול API וטיפולים
# ─────────────────────────────────────────────

@app.route("/settings")
@login_required
def settings():
    treatments_path = Path(__file__).parent / "data" / "treatments.json"
    with open(treatments_path, "r", encoding="utf-8") as f:
        treatments_data = json.load(f)

    env_path = Path(__file__).parent / ".env"
    openai_key = os.getenv("OPENAI_API_KEY", "")
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    openai_set = bool(openai_key and len(openai_key) > 10)
    gemini_set = bool(gemini_key and len(gemini_key) > 10)

    return render_template(
        "settings.html",
        treatments_data=treatments_data,
        openai_set=openai_set,
        gemini_set=gemini_set,
    )


@app.route("/api/save-api-keys", methods=["POST"])
@login_required
def save_api_keys():
    openai_key = request.form.get("openai_key", "").strip()
    gemini_key = request.form.get("gemini_key", "").strip()
    new_password = request.form.get("new_password", "").strip()

    env_path = Path(__file__).parent / ".env"
    env_lines = []

    if env_path.exists():
        with open(env_path, "r") as f:
            env_lines = f.readlines()

    def set_env_var(lines, key, value):
        for i, line in enumerate(lines):
            if line.startswith(f"{key}="):
                lines[i] = f"{key}={value}\n"
                return lines
        lines.append(f"{key}={value}\n")
        return lines

    if openai_key:
        env_lines = set_env_var(env_lines, "OPENAI_API_KEY", openai_key)
        os.environ["OPENAI_API_KEY"] = openai_key

    if gemini_key:
        env_lines = set_env_var(env_lines, "GEMINI_API_KEY", gemini_key)
        os.environ["GEMINI_API_KEY"] = gemini_key

    if new_password:
        env_lines = set_env_var(env_lines, "SYSTEM_PASSWORD", new_password)
        os.environ["SYSTEM_PASSWORD"] = new_password
        global SYSTEM_PASSWORD
        SYSTEM_PASSWORD = new_password

    with open(env_path, "w") as f:
        f.writelines(env_lines)

    return jsonify({"success": True, "message": "ההגדרות נשמרו בהצלחה"})


@app.route("/api/treatments", methods=["GET"])
@login_required
def get_treatments_api():
    treatments_path = Path(__file__).parent / "data" / "treatments.json"
    with open(treatments_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return jsonify(data)


@app.route("/api/treatments/save", methods=["POST"])
@login_required
def save_treatments():
    data = request.json
    treatments_path = Path(__file__).parent / "data" / "treatments.json"
    data["last_updated"] = datetime.now().strftime("%Y-%m-%d")
    with open(treatments_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return jsonify({"success": True, "message": "רשימת הטיפולים עודכנה"})


# ─────────────────────────────────────────────
#  פונקציות עזר
# ─────────────────────────────────────────────

def load_treatments_flat() -> list:
    """מחזיר רשימה שטוחה של כל הטיפולים"""
    treatments_path = Path(__file__).parent / "data" / "treatments.json"
    with open(treatments_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    result = []
    for cat in data["categories"]:
        for t in cat["treatments"]:
            if t.get("active", True):
                t["category_name"] = cat["name"]
                result.append(t)
    return result


def load_treatments_list_text() -> str:
    treatments_path = Path(__file__).parent / "data" / "treatments.json"
    with open(treatments_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    lines = []
    for cat in data["categories"]:
        lines.append(f"\n{cat['name']}:")
        for t in cat["treatments"]:
            if t.get("active", True):
                lines.append(f"  - {t['name']}: {t['description']}")
    return "\n".join(lines)


# ─────────────────────────────────────────────
#  הרצה
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("  רויאל-מד | ROYAL-MED AI")
    print("  מערכת AI פנימית למרפאה")
    print("=" * 50)
    print(f"  כתובת: http://localhost:5000")
    print(f"  סיסמה: {SYSTEM_PASSWORD}")
    print("=" * 50 + "\n")
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
