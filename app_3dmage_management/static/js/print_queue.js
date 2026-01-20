// --- Variabili Globali per lo stato di Drag ---
let isDraggingAnywhere = false;

function initPrintQueue() {
    const queueScriptTag = document.getElementById('print-queue-data');
    if (!queueScriptTag) return;

    const updateQueueUrl = queueScriptTag.dataset.updateQueueUrl;
    const setStatusUrlBase = queueScriptTag.dataset.setStatusUrlBase;
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
        if (!container) return;
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

    // 1. Link cliccabili (Delegated)
    // Rimosso l'event listener diretto sulle card, usiamo delega su document in fondo

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
                    isDraggingAnywhere = true;
                    document.querySelectorAll('.empty-slot').forEach(el => el.style.display = 'none');
                },

                onEnd: function(evt) {
                    isDraggingAnywhere = false;
                    updateEmptySlots(evt.to);
                    updateEmptySlots(evt.from);
                },

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
            updateEmptySlots(container);
        });
    });
}

// Inizializzazione al caricamento e dopo ogni swap HTMX
document.addEventListener('DOMContentLoaded', initPrintQueue);
document.addEventListener('htmx:afterSettle', function(evt) {
    if (evt.detail.target.id === 'print-queue-board-wrapper') {
        initPrintQueue();
    }
});

// Impedisce HTMX di aggiornare mentre si sta trascinando
document.addEventListener('htmx:beforeRequest', function(evt) {
    if (isDraggingAnywhere && evt.detail.elt.id === 'print-queue-board-wrapper') {
        evt.preventDefault();
    }
});

// Delega eventi per i click sulle card (per sopravvivere agli swap HTMX)
document.addEventListener('click', function(e) {
    const card = e.target.closest('.kanban-card[data-url]');
    if (card && !isDraggingAnywhere) {
        if (e.target.closest('button, a, form')) return;
        window.location.href = card.dataset.url;
    }
});

// --- FUNZIONE DI ORDINAMENTO (GLOBALE) ---
function sortQueue(printerId) {
    const container = document.querySelector(`.print-queue-container[data-printer-id="${printerId}"]`);
    if (!container) return;

    const cards = Array.from(container.querySelectorAll('.kanban-card'));
    if (cards.length < 2) return;

    cards.sort((a, b) => {
        const priorityA = parseInt(a.dataset.sortPriority) || 99;
        const priorityB = parseInt(b.dataset.sortPriority) || 99;
        if (priorityA !== priorityB) return priorityA - priorityB;
        const matA = (a.dataset.sortMaterial || '').toLowerCase();
        const matB = (b.dataset.sortMaterial || '').toLowerCase();
        if (matA < matB) return -1;
        if (matA > matB) return 1;
        return 0;
    });

    cards.forEach(card => container.appendChild(card));

    const queueScriptTag = document.getElementById('print-queue-data');
    if (!queueScriptTag) return;
    const updateQueueUrl = queueScriptTag.dataset.updateQueueUrl;
    const fileIds = cards.map(card => card.dataset.printFileId);

    fetch(updateQueueUrl, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify({ printer_id: printerId, file_ids: fileIds })
    });
}
