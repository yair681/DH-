"""
=============================================================
  רויאל-מד | Agent 1 — פענוח ואבחון
=============================================================
  מנתח תמונות בדיקה/אבחון ומחזיר פענוח קליני בעברית
  עם המלצות טיפול מרשימת הטיפולים של המרפאה.

  תומך ב:
  - OpenAI GPT-4o Vision
  - Google Gemini 1.5 Pro Vision
=============================================================
"""

import base64
import json
import os
from pathlib import Path

from google import genai
from openai import OpenAI

from agents.prompts import (
    DIAGNOSIS_SYSTEM_PROMPT,
    DIAGNOSIS_USER_PROMPT_TEMPLATE,
    DIAGNOSIS_TEXT_ONLY_PROMPT,
    OPENAI_MODEL_VISION,
    GEMINI_MODEL_VISION,
)


def load_treatments_list() -> str:
    """טוען את רשימת הטיפולים מ-JSON ומחזיר כטקסט מפורמט"""
    treatments_path = Path(__file__).parent.parent / "data" / "treatments.json"
    with open(treatments_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    lines = []
    for category in data["categories"]:
        lines.append(f"\n## {category['name']}")
        for t in category["treatments"]:
            if t.get("active", True):
                lines.append(f"  • {t['name']}: {t['description']}")
                lines.append(f"    התוויות: {', '.join(t['indications'])}")
    return "\n".join(lines)


def encode_image_base64(image_path: str) -> str:
    """מקודד תמונה ל-base64"""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def get_image_mime_type(image_path: str) -> str:
    """מחזיר MIME type לפי סיומת קובץ"""
    ext = Path(image_path).suffix.lower()
    mime_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }
    return mime_map.get(ext, "image/jpeg")


# ─────────────────────────────────────────────
#  OpenAI GPT-4o Vision
# ─────────────────────────────────────────────

def analyze_with_openai(image_path: str, additional_info: str = "", api_key: str = "") -> dict:
    """
    מנתח תמונת בדיקה עם GPT-4o Vision

    Args:
        image_path: נתיב לתמונה
        additional_info: מידע נוסף מהצוות
        api_key: OpenAI API key

    Returns:
        dict עם: success, result, error
    """
    try:
        client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))
        treatments = load_treatments_list()

        user_prompt = DIAGNOSIS_USER_PROMPT_TEMPLATE.format(
            treatments_list=treatments,
            additional_info=additional_info or "לא סופק מידע נוסף",
        )

        image_b64 = encode_image_base64(image_path)
        mime_type = get_image_mime_type(image_path)

        response = client.chat.completions.create(
            model=OPENAI_MODEL_VISION,
            messages=[
                {"role": "system", "content": DIAGNOSIS_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{image_b64}",
                                "detail": "high",
                            },
                        },
                    ],
                },
            ],
            max_tokens=2000,
            temperature=0.3,
        )

        return {
            "success": True,
            "result": response.choices[0].message.content,
            "model": "GPT-4o",
            "tokens_used": response.usage.total_tokens,
        }

    except Exception as e:
        return {"success": False, "error": str(e), "result": None}


# ─────────────────────────────────────────────
#  Google Gemini Vision
# ─────────────────────────────────────────────

def analyze_with_gemini(image_path: str, additional_info: str = "", api_key: str = "") -> dict:
    """
    מנתח תמונת בדיקה עם Gemini 1.5 Pro Vision

    Args:
        image_path: נתיב לתמונה
        additional_info: מידע נוסף מהצוות
        api_key: Gemini API key

    Returns:
        dict עם: success, result, error
    """
    try:
        import PIL.Image, base64, io
        client = genai.Client(api_key=api_key or os.getenv("GEMINI_API_KEY"))
        treatments = load_treatments_list()

        full_prompt = (
            DIAGNOSIS_SYSTEM_PROMPT
            + "\n\n"
            + DIAGNOSIS_USER_PROMPT_TEMPLATE.format(
                treatments_list=treatments,
                additional_info=additional_info or "לא סופק מידע נוסף",
            )
        )

        image = PIL.Image.open(image_path)
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        image_bytes = buf.getvalue()

        response = client.models.generate_content(
            model=GEMINI_MODEL_VISION,
            contents=[
                full_prompt,
                {"mime_type": "image/png", "data": base64.b64encode(image_bytes).decode()}
            ]
        )

        return {
            "success": True,
            "result": response.text,
            "model": "Gemini 1.5 Pro",
        }

    except Exception as e:
        return {"success": False, "error": str(e), "result": None}


# ─────────────────────────────────────────────
#  פונקציה ראשית — בוחרת מודל אוטומטית
# ─────────────────────────────────────────────

def run_diagnosis_agent(
    image_path: str,
    additional_info: str = "",
    preferred_model: str = "openai",
    openai_key: str = "",
    gemini_key: str = "",
) -> dict:
    """
    מריץ את ה-Diagnosis Agent עם המודל המועדף.
    אם המודל הראשי נכשל, עובר אוטומטית למודל השני (fallback).

    Args:
        image_path: נתיב לתמונה
        additional_info: הערות מהצוות
        preferred_model: "openai" או "gemini"
        openai_key: OpenAI API key (אופציונלי אם מוגדר בסביבה)
        gemini_key: Gemini API key (אופציונלי אם מוגדר בסביבה)

    Returns:
        dict: success, result, model_used, error
    """
    if preferred_model == "openai":
        result = analyze_with_openai(image_path, additional_info, openai_key)
        if not result["success"]:
            # Fallback ל-Gemini
            result = analyze_with_gemini(image_path, additional_info, gemini_key)
    else:
        result = analyze_with_gemini(image_path, additional_info, gemini_key)
        if not result["success"]:
            # Fallback ל-OpenAI
            result = analyze_with_openai(image_path, additional_info, openai_key)

    return result
