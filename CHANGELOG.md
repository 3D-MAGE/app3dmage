# Changelog

Tutte le modifiche notevoli a questo progetto saranno documentate in questo file.

## [2.2.0] - 2026-01-09

### Workflow di Produzione e Magazzino
- **Suggerimento Quantità Intelligente**: Il modale di chiusura ordine ora propone automaticamente la quantità di pezzi **effettivamente stampati** (DONE) ma non ancora versati a magazzino, facilitando i completamenti parziali.
- **Logica Multi-Set Corretta**: Sistemato il calcolo del moltiplicatore file per ordini con più set, garantendo la generazione del corretto numero di file di stampa.
- **Scaling Vincolato**: Nella creazione di un ordine, la quantità per ogni singolo set è ora bloccata (`readonly`) al valore predefinito del Master. L'aumento della produzione avviene aggiungendo ulteriori set completi.
- **Stabilità Backend**: Risolto un bug (`total_pieces_per_master` non definito) che poteva causare crash durante il versamento a magazzino degli oggetti.

### Interfaccia Utente e UX
- **Unificazione Terminologia**: Sostituito ovunque il termine "Lotto" con "**Set**" per coerenza e chiarezza nel flusso di lavoro.
- **Restyling Modale Creazione**: Consolidata la visualizzazione della quantità del set in una pillola descrittiva, rimuovendo campi di input superflui e riducendo il disordine visivo.
- **Visibilità Avvisi**: Nel modale di chiusura ordine, l'avviso di "Completamento Parziale" è stato spostato in alto e reso più evidente (colore rosso) per una maggiore sicurezza operativa.
- **Tabella Master**: Ottimizzato il layout HTML dei template (Master detail) per rimuovere spazi vuoti e migliorare l'allineamento.


## [2.1.0] - 2026-01-02

### Interfaccia Utente e UX
- **Azioni Basate sullo Stato**: L'intestazione dell'ordine ora mostra pulsanti diversi in base allo stato:
  - **In Corso**: Mantiene "Completa", "Modifica" (con funzioni master all'interno) ed "Elimina".
  - **Completati**: Mostra direttamente "Riapri Ordine", "Ristampa" e "Promuovi a Master" per una gestione più rapida.
- **Aggiorna Master**: Sostituito il dialogo di conferma nativo con una modale Bootstrap personalizzata.
- **Libreria Progetti**: Aggiunte le colonne "Quantità Base" e "File di Stampa" associati.
- **Dashboard**: Implementato l'ordinamento per le colonne "Priorità", "Stato" e "Progresso".
- **Bug Fix**: Risolto un problema nel caricamento della modale "Crea Ordine di Lavoro".
- **Promozione a Master**: Funzionalità "Promuovi a Master" per convertire ordini in template Master con un click.

### Stabilità e Performance
- **Dashboard Polling**: Risolto un errore `decimal.InvalidOperation` durante il refresh automatico (HTMX) causato da dati non validi nel timestamp globale.

## [2.0.0] - 2025-12-27

### Refactoring Architetturale (v2.0)
- **Libreria Progetti (Master Data)**: Introdotta la distinzione tra "Progetti Master" (template/BOM) e "Ordini di Lavoro" (istanze di produzione).
- **Modelli**:
  - Rinominato il modello `Project` esistente in `WorkOrder`.
  - Creato un nuovo modello `Project` per i dati master.
  - Aggiunto `MasterPrintFile` per memorizzare i settaggi G-code template.
- **Workflow di Produzione**:
  - Possibilità di creare un Ordine di Lavoro partendo da un Progetto master con un click.
  - Supporto per il versamento parziale a magazzino: un ordine rimane aperto finché la quantità prodotta non raggiunge quella richiesta.
- **Interfaccia Utente**:
  - Nuova sezione "Libreria Progetti" per la gestione dei template.
  - Aggiornata la Dashboard e la Kanban board per riflettere la terminologia "Ordini".
  - Ottimizzazione dei contatori "Totale In Corso" e "Da Stampare".

## [1.5.0] - 2025-12-26

### Magazzino (Inventory)
- **Stabilità UI**: Rifattorizzata l'architettura JavaScript (`inventory.js`) per separare l'inizializzazione statica dei modali da quella dinamica della tabella. Questo risolve il problema dei pulsanti "Vendi" ed "Elimina" che smettevano di funzionare dopo i refresh automatici di HTMX.
- **Refresh Immediato**: Implementato un trigger manuale HTMX che ricarica immediatamente la tabella alla chiusura dei modali (Salva o Annulla). Questo garantisce che lo stato di blocco (concurrency lock) venga rimosso visivamente all'istante senza attendere l'intervallo di 10 secondi.
- **Gestione Concorrenza**: Ottimizzata la gestione dei lock durante le transizioni tra modali (es. passaggio da Modifica a Vendita) per prevenire rilasci prematuri del blocco oggetto.

## [1.4.0] - 2025-12-21

### Magazzino (Inventory)
- **Bug Fix**: Implementato l'invio tramite AJAX del modulo di modifica oggetti. Questo evita il reindirizzamento alla pagina della risposta JSON e ricarica correttamente la dashboard.
- **Pulizia Stati**: Rimosso lo stato "Venduto" dal menu a tendina della modifica manuale. La vendita deve essere gestita esclusivamente tramite la procedura guidata dedicata.

### Contabilità (Accounting)
- **Restyling Layout**: Spostato il comportamento "sticky" dall'intestazione del riepilogo finanziario alla sezione dei filtri.
- **Stabilità UI**: Rimossa la logica di restringimento dell'header allo scroll per eliminare effetti di jitter e migliorare la leggibilità durante la navigazione.

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
