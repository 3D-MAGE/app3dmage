@echo off
if not exist venv_local (
    echo Errore: Esegui prima setup_local.bat per configurare l'ambiente!
    pause
    exit /b
)

echo Attivazione ambiente locale (venv_local)...
call venv_local\Scripts\activate

echo Avvio server Django...
python manage.py runserver
