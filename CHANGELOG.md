# Changelog

Tutte le modifiche notevoli a questo progetto saranno documentate in questo file.

## [1.3.0] - 2025-12-19

### Sincronizzazione Stato Progetto
- **Logica Centralizzata**: Spostata la funzione di sincronizzazione stato nel modello `Project` come metodo `sync_status()`.
- **Integrazione Coda**: Il progetto ora aggiorna automaticamente il suo stato in base agli spostamenti dei file nella coda di stampa (es. spostando in "In stampa" il progetto riflette lo stato immediatamente).

### Miglioramento Selezione Filamenti
- **Filtraggio Disponibilità**: I menu di selezione filamenti ora mostrano solo i materiali con almeno una bobina attiva, prevenendo errori di selezione di materiali esauriti.
- **Ordinamento Raffinato**: Standardizzato l'ordinamento alfabetico per **Materiale** e poi per **Codice Colore** (ignorando la marca) per una ricerca più rapida nei dropdown.

## [1.2.0] - 2025-12-18

### Sincronizzazione Vendite e Contabilità
- **Logica Centralizzata**: Spostato il calcolo delle commissioni (Satispay 1%, SumUp 1.95%) direttamente nel modello `StockItem`.
- **Architettura Prezzi**: Standardizzato il database per memorizzare sempre il **Prezzo Lordo**. Tutte le annotazioni di ricavo netto e profitto avvengono ora a livello di query (tramite `StockItemQuerySet`).
- **Accounting Sync**: Risolto un bug critico in `edit_sale` che impediva l'aggiornamento dei saldi di cassa quando si modificava una vendita esistente.
- **Interfaccia Utente**: Introdotta l'anteprima in tempo reale del "Netto ricevuto" nelle modali di vendita (Magazzino) e modifica (Vendite).
- **Dashboard Vendite**: Aggiornate le tabelle per mostrare ricavi e profitti al netto delle commissioni, con supporto al sorting corretto.

### Gestione Progetti e Workflow
- **Nuovi Stati**: Introdotti gli stati "In stampa" (automatico quando un file è in stampa) e "Stampato" (automatico quando tutti i file sono completati).
- **Workflow Post-Produzione**: Un progetto completato sposta ora automaticamente gli oggetti in "Post-Produzione" nel Magazzino.
- **Correzione Progress Bar**: Risolto un bug che rendeva grigie le barre di progresso in alcuni browser dovuto a localizzazione delle virgole nei CSS (ora forzato formato con punto).
- **Integrità Dati**: Risolto un problema di duplicazione righe nella dashboard progetti dovuto a join multipli, ora gestiti tramite Subquery.

## [1.1.0] - 2025-12-17

### Correzioni Bug e UI (Magazzino)
- **Inventario**: Risolto un `TemplateSyntaxError` nel template `inventory.html`.
- **Interfaccia Vendita**: Corretto il layout grafico della modale di vendita per una migliore usabilità.
- **Logica Stati**: Rimossa l'opzione "Venduto" dal menu a tendina modificabile manualmente (lo stato "Venduto" deve essere gestito automaticamente).
- **Visualizzazione**: Sistemata la visualizzazione corretta degli stati degli oggetti nella lista inventario.

## [1.0.0] - 2025-12-16

### Refactoring Architetturale
- **Viste Django**: Suddiviso il file monolitico `views.py` in un package `views/` organizzato per moduli.
- **Business Logic**: Introdotto `ProjectManager` nel modello `Project` per centralizzare e ottimizzare il calcolo dei costi.
- **Dashboard**: Aggiornato `dashboard.py` per utilizzare la nuova logica del `ProjectManager`.

## 2025-12-15

### Funzionalità Iniziali
- **Progetti**: Aggiornamento della funzionalità "Riapri Progetto".
- **Stampa**: Aggiornamento e ottimizzazione della "Coda di Stampa".
