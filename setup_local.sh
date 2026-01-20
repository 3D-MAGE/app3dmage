#!/bin/bash

echo "=========================================="
echo "CONFIGURAZIONE AMBIENTE LOCALE 3DMAGE"
echo "=========================================="

# Assicura di operare nella cartella dello script
cd "$(dirname "$0")" || exit

echo "1. Creazione nuovo Virtual Environment..."
python3 -m venv venv_local

echo "2. Attivazione..."
source venv_local/bin/activate

echo "3. Installazione dipendenze..."
pip install --upgrade pip
echo "Installazione python-dotenv e django..."
pip install python-dotenv django dj-database_url whitenoise

if [ -f "requirements.txt" ]; then
    echo "Installazione da requirements.txt..."
    pip install -r requirements.txt
fi

echo "4. Avvio Server..."
python manage.py runserver
