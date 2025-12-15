document.addEventListener('DOMContentLoaded', function () {
    const queueScriptTag = document.getElementById('print-queue-data');
    if (!queueScriptTag) return;

    const updateQueueUrl = queueScriptTag.dataset.updateQueueUrl;
    const setStatusUrlBase = queueScriptTag.dataset.setStatusUrlBase;

    // Helper per CSRF Token
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
    const csrftoken = getCookie('csrftoken');

    // Funzione helper per le notifiche
    function showNotification(msg, type = 'info') {
        if (typeof showToast === 'function') {
            showToast(msg, type);
        } else {
            console.log(type.toUpperCase() + ': ' + msg);
        }
    }

    // Funzione per mostrare/nascondere "Slot Vuoto"
    function updateEmptySlots(container) {
        const emptySlot = container.querySelector('.empty-slot');
        if (emptySlot) {
            const cards = container.querySelectorAll('.kanban-card:not(.kanban-card-ghost)');
            emptySlot.style.display = cards.length === 0 ? 'flex' : 'none';
        }
    }

    // --- Aggiorna Grafica Card (Badge) ---
    function updateCardVisuals(card, targetStatus) {
        let statusBadge = card.querySelector('.badge[class*="bg-print-status-"]');

        if (targetStatus === 'PRINTING') {
            if (statusBadge) {
                statusBadge.style.display = '';
                statusBadge.textContent = 'In Stampa';
                statusBadge.className = statusBadge.className.replace(/bg-print-status-\w+/, 'bg-print-status-printing');
            } else {
                const priorityBadge = card.querySelector('.badge[class*="bg-priority-"]');
                statusBadge = document.createElement('span');
                statusBadge.className = 'badge bg-print-status-printing me-1';
                statusBadge.textContent = 'In Stampa';
                if (priorityBadge && priorityBadge.parentNode) {
                    priorityBadge.parentNode.insertBefore(statusBadge, priorityBadge);
                } else {
                    const header = card.querySelector('.kanban-card-header');
                    if(header) header.appendChild(statusBadge);
                }
            }
        } else {
            if (statusBadge) {
                statusBadge.style.display = 'none';
            }
        }
    }

    // 1. Link cliccabili
    document.querySelectorAll('.kanban-card[data-url]').forEach(card => {
        let isDragging = false;
        card.addEventListener('mousedown', () => { isDragging = false; });
        card.addEventListener('mousemove', () => { isDragging = true; });
        card.addEventListener('mouseup', function() {
            if (!isDragging) window.location.href = this.dataset.url;
        });
    });

    // 2. Inizializzazione Sortable
    const printerColumns = document.querySelectorAll('.kanban-column');

    printerColumns.forEach(column => {
        let printerId = 'default';
        if (column.id && column.id.includes('-')) {
            printerId = column.id.split('-')[1];
        }
        const groupName = 'printer_group_' + printerId;

        const containers = column.querySelectorAll('.print-queue-container, .printing-now-container');

        containers.forEach(container => {
            new Sortable(container, {
                group: groupName,
                draggable: '.kanban-card',
                animation: 150,
                ghostClass: 'kanban-card-ghost',

                onStart: function(evt) {
                    document.querySelectorAll('.empty-slot').forEach(el => el.style.display = 'none');
                },

                onEnd: function(evt) {
                    updateEmptySlots(evt.to);
                    updateEmptySlots(evt.from);
                },

                // --- LOGICA DI RILASCIO ---
                onAdd: function (evt) {
                    const item = evt.item;
                    const toContainer = evt.to;
                    const fromContainer = evt.from;
                    const fileId = item.dataset.printFileId;

                    if (toContainer.classList.contains('printing-now-container')) {
                        const currentCards = toContainer.querySelectorAll('.kanban-card:not(.kanban-card-ghost)');
                        if (currentCards.length > 1) {
                            showNotification('C\'è già un file in stampa!', 'warning');
                            fromContainer.appendChild(item);
                            updateEmptySlots(toContainer);
                            updateEmptySlots(fromContainer);
                            return;
                        }
                    }

                    let statusToSend = '';
                    if (toContainer.classList.contains('printing-now-container')) {
                        statusToSend = 'PRINTING';
                    } else if (toContainer.classList.contains('print-queue-container')) {
                        statusToSend = 'TODO';
                    }

                    updateCardVisuals(item, statusToSend);

                    fetch(`${setStatusUrlBase}${fileId}/set_status/`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': csrftoken
                        },
                        body: JSON.stringify({ new_status: statusToSend })
                    })
                    .then(response => response.json())
                    .then(data => {
                        if (data.status === 'ok') {
                            showNotification('Stato aggiornato!', 'success');
                        } else {
                            showNotification('Errore: ' + data.message, 'error');
                            const originalStatus = (statusToSend === 'PRINTING') ? 'TODO' : 'PRINTING';
                            updateCardVisuals(item, originalStatus);
                            fromContainer.appendChild(item);
                            updateEmptySlots(toContainer);
                            updateEmptySlots(fromContainer);
                        }
                    })
                    .catch(error => {
                        console.error('Fetch error:', error);
                        showNotification('Errore di connessione', 'error');
                        const originalStatus = (statusToSend === 'PRINTING') ? 'TODO' : 'PRINTING';
                        updateCardVisuals(item, originalStatus);
                        fromContainer.appendChild(item);
                        updateEmptySlots(toContainer);
                        updateEmptySlots(fromContainer);
                    });
                },

                onUpdate: function (evt) {
                    if (evt.to.classList.contains('print-queue-container')) {
                        let pId = 'default';
                        const col = evt.to.closest('.kanban-column');
                        if (col && col.id.includes('-')) pId = col.id.split('-')[1];

                        const fileIds = Array.from(evt.to.querySelectorAll('.kanban-card'))
                            .map(card => card.dataset.printFileId);

                        fetch(updateQueueUrl, {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrftoken},
                            body: JSON.stringify({ printer_id: pId, file_ids: fileIds })
                        });
                    }
                }
            });
        });
        column.querySelectorAll('.print-queue-container, .printing-now-container').forEach(c => updateEmptySlots(c));
    });
});

