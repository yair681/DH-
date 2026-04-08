"""
=============================================================
  רויאל-מד | מסד נתונים — SQLite
=============================================================
  מסד נתונים מקומי מלא — ללא תלות בשרת חיצוני
  כל הנתונים נשמרים במחשב המרפאה בלבד
=============================================================
"""

import sqlite3
import os
from datetime import datetime
from pathlib import Path


DB_PATH = Path(__file__).parent.parent / "data" / "royal_med.db"


def get_connection():
    """מחזיר חיבור למסד נתונים"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row  # מאפשר גישה לשדות לפי שם
    return conn


def init_database():
    """יוצר את כל הטבלאות אם לא קיימות"""
    conn = get_connection()
    c = conn.cursor()

    # טבלת מטופלים
    c.execute("""
        CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT,
            birth_year INTEGER,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # טבלת ייעוצי אבחון
    c.execute("""
        CREATE TABLE IF NOT EXISTS consultations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER,
            patient_name TEXT,
            consultation_type TEXT NOT NULL,  -- 'diagnosis' or 'visualization'
            image_path TEXT,
            additional_info TEXT,
            ai_result TEXT,
            treatment_id TEXT,
            treatment_name TEXT,
            model_used TEXT,
            tokens_used INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (patient_id) REFERENCES patients(id)
        )
    """)

    # טבלת הדמיות לפני/אחרי
    c.execute("""
        CREATE TABLE IF NOT EXISTS visualizations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER,
            patient_name TEXT,
            before_image_path TEXT,
            after_image_path TEXT,
            after_image_url TEXT,
            treatment_id TEXT,
            treatment_name TEXT,
            prompt_used TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (patient_id) REFERENCES patients(id)
        )
    """)

    # טבלת היסטוריית צ'אט
    c.execute("""
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            patient_id INTEGER,
            role TEXT NOT NULL,  -- 'user' or 'assistant'
            content TEXT NOT NULL,
            model_used TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # טבלת Agents מותאמים אישית
    c.execute("""
        CREATE TABLE IF NOT EXISTS custom_agents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            icon TEXT DEFAULT '🤖',
            system_prompt TEXT NOT NULL,
            knowledge TEXT DEFAULT '',
            model TEXT DEFAULT 'gpt-4o',
            active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # טבלת שיחות עם Agents מותאמים
    c.execute("""
        CREATE TABLE IF NOT EXISTS agent_conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id INTEGER NOT NULL,
            session_id TEXT NOT NULL,
            patient_id INTEGER,
            patient_name TEXT,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (agent_id) REFERENCES custom_agents(id)
        )
    """)

    conn.commit()
    conn.close()
    print(f"[DB] מסד נתונים אותחל: {DB_PATH}")


# ─────────────────────────────────────────────
#  מטופלים
# ─────────────────────────────────────────────

def create_patient(name: str, phone: str = "", birth_year: int = None, notes: str = "") -> int:
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "INSERT INTO patients (name, phone, birth_year, notes) VALUES (?, ?, ?, ?)",
        (name, phone, birth_year, notes),
    )
    patient_id = c.lastrowid
    conn.commit()
    conn.close()
    return patient_id


def get_all_patients() -> list:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM patients ORDER BY created_at DESC")
    rows = [dict(row) for row in c.fetchall()]
    conn.close()
    return rows


def get_patient(patient_id: int) -> dict:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM patients WHERE id = ?", (patient_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else {}


def search_patients(query: str) -> list:
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT * FROM patients WHERE name LIKE ? OR phone LIKE ? ORDER BY name",
        (f"%{query}%", f"%{query}%"),
    )
    rows = [dict(row) for row in c.fetchall()]
    conn.close()
    return rows


# ─────────────────────────────────────────────
#  ייעוצי אבחון
# ─────────────────────────────────────────────

def save_consultation(
    patient_id: int = None,
    patient_name: str = "",
    consultation_type: str = "diagnosis",
    image_path: str = "",
    additional_info: str = "",
    ai_result: str = "",
    treatment_id: str = "",
    treatment_name: str = "",
    model_used: str = "",
    tokens_used: int = 0,
) -> int:
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO consultations
        (patient_id, patient_name, consultation_type, image_path, additional_info,
         ai_result, treatment_id, treatment_name, model_used, tokens_used)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (patient_id, patient_name, consultation_type, image_path, additional_info,
          ai_result, treatment_id, treatment_name, model_used, tokens_used))
    record_id = c.lastrowid
    conn.commit()
    conn.close()
    return record_id


