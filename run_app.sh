#!/bin/bash

# Assicura di operare nella cartella dello script
cd "$(dirname "$0")" || exit

if [ ! -d "venv_local" ]; then
    echo "Errore: Esegui prima setup_local.sh per configurare l'ambiente!"
    exit 1
fi

echo "Attivazione ambiente locale (venv_local)..."
source venv_local/bin/activate

echo "Avvio server Django..."
python manage.py runserver
