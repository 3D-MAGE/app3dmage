# Changelog

Tutte le modifiche notevoli a questo progetto saranno documentate in questo file.

## [Non Rilasciato] - 2025-12-17

### Correzioni Bug e UI (Magazzino)
- **Inventario**: Risolto un `TemplateSyntaxError` nel template `inventory.html`.
- **Interfaccia Vendita**: Corretto il layout grafico della modale di vendita per una migliore usabilità.
- **Logica Stati**: Rimossa l'opzione "Venduto" dal menu a tendina modificabile manualmente (lo stato "Venduto" deve essere gestito automaticamente).
- **Visualizzazione**: Sistemata la visualizzazione corretta degli stati degli oggetti nella lista inventario.

## 2025-12-16

### Refactoring Architetturale
- **Viste Django**: Suddiviso il file monolitico `views.py` in un package `views/` organizzato per moduli.
- **Business Logic**: Introdotto `ProjectManager` nel modello `Project` per centralizzare e ottimizzare il calcolo dei costi.
- **Dashboard**: Aggiornato `dashboard.py` per utilizzare la nuova logica del `ProjectManager`.

## 2025-12-15

### Funzionalità
- **Progetti**: Aggiornamento della funzionalità "Riapri Progetto".
- **Stampa**: Aggiornamento e ottimizzazione della "Coda di Stampa".