def get_patient_consultations(patient_id: int) -> list:
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT * FROM consultations WHERE patient_id = ? ORDER BY created_at DESC",
        (patient_id,),
    )
    rows = [dict(row) for row in c.fetchall()]
    conn.close()
    return rows


def get_recent_consultations(limit: int = 20) -> list:
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT * FROM consultations ORDER BY created_at DESC LIMIT ?",
        (limit,),
    )
    rows = [dict(row) for row in c.fetchall()]
    conn.close()
    return rows


# ─────────────────────────────────────────────
#  הדמיות
# ─────────────────────────────────────────────

def save_visualization(
    patient_id: int = None,
    patient_name: str = "",
    before_image_path: str = "",
    after_image_path: str = "",
    after_image_url: str = "",
    treatment_id: str = "",
    treatment_name: str = "",
    prompt_used: str = "",
) -> int:
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO visualizations
        (patient_id, patient_name, before_image_path, after_image_path,
         after_image_url, treatment_id, treatment_name, prompt_used)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (patient_id, patient_name, before_image_path, after_image_path,
          after_image_url, treatment_id, treatment_name, prompt_used))
    record_id = c.lastrowid
    conn.commit()
    conn.close()
    return record_id


def get_patient_visualizations(patient_id: int) -> list:
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "SELECT * FROM visualizations WHERE patient_id = ? ORDER BY created_at DESC",
        (patient_id,),
    )
    rows = [dict(row) for row in c.fetchall()]
    conn.close()
    return rows


# ─────────────────────────────────────────────
#  היסטוריית צ'אט
# ─────────────────────────────────────────────

def save_chat_message(session_id: str, role: str, content: str,
                      patient_id: int = None, model_used: str = "") -> None:
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO chat_history (session_id, patient_id, role, content, model_used)
        VALUES (?, ?, ?, ?, ?)
    """, (session_id, patient_id, role, content, model_used))
    conn.commit()
    conn.close()


def get_chat_history(session_id: str, limit: int = 50) -> list:
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT * FROM chat_history
        WHERE session_id = ?
        ORDER BY created_at ASC
        LIMIT ?
    """, (session_id, limit))
    rows = [dict(row) for row in c.fetchall()]
    conn.close()
    return rows


def create_custom_agent(name, description, icon, system_prompt, knowledge, model) -> int:
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO custom_agents (name, description, icon, system_prompt, knowledge, model)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (name, description, icon, system_prompt, knowledge, model))
    agent_id = c.lastrowid
    conn.commit()
    conn.close()
    return agent_id


def get_all_custom_agents() -> list:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM custom_agents ORDER BY created_at DESC")
    rows = [dict(row) for row in c.fetchall()]
    conn.close()
    return rows


def get_custom_agent(agent_id: int) -> dict:
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM custom_agents WHERE id = ?", (agent_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else {}


def update_custom_agent(agent_id: int, name, description, icon, system_prompt, knowledge, model, active) -> None:
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        UPDATE custom_agents
        SET name=?, description=?, icon=?, system_prompt=?, knowledge=?, model=?, active=?,
            updated_at=CURRENT_TIMESTAMP
        WHERE id=?
    """, (name, description, icon, system_prompt, knowledge, model, active, agent_id))
    conn.commit()
    conn.close()


def delete_custom_agent(agent_id: int) -> None:
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM custom_agents WHERE id=?", (agent_id,))
    c.execute("DELETE FROM agent_conversations WHERE agent_id=?", (agent_id,))
    conn.commit()
    conn.close()


def save_agent_message(agent_id, session_id, role, content, patient_id=None, patient_name="") -> None:
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO agent_conversations (agent_id, session_id, patient_id, patient_name, role, content)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (agent_id, session_id, patient_id, patient_name, role, content))
    conn.commit()
    conn.close()


def get_agent_conversation(agent_id, session_id, limit=30) -> list:
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT * FROM agent_conversations
        WHERE agent_id=? AND session_id=?
        ORDER BY created_at ASC LIMIT ?
    """, (agent_id, session_id, limit))
    rows = [dict(row) for row in c.fetchall()]
    conn.close()
    return rows


def get_stats() -> dict:
    """סטטיסטיקות כלליות"""
    conn = get_connection()
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM patients")
    total_patients = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM consultations WHERE consultation_type='diagnosis'")
    total_diagnoses = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM visualizations")
    total_visualizations = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM consultations WHERE DATE(created_at) = DATE('now')")
    today_consultations = c.fetchone()[0]

    conn.close()
    return {
        "total_patients": total_patients,
        "total_diagnoses": total_diagnoses,
        "total_visualizations": total_visualizations,
        "today_consultations": today_consultations,
    }
