@echo off
echo ==========================================
echo CONFIGURAZIONE AMBIENTE LOCALE 3DMAGE
echo ==========================================

echo 1. Creazione nuovo Virtual Environment...
python -m venv venv_local

echo 2. Attivazione...
call venv_local\Scripts\activate

echo 3. Installazione dipendenze...
echo Installazione python-dotenv e django...
pip install python-dotenv django dj-database_url whitenoise
if exist requirements.txt (
    echo Installazione da requirements.txt...
    pip install -r requirements.txt
)

echo 4. Avvio Server...
python manage.py runserver

pause
