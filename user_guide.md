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

### **File di Stampa (Print Files)**
Sono le singole attività di stampa all'interno di un ordine. Ognuno ha il suo stato:
*   `Todo` -> `In Stampa` -> `Stampato` o `Fallito`.
*   Se un file fallisce, è possibile rimetterlo in coda per ritentare.

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
*   Metodo di pagamento (usato per calcolare le commissioni, es: Satispay 1% o SumUp 1.95%).

---

## 5. Materiali e Hardware

### **Filamenti e Bobine (Filaments & Spools)**
*   **Filamento**: Definisce il tipo di materiale (Marca, Colore, Materiale es: PLA Nero Prusa).
*   **Bobina**: Rappresenta il singolo rotolo fisico di plastica. L'app traccia il peso iniziale, i grammi consumati da ogni stampa e calcola il peso residuo.

### **Stampanti e Piatti (Printers & Plates)**
*   **Stampante**: Definisce il nome, il modello e il consumo energetico (Watt) per il calcolo dei costi elettrici.
*   **Piatto**: Le diverse superfici di stampa (PEI Smooth, Textured, ecc.) che possono essere associate alle stampanti.

---

## 6. Workflow Tipico

1.  **Crea un Master**: Definisci il nome e aggiungi le **Parti**.
2.  **Configura i Template**: Per ogni parte, aggiungi i file G-Code che vuoi stampare, associando stampante e consumo filamento.
3.  **Definisci gli Output**: Specifica quali oggetti (e quanti) compongono un "set" completo di questo progetto.
4.  **Crea un Ordine**: Dalla libreria Master, clicca su "Crea Ordine" e scegli quanti set produrre.
5.  **Produci**: Vai nel dettaglio dell'Ordine e gestisci gli stati dei singoli file mentre le stampanti lavorano.
6.  **Completa e Versa**: Clicca su "Completa" per trasformare la produzione in oggetti reali nel magazzino.
7.  **Vendi**: Gestisci le vendite dal modulo Magazzino o Vendite per tracciare ricavi e profitti netti.
