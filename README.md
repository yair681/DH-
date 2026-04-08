# רויאל-מד | ROYAL-MED AI System
## מערכת AI פנימית למרכז אסתטיקה רפואית

---

## תוכן עניינים
1. [דרישות מערכת](#דרישות-מערכת)
2. [התקנה מהירה](#התקנה-מהירה)
3. [הגדרת API Keys](#הגדרת-api-keys)
4. [הפעלת המערכת](#הפעלת-המערכת)
5. [מבנה המערכת](#מבנה-המערכת)
6. [ניהול טיפולים](#ניהול-טיפולים)
7. [שינוי סיסמה](#שינוי-סיסמה)
8. [פתרון בעיות](#פתרון-בעיות)

---

## דרישות מערכת
- Windows 10/11
- Python 3.10 ומעלה — הורד מ: https://www.python.org/downloads/
  - **חשוב**: סמן "Add Python to PATH" בזמן ההתקנה
- חיבור אינטרנט (לקריאות API בלבד)
- מפתח OpenAI API (חובה)
- מפתח Google Gemini API (מומלץ, לא חובה)

---

## התקנה מהירה

### שיטה 1 — כפול-קליק (מומלץ)
1. לך לתיקייה `royal-med-ai` בשולחן העבודה
2. לחץ פעמיים על `start.bat`
3. בפעם הראשונה — המערכת תתקין הכל אוטומטית
4. הכנס API Keys כשיפתח הקובץ
5. פתח דפדפן וכנס ל: **http://localhost:5000**

### שיטה 2 — ידנית
```
# פתח PowerShell / CMD בתוך תיקיית royal-med-ai
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
# ערוך את .env עם מפתחות ה-API
python app.py
```

---

## הגדרת API Keys

### OpenAI API Key (לאבחון + הדמיות)
1. כנס ל: https://platform.openai.com/api-keys
2. צור מפתח חדש
3. הכנס בקובץ `.env`:
   ```
   OPENAI_API_KEY=sk-proj-...
   ```
4. ודא שיש לך קרדיט — GPT-4o Vision ו-DALL-E 3 הם בתשלום
   - אבחון תמונה: ~$0.01-0.03 לקריאה
   - הדמיית לפני/אחרי: ~$0.04-0.08 לתמונה

### Google Gemini API Key (מודל חלופי — חינמי)
1. כנס ל: https://aistudio.google.com/app/apikey
2. צור מפתח
3. הכנס בקובץ `.env`:
   ```
   GEMINI_API_KEY=AIza...
   ```

### הגדרה דרך הממשק
אפשר גם להכניס מפתחות ישירות דרך **הגדרות ← API** בממשק הגרפי.

---

## הפעלת המערכת
- **הפעלה**: לחץ פעמיים על `start.bat`
- **כתובת**: http://localhost:5000
- **סיסמת ברירת מחדל**: `royalmed2024`
- **לעצירה**: סגור את חלון ה-CMD או Ctrl+C

---

## מבנה המערכת

```
royal-med-ai/
├── app.py                    ← שרת Flask ראשי
├── start.bat                 ← הפעלה ב-Windows
├── requirements.txt          ← חבילות Python
├── .env                      ← API Keys וסיסמה (צור אותו!)
├── .env.example              ← תבנית
│
├── agents/
│   ├── diagnosis_agent.py    ← Agent 1: פענוח ואבחון
│   ├── visualization_agent.py← Agent 2: הדמיית לפני/אחרי
│   └── prompts.py            ← כל הפרומטים (ניתן לערוך!)
│
├── data/
│   ├── treatments.json       ← רשימת טיפולים (ניתן לערוך!)
│   └── royal_med.db          ← מסד נתונים (נוצר אוטומטית)
│
├── database/
│   └── models.py             ← ניהול מסד נתונים
│
├── templates/                ← דפי HTML
│   ├── login.html
│   ├── dashboard.html
│   ├── diagnosis.html
│   ├── visualization.html
│   ├── chat.html
│   ├── patients.html
│   └── settings.html
│
└── static/
    ├── css/style.css         ← עיצוב
    ├── js/app.js             ← JavaScript
    └── uploads/              ← תמונות שהועלו (נוצר אוטומטית)
```

---

## ניהול טיפולים

### דרך הממשק (מומלץ)
1. כנס להגדרות → ניהול רשימת טיפולים
2. ערוך שם/תיאור, הפעל/כבה טיפולים
3. הוסף טיפולים חדשים
4. לחץ "שמור שינויים"

### ידנית בקובץ JSON
פתח `data/treatments.json` בכל עורך טקסט (Notepad, VS Code).

מבנה טיפול:
```json
{
  "id": "treatment_id",
  "name": "שם הטיפול",
  "description": "תיאור",
  "indications": ["התווייה 1", "התווייה 2"],
  "duration": "30-45 דקות",
  "recovery": "1-3 ימים",
  "active": true
}
```

---

## שינוי הפרומטים
כל הפרומטים נמצאים בקובץ `agents/prompts.py`.
פתח את הקובץ ועדכן ישירות — כל שינוי ייכנס לתוקף בהפעלה הבאה.

**פרומטים עיקריים:**
- `DIAGNOSIS_SYSTEM_PROMPT` — אופי ה-Agent לאבחון
- `CHAT_SYSTEM_PROMPT` — אופי עוזר הצ'אט
- `TREATMENT_VISUAL_CHANGES` — תיאורי הדמיה לכל טיפול

---

## שינוי סיסמה
**דרך הממשק**: הגדרות → שינוי סיסמת כניסה

**ידנית**: ערוך `SYSTEM_PASSWORD=...` בקובץ `.env`

---

## גיבוי נתונים
כל הנתונים נשמרים ב: `data/royal_med.db`
לגיבוי — פשוט העתק קובץ זה למקום בטוח.

---

## פתרון בעיות

| בעיה | פתרון |
|------|--------|
| "Python לא מותקן" | הורד Python מ-python.org, סמן "Add to PATH" |
| "שגיאת API" | בדוק שה-API Key נכון ויש קרדיט |
| הדמיה לא נוצרת | ודא שה-OPENAI_API_KEY מוגדר ויש קרדיט |
| דף לא נטען | ודא שה-start.bat רץ ופתח http://localhost:5000 |
| שכחתי סיסמה | ערוך `SYSTEM_PASSWORD` ישירות ב-.env |

---

## אבטחה
- המערכת פועלת רק על המחשב המקומי (localhost)
- אין גישה חיצונית ללא הגדרה מפורשת
- כל הנתונים שמורים מקומית בלבד
- API Keys שמורים בקובץ .env על המחשב בלבד

---

*נבנה עבור רויאל-מד | גרסה 1.0*
