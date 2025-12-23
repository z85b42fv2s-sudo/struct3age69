@echo off
echo Avvio dell'applicazione Analisi Strutturale...
cd /d "%~dp0"
python -m streamlit run app.py
pause
