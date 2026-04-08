"""
=============================================================
  רויאל-מד | Agent 2 — הדמיית לפני/אחרי
=============================================================
  מקבל תמונת פנים של מטופל + טיפול שנבחר
  ומייצר הדמיה ריאליסטית של תוצאת הטיפול.

  שלב 1: GPT-4o/Gemini מנתח את התמונה ומייצר prompt מדויק
  שלב 2: DALL-E 3 מייצר את תמונת ה"אחרי"
=============================================================
"""

import base64
import json
import os
import urllib.request
from pathlib import Path

from google import genai as google_genai
from openai import OpenAI

from agents.prompts import (
    VISUALIZATION_SYSTEM_PROMPT,
    VISUALIZATION_PROMPT_TEMPLATE,
    TREATMENT_VISUAL_CHANGES,
    DALLE_IMAGE_PROMPT,
    DALLE_IMAGE_SIZE,
    DALLE_IMAGE_QUALITY,
    DALLE_IMAGE_STYLE,
    OPENAI_MODEL_VISION,
    GEMINI_MODEL_VISION,
)


def load_treatment_by_id(treatment_id: str) -> dict:
    """מחזיר פרטי טיפול לפי ID"""
    treatments_path = Path(__file__).parent.parent / "data" / "treatments.json"
    with open(treatments_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    for category in data["categories"]:
        for treatment in category["treatments"]:
            if treatment["id"] == treatment_id:
                return treatment
    return {}


def encode_image_base64(image_path: str) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def get_image_mime_type(image_path: str) -> str:
    ext = Path(image_path).suffix.lower()
    return {".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".png": "image/png", ".gif": "image/gif", ".webp": "image/webp"}.get(ext, "image/jpeg")


# ─────────────────────────────────────────────
#  שלב 1: ניתוח תמונה + יצירת prompt
# ─────────────────────────────────────────────

def generate_visualization_prompt_openai(
    image_path: str, treatment: dict, api_key: str = ""
) -> dict:
    """
    GPT-4o מנתח את תמונת המטופל ומייצר prompt מדויק ל-DALL-E
    """
    try:
        client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))

        specific_changes = TREATMENT_VISUAL_CHANGES.get(
            treatment.get("id", ""), treatment.get("description", "")
        )

        analysis_prompt = f"""
        נתח את תמונת הפנים הזו ויצר prompt מדויק ל-DALL-E 3 שיראה כיצד הפנים ייראו אחרי:
        טיפול: {treatment.get('name', '')}
        שינויים צפויים: {specific_changes}

        ה-prompt צריך:
        1. לשמור על כל המאפיינים הייחודיים של האדם בתמונה (גיל, מבנה, גוון עור, צבע שיער ועיניים)
        2. לתאר את השינויים הספציפיים מהטיפול בצורה ריאליסטית ומתונה
        3. לציין סגנון צילום רפואי מקצועי
        4. להיות באנגלית (לצורך DALL-E)

        החזר רק את ה-prompt עצמו, ללא הסברים נוספים.
        """

        image_b64 = encode_image_base64(image_path)
        mime_type = get_image_mime_type(image_path)

        response = client.chat.completions.create(
            model=OPENAI_MODEL_VISION,
            messages=[
                {"role": "system", "content": VISUALIZATION_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": analysis_prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime_type};base64,{image_b64}"},
                        },
                    ],
                },
            ],
            max_tokens=500,
            temperature=0.4,
        )

        return {
            "success": True,
            "prompt": response.choices[0].message.content,
        }

    except Exception as e:
        # fallback prompt אם הניתוח נכשל
        specific_changes = TREATMENT_VISUAL_CHANGES.get(treatment.get("id", ""), "")
        fallback_prompt = DALLE_IMAGE_PROMPT.format(
            treatment_name=treatment.get("name", "aesthetic treatment"),
            specific_changes=specific_changes,
        )
        return {"success": True, "prompt": fallback_prompt, "fallback": True}


# ─────────────────────────────────────────────
#  שלב 2: יצירת תמונה עם DALL-E 3
# ─────────────────────────────name────────────
#  הערה: DALL-E לא יכול לקבל תמונת קלט ולערוך אותה.
#  המערכת מייצרת הדמיה על בסיס תיאור מפורט של המטופל.
#  לעריכת תמונות קיימות ישירות — מומלץ לשדרג ל-GPT-Image-1 API
# ─────────────────────────────────────────────

def generate_after_image_dalle(dalle_prompt: str, api_key: str = "") -> dict:
    """
    מייצר תמונת 'אחרי' עם DALL-E 3
    """
    try:
        client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))

        response = client.images.generate(
            model="dall-e-3",
            prompt=dalle_prompt,
            size=DALLE_IMAGE_SIZE,
            quality=DALLE_IMAGE_QUALITY,
            style=DALLE_IMAGE_STYLE,
            n=1,
        )

        image_url = response.data[0].url
        revised_prompt = response.data[0].revised_prompt

        return {
            "success": True,
            "image_url": image_url,
            "revised_prompt": revised_prompt,
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


def download_image(url: str, save_path: str) -> bool:
    """מוריד תמונה מ-URL ושומר מקומית"""
    try:
        urllib.request.urlretrieve(url, save_path)
        return True
    except Exception:
        return False


# ─────────────────────────────────────────────
#  פונקציה ראשית
# ─────────────────────────────────────────────

def run_visualization_agent(
    image_path: str,
    treatment_id: str,
    save_dir: str,
    openai_key: str = "",
    gemini_key: str = "",
) -> dict:
    """
    מריץ את ה-Visualization Agent המלא:
    1. טוען פרטי טיפול
    2. GPT-4o מנתח תמונה ומייצר prompt
    3. DALL-E 3 מייצר תמונת אחרי
    4. שומר תמונה מקומית

    Args:
        image_path: נתיב לתמונת המטופל
        treatment_id: ID הטיפול שנבחר
        save_dir: תיקייה לשמירת תמונת האחרי
        openai_key: OpenAI API key
        gemini_key: Gemini API key (לשימוש עתידי)

    Returns:
        dict: success, before_path, after_path, treatment, prompt_used, error
    """
    treatment = load_treatment_by_id(treatment_id)
    if not treatment:
        return {"success": False, "error": f"טיפול לא נמצא: {treatment_id}"}

    # שלב 1: יצירת prompt מותאם אישית
    prompt_result = generate_visualization_prompt_openai(image_path, treatment, openai_key)
    dalle_prompt = prompt_result.get("prompt", "")

    # שלב 2: יצירת תמונת אחרי
    image_result = generate_after_image_dalle(dalle_prompt, openai_key)

    if not image_result["success"]:
        return {
            "success": False,
            "error": image_result.get("error", "שגיאה ביצירת הדמיה"),
        }

    # שמירת תמונת האחרי
    import uuid
    after_filename = f"after_{treatment_id}_{uuid.uuid4().hex[:8]}.png"
    after_path = os.path.join(save_dir, after_filename)
    downloaded = download_image(image_result["image_url"], after_path)

    return {
        "success": True,
        "before_path": image_path,
        "after_path": after_path if downloaded else None,
        "after_url": image_result["image_url"],
        "treatment": treatment,
        "prompt_used": dalle_prompt,
        "is_fallback": prompt_result.get("fallback", False),
    }
