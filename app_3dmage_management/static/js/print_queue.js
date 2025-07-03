document.addEventListener('DOMContentLoaded', function () {
    const queueScriptTag = document.getElementById('print-queue-data');
    if (!queueScriptTag) return;

    const updateQueueUrl = queueScriptTag.dataset.updateQueueUrl;
    const setStatusUrlBase = queueScriptTag.dataset.setStatusUrlBase;
    const csrftoken = getCookie('csrftoken');

    // Logica per rendere le card dei link cliccabili
    document.querySelectorAll('.kanban-card[data-url]').forEach(card => {
        let isDragging = false;
        card.addEventListener('mousedown', () => { isDragging = false; });
        card.addEventListener('mousemove', () => { isDragging = true; });
        card.addEventListener('mouseup', function() {
            if (!isDragging) {
                window.location.href = this.dataset.url;
            }
        });
    });

    // Raccoglie tutti i contenitori (sia 'In Stampa' che 'In Coda')
    const allContainers = document.querySelectorAll('.print-queue-container, .printing-now-container');

    allContainers.forEach(container => {
        new Sortable(container, {
            group: 'print_files',
            animation: 150,
            ghostClass: 'kanban-card-ghost',

            // Funzione chiamata quando un elemento viene aggiunto a un contenitore
            onAdd: function (evt) {
                const item = evt.item;
                const toContainer = evt.to;
                const fileId = item.dataset.printFileId;

                let newStatus = 'TODO'; // Default
                if (toContainer.classList.contains('printing-now-container')) {
                    newStatus = 'PRINTING';
                }

                const url = `${setStatusUrlBase}${fileId}/set_status/`;

                fetch(url, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrftoken},
                    body: JSON.stringify({ new_status: newStatus })
                })
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'ok') {
                        showToast('Stato aggiornato, ricarico...');
                        // Ricarica la pagina per mostrare lo stato corretto e consistente
                        setTimeout(() => window.location.reload(), 800);
                    } else {
                        showToast(`Errore: ${data.message}`, 'error');
                        // Ricarica per annullare la modifica visiva non andata a buon fine
                        setTimeout(() => window.location.reload(), 1500);
                    }
                })
                .catch(error => {
                    showToast('Errore di connessione.', 'error');
                    setTimeout(() => window.location.reload(), 1500);
                });
            },

            // Funzione chiamata quando l'ordinamento finisce nella stessa lista
            onEnd: function (evt) {
                // Questo si attiva solo per riordinare la lista 'TODO'
                if (evt.from === evt.to && evt.from.classList.contains('print-queue-container')) {
                    const printerId = evt.to.dataset.printerId;
                    const fileIds = Array.from(evt.to.children).map(card => card.dataset.printFileId);

                    fetch(updateQueueUrl, {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrftoken},
                        body: JSON.stringify({ printer_id: printerId, file_ids: fileIds })
                    })
                    .then(response => response.json())
                    .then(data => {
                        if (data.status === 'ok') {
                            showToast('Ordine della coda aggiornato!');
                        } else {
                            showToast(`Errore: ${data.message}`, 'error');
                        }
                    })
                    .catch(error => showToast('Errore di connessione.', 'error'));
                }
            },
        });
    });
});