// --- FUNZIONE DI ORDINAMENTO (GLOBALE) ---
// Deve stare fuori dal DOMContentLoaded per essere vista dall'HTML 'onclick'
function sortQueue(printerId) {
    const container = document.querySelector(`.print-queue-container[data-printer-id="${printerId}"]`);
    if (!container) return;

    const cards = Array.from(container.querySelectorAll('.kanban-card'));
    if (cards.length < 2) return;

    // Ordinamento: Priorità (ASC) -> Materiale (ASC)
    cards.sort((a, b) => {
        const priorityA = parseInt(a.dataset.sortPriority) || 99;
        const priorityB = parseInt(b.dataset.sortPriority) || 99;

        if (priorityA !== priorityB) {
            return priorityA - priorityB;
        }

        const matA = (a.dataset.sortMaterial || '').toLowerCase();
        const matB = (b.dataset.sortMaterial || '').toLowerCase();

        if (matA < matB) return -1;
        if (matA > matB) return 1;
        return 0;
    });

    cards.forEach(card => container.appendChild(card));

    // Salvataggio
    const queueScriptTag = document.getElementById('print-queue-data');
    if (!queueScriptTag) return;
    const updateQueueUrl = queueScriptTag.dataset.updateQueueUrl;

    // Funzione interna per recuperare il cookie CSRF al momento del click
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    const fileIds = cards.map(card => card.dataset.printFileId);

    fetch(updateQueueUrl, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify({ printer_id: printerId, file_ids: fileIds })
    })
    .then(res => {
        if(res.ok) {
            console.log('Ordinamento salvato per stampante ' + printerId);
        }
    });
}
