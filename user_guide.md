# Guida Utente - 3DMAGE Management

Benvenuto nella guida utente di **3DMAGE Management**. Questa applicazione è stata progettata per gestire l'intero ciclo di vita della produzione 3D, dalla prototipazione (Master) alla produzione (Ordini di Lavoro) fino alla vendita (Magazzino).

---

## 1. Concetti Fondamentali: Master vs Ordini

La distinzione principale nell'app è tra **Progetti Master** e **Ordini di Lavoro**.

*   **Progetto Master (Il "Ricettario")**: Rappresenta il progetto teorico. È il blueprint o la "ricetta" di come si produce un oggetto. Contiene le istruzioni, le parti che lo compongono, quali file stampare e quali prodotti finali genera.
*   **Ordine di Lavoro (La "Produzione")**: È l'istanza reale di produzione. Quando decidi di produrre 10 pezzi di un Master, crei un Ordine di Lavoro. Questo ha uno stato (In stampa, Completato, ecc.) e traccia i costi e i tempi reali.

---

## 2. Definizioni del Progetto Master

All'interno di un **Progetto Master**, troviamo diverse entità:

### **Parti (Project Parts)**
Le **Parti** sono raggruppamenti logici dei componenti fisici del progetto.
*   *Esempio*: Un progetto "Robot" può essere diviso nelle parti "Gambe", "Busto", "Braccia", "Testa".
*   *Scopo*: Servono a organizzare i file di stampa in modo ordinato.
*   *Denominazione automatica*: Quando un progetto Master viene creato con 1 sola parte iniziale (opzione predefinita), la parte riceve automaticamente il **nome dell'oggetto** anziché il generico "Parte 1", mantenendo la struttura snella e intuitiva.

### **Output (Project Outputs)**
Gli **Output** sono i prodotti finali che verranno effettivamente versati in magazzino al termine della produzione.
*   *Esempio*: Un progetto "Set Scacchi" potrebbe avere come output "Pezzi Bianchi x1" e "Pezzi Neri x1".
*   *Nota*: Un progetto può produrre più oggetti diversi contemporaneamente o in un unico set.

### **Template File di Stampa (Master Print Files)**
Sono i "pre-set" dei file G-Code da stampare. Associate a una **Parte**, definiscono:
*   Nome del file.
*   Stampante e Piatto consigliati.
*   Tempo di stampa stimato.
*   Filamenti necessari e peso stimato.
*   **Oggetti per Stampa**: Quanti pezzi fisici vengono prodotti ogni volta che quel file finisce di stampare.

---

## 3. Gestione della Produzione: Ordini di Lavoro

Quando crei un **Ordine di Lavoro** da un Master, l'app genera i compiti di stampa reali.

### **Stati dell'Ordine**
*   **Preventivo (Quote)**: Fase iniziale, utile per calcolare i costi.
*   **Da Stampare (Todo)**: L'ordine è pronto per la produzione.
*   **In Stampa (Printing)**: Almeno uno dei file associati è attualmente in stampa.
*   **Stampato (Printed)**: Tutti i file sono stati stampati, ma gli oggetti non sono ancora stati "versati" in magazzino.
*   **Completato (Done)**: Gli oggetti sono stati versati in magazzino e l'ordine è chiuso.

### **File di Stampa (Print Files / G-Code)**
Sono le singole attività di stampa all'interno di un ordine. Ognuno segue un ciclo di stati ben definito:
*   **Da Preparare (`Prepare`)**: Stato preliminare facoltativo (prima di "Da Stampare"). Si usa per i file non ancora pronti per la produzione (es. slicing da ottimizzare, piatto o materiale da verificare). **I file "Da Preparare" NON vengono mostrati nella Coda di Stampa**, mantenendo pulita la vista delle macchine.
*   **Da Stampare (`Todo`)**: Stato predefinito alla creazione. Il file è pronto e viene visualizzato nella colonna "In Coda" della rispettiva stampante nella Coda di Stampa.
*   **In Stampa (`Printing`)**: Il file è attualmente in esecuzione sul piatto della stampante.
*   **Stampato (`Done`)**: Stampa completata con successo. I pezzi prodotti vengono conteggiati nell'avanzamento.
*   **Fallito (`Failed`)**: Stampa fallita. È possibile inserire i grammi di filamento sprecati e rimettere in coda una ristampa con 1 clic.

---

## 4. Magazzino e Vendite

### **Oggetti a Magazzino (Stock Items)**
Una volta completato un ordine, i pezzi prodotti diventano **Oggetti a Magazzino**.
*   **Stato**: Possono essere `A Magazzino`, `In Conto Vendita` (presso un negozio esterno) o `Venduto`.
*   **Costi**: L'app calcola automaticamente il costo dei materiali in base alle bobine utilizzate. È possibile aggiungere manualmente il **Costo Manodopera**.

