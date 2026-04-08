@echo off
chcp 65001 >nul
title Royal-Med AI System

echo.
echo  ==========================================
echo   רויאל-מד  ^|  ROYAL-MED AI SYSTEM
echo  ==========================================
echo.

REM בדיקה אם Python מותקן
python --version >nul 2>&1
if errorlevel 1 (
    echo  [שגיאה] Python לא מותקן. הורד מ: https://www.python.org
    pause
    exit /b
)

REM בדיקה אם .env קיים
if not exist ".env" (
    echo  [הגדרות] יוצר קובץ .env מהתבנית...
    copy .env.example .env >nul
    echo  [חשוב!] פתח את קובץ .env והכנס את מפתחות ה-API שלך!
    echo.
    notepad .env
)

REM התקנת חבילות אם צריך
if not exist "venv\" (
    echo  [התקנה] יוצר סביבה וירטואלית...
    python -m venv venv
    echo  [התקנה] מתקין חבילות...
    venv\Scripts\pip install -r requirements.txt --quiet
    echo  [התקנה] הושלמה!
)

echo  [מפעיל] מתחיל את השרת...
echo  [כתובת] http://localhost:5000
echo  [עצירה] לחץ Ctrl+C לעצירה
echo.

REM הפעלת השרת
venv\Scripts\python app.py

pause