### **Vendite**
Quando un oggetto viene segnato come `Venduto`, è possibile specificare:
*   Prezzo di vendita effettivo.
*   Data di vendita.
*   Metodo di pagamento (usato per calcolare le commissioni nette e il saldo effettivo, es: Satispay Business 0% sotto i 10€ e 0,95% da 10€ in su, SumUp 1.95%, Contanti 0%). I pagamenti antecedenti al 04/09/2026 mantengono la commissione storica dell'1%.

---

## 5. Materie Prime & Componenti Esterni

Oltre ai filamenti, molti progetti richiedono componenti fisici non stampabili (calamite, viti, inserti filettati, cuscinetti):
*   **Magazzino Materie Prime** (nel menu *Magazzino > Materie Prime*): Permette di censire le materie prime, registrare gli acquisti/carichi con relativo costo e monitorare le giacenze attuali.
*   **Associazione ai Progetti Master**: È possibile impostare il fabbisogno unitario di materie prime per ogni Master (es. "4x Calamita 10x2mm per ogni scatola").
*   **Fabbisogno negli Ordini di Lavoro**: Quando viene creato un Ordine di Lavoro, il fabbisogno totale viene calcolato e precaricato automaticamente. Al completamento dell'ordine, le quantità utilizzate vengono scalate dalle giacenze di magazzino.

---

## 6. Note Rapide & Centro Notifiche

### **Note Rapide (Offcanvas)**
Accessibile in qualsiasi momento dall'icona del taccuino nella barra superiore (con badge contatore promemoria attivi):
*   Aggiunta istantanea di appunti o promemoria con casella di spunta per completamento rapido.
*   Suddivisione per categorie: *Acquisti*, *Manutenzione Stampanti*, *Produzione*, *Generale*.
*   Possibilità di impostare data di scadenza e collegamenti specifici (a una stampante, a una bobina o a un ordine).
*   Pannello esteso completo raggiungibile cliccando sull'icona di espansione interna.

### **Centro Notifiche**
Accessibile dall'icona a campanella nella barra superiore:
*   Badge dinamico con conteggio avvisi non letti.
*   **Avvisi automatici generati dal sistema**:
    *   Bobine esaurite (0g) o prossime all'esaurimento (&le; 150g rimanenti);
    *   Ordini di lavoro in ritardo sulla data di consegna prevista (con link diretto al dettaglio dell'ordine);
    *   Promemoria scaduti o in scadenza nella giornata odierna.
*   Pannello storico completo per archiviare o svuotare gli avvisi.

---

## 7. Documentazione Economica & Calcoli
Nel menu **Impostazioni / Statistiche** (icona ingranaggio) è disponibile la pagina **Documentazione**, che illustra dettagliatamente:
*   La struttura dei costi di produzione (materiale, elettricità, ammortamento usura, minuteria e manodopera).
*   L'algoritmo non lineare di calcolo del prezzo consigliato e dei preventivi.
*   La compensazione fiscale (regime forfettario 5%) e i margini di sicurezza.
*   Le commissioni applicate ai diversi metodi di pagamento.

---

## 8. Materiali e Hardware

### **Filamenti e Bobine (Filaments & Spools)**
*   **Filamento**: Definisce il tipo di materiale (Marca, Colore, Materiale es: PLA Nero Prusa).
*   **Bobina**: Rappresenta il singolo rotolo fisico di plastica. L'app traccia il peso iniziale, i grammi consumati da ogni stampa e calcola il peso residuo.

### **Stampanti e Piatti (Printers & Plates)**
*   **Stampante**: Definisce il nome, il modello e il consumo energetico (Watt) per il calcolo dei costi elettrici.
*   **Piatto**: Le diverse superfici di stampa (PEI Smooth, Textured, ecc.) che possono essere associate alle stampanti.

---

## 9. Workflow Tipico

1.  **Crea un Master**: Definisci il nome e aggiungi le **Parti** (se c'è 1 sola parte, prende automaticamente il nome del progetto).
2.  **Configura i Template & Materie Prime**: Aggiungi i file G-Code da stampare e le eventuali minuterie/accessori necessari.
3.  **Definisci gli Output**: Specifica quali oggetti (e quanti) compongono un "set" completo di questo progetto.
4.  **Crea un Ordine**: Dalla libreria Master, clicca su "Crea Ordine" e scegli quanti set produrre.
5.  **Produci**: Gestisci gli stati dei file (`Da Preparare` -> `Da Stampare` -> `In Stampa`). I file "Da Preparare" non intasano la Coda di Stampa.
6.  **Completa e Versa**: Clicca su "Completa" per trasformare la produzione in oggetti reali nel magazzino e scaricare le materie prime impiegate.
7.  **Vendi**: Gestisci le vendite dal modulo Magazzino o Vendite per tracciare ricavi e profitti netti.
