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

function showToast(message, type = 'success') {
    const toastEl = document.getElementById('appToast');
    if (!toastEl) return;
    const toastBody = toastEl.querySelector('.toast-body');

    // Rimuove le classi di colore precedenti
    toastEl.classList.remove('bg-success', 'bg-danger', 'bg-warning', 'bg-info');

    // Aggiunge la nuova classe di colore
    const bgColor = type === 'error' ? 'danger' : type; // 'error' diventa 'danger'
    toastEl.classList.add(`bg-${bgColor}`);

    toastBody.textContent = message;
    new bootstrap.Toast(toastEl).show();
}

// NUOVO: Funzioni per gestire l'overlay di caricamento
function showLoader() {
    document.getElementById('loading-overlay')?.classList.remove('d-none');
}

function hideLoader() {
    document.getElementById('loading-overlay')?.classList.add('d-none');
}

// --- Gestione Blocchi Concorrenza ---
let lockHeartbeatInterval = null;

async function acquireLock(model, id) {
    try {
        const response = await fetch(`/ajax/lock/${model}/${id}/`, {
            method: 'POST',
            headers: { 'X-CSRFToken': getCookie('csrftoken') }
        });
        const data = await response.json();
        if (response.status === 403) {
            showToast(data.message, 'warning');
            return false;
        }
        return data.status === 'ok';
    } catch (e) {
        console.error('Errore durante acquisizione blocco:', e);
        return false;
    }
}

async function releaseLock(model, id) {
    if (!id) return;
    const url = `/ajax/unlock/${model}/${id}/`;
    const csrfToken = getCookie('csrftoken');
    
    // Prefer sendBeacon for unload/navigation scenarios
    if (navigator.sendBeacon) {
        const formData = new FormData();
        formData.append('csrfmiddlewaretoken', csrfToken);
        // sendBeacon uses POST by default, but doesn't support custom headers easily for CSRF if not FormData
        // Django expects CSRF token in cookie OR header OR form data. FormData is safest for beacon.
        const success = navigator.sendBeacon(url, formData);
        if (success) return;
    }

    try {
        await fetch(url, {
            method: 'POST',
            headers: { 
                'X-CSRFToken': csrfToken,
                'Content-Type': 'application/x-www-form-urlencoded' 
            },
            keepalive: true // Fallback for modern browsers if beacon fails or not used
        });
    } catch (e) {
        console.error('Errore durante rilascio blocco:', e);
    }
}

function startLockHeartbeat(model, id) {
    if (lockHeartbeatInterval) clearInterval(lockHeartbeatInterval);
    lockHeartbeatInterval = setInterval(() => acquireLock(model, id), 60000); // Ogni minuto
    
    // Rilascio automatico alla chiusura
    window.addEventListener('beforeunload', () => releaseLock(model, id));
}

// --- Gestione Notifiche Globali ---
async function fetchNotifications() {
    const badge = document.getElementById('notificationsBadge');
    const list = document.getElementById('notificationsList');
    if (!badge || !list) return;

    try {
        const response = await fetch('/api/notifications/');
        if (!response.ok) return;
        const data = await response.json();

        if (data.count > 0) {
            badge.textContent = data.count > 9 ? '9+' : data.count;
            badge.classList.remove('d-none');
        } else {
            badge.classList.add('d-none');
        }

        if (data.notifications && data.notifications.length > 0) {
            list.innerHTML = data.notifications.map(n => {
                let icon = 'bi-info-circle text-info';
                let iconBg = 'bg-info bg-opacity-25';
                if (n.level === 'WARNING') {
                    icon = 'bi-exclamation-triangle-fill text-warning';
                    iconBg = 'bg-warning bg-opacity-25';
                } else if (n.level === 'DANGER') {
                    icon = 'bi-exclamation-octagon-fill text-danger';
                    iconBg = 'bg-danger bg-opacity-25';
                } else if (n.level === 'SUCCESS') {
                    icon = 'bi-check-circle-fill text-success';
                    iconBg = 'bg-success bg-opacity-25';
                }

                const link = n.related_url ? n.related_url : '#';
                return `
                    <li class="px-3 py-2 border-bottom border-secondary border-opacity-25 list-group-item bg-transparent text-light">
                        <a href="${link}" class="text-decoration-none text-light d-flex align-items-start gap-2">
                            <span class="badge rounded-circle p-2 ${iconBg} mt-1 flex-shrink-0">
                                <i class="bi ${icon} fs-6"></i>
                            </span>
                            <div class="flex-grow-1 overflow-hidden">
                                <div class="small fw-semibold text-white text-break">${n.message}</div>
                                ${n.time_ago ? `<div class="text-white-50 small mt-1" style="font-size: 0.75rem;"><i class="bi bi-clock me-1"></i>${n.time_ago}</div>` : ''}
                            </div>
                        </a>
                    </li>
                `;
            }).join('');
        } else {
            list.innerHTML = '<li class="p-3 text-center text-muted small"><i class="bi bi-bell-slash me-1"></i>Nessuna notifica non letta</li>';
        }
    } catch (e) {
        console.error('Errore durante fetch notifiche:', e);
    }
}

async function markAllNotificationsAsRead(e) {
    if (e) {
        e.preventDefault();
        e.stopPropagation();
    }
    try {
        const res = await fetch('/api/notifications/mark-read/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCookie('csrftoken'),
                'Content-Type': 'application/json'
            }
        });
        if (res.ok) {
            const badge = document.getElementById('notificationsBadge');
            if (badge) badge.classList.add('d-none');
            const list = document.getElementById('notificationsList');
            if (list) list.innerHTML = '<li class="p-3 text-center text-muted small"><i class="bi bi-check2 me-1"></i>Tutte le notifiche lette</li>';
        }
    } catch (err) {
        console.error('Errore markAllNotificationsAsRead:', err);
    }
}

// --- Gestione Offcanvas Note Rapide ---
async function loadQuickNotes() {
    const badge = document.getElementById('quickNotesBadge');
    const offcanvasBadge = document.getElementById('offcanvasActiveBadge');
    const list = document.getElementById('offcanvasNotesList');
    if (!list) return;

    try {
        const res = await fetch('/notes/api/quick/');
        if (!res.ok) return;
        const data = await res.json();

        const count = data.count || 0;
        if (badge) {
            if (count > 0) {
                badge.textContent = count > 9 ? '9+' : count;
                badge.classList.remove('d-none');
            } else {
                badge.classList.add('d-none');
            }
        }
        if (offcanvasBadge) {
            offcanvasBadge.textContent = count;
        }

        if (data.notes && data.notes.length > 0) {
            list.innerHTML = data.notes.map(n => {
                let badgeClass = 'bg-secondary';
                if (n.category_code === 'PURCHASE') badgeClass = 'bg-warning text-dark';
                else if (n.category_code === 'MAINTENANCE') badgeClass = 'bg-info text-dark';
                else if (n.category_code === 'PRODUCTION') badgeClass = 'bg-success';

                let dueHtml = '';
                if (n.is_overdue) {
                    dueHtml = `<span class="badge bg-danger text-white ms-1" style="font-size:0.65rem;">Scaduta</span>`;
                } else if (n.is_due_today) {
                    dueHtml = `<span class="badge bg-warning text-dark ms-1" style="font-size:0.65rem;">Oggi</span>`;
                } else if (n.due_date) {
                    dueHtml = `<small class="text-muted ms-1" style="font-size:0.7rem;">${n.due_date}</small>`;
                }

                return `
                    <div class="card bg-dark border-secondary border-opacity-50 mb-2 p-2" id="quick-note-${n.id}">
                        <div class="d-flex align-items-start gap-2">
                            <input type="checkbox" class="form-check-input mt-1 flex-shrink-0"
                                   style="cursor: pointer; width: 1.15rem; height: 1.15rem;"
                                   onchange="toggleQuickNote(${n.id}, this)">
                            <div class="flex-grow-1 overflow-hidden">
                                <div class="small fw-semibold text-white text-truncate">${n.title}</div>
                                <div class="d-flex align-items-center gap-1 mt-1 flex-wrap">
                                    <span class="badge ${badgeClass}" style="font-size: 0.65rem;">${n.category}</span>
                                    ${dueHtml}
                                </div>
                            </div>
                        </div>
                    </div>
                `;
            }).join('');
        } else {
            list.innerHTML = `
                <div class="text-center py-4 text-muted">
                    <i class="bi bi-journal-check fs-2 d-block mb-2 text-secondary"></i>
                    Nessun promemoria attivo!
                </div>
            `;
        }
    } catch (e) {
        console.error('Errore durante caricamento note rapide:', e);
    }
}

async function toggleQuickNote(noteId, checkboxEl) {
    try {
        const res = await fetch(`/notes/${noteId}/toggle/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCookie('csrftoken'),
                'Content-Type': 'application/json'
            }
        });
        const data = await res.json();
        if (data.status === 'ok') {
            const card = document.getElementById(`quick-note-${noteId}`);
            if (card) {
                card.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
                card.style.opacity = '0.3';
                card.style.transform = 'translateX(20px)';
                setTimeout(() => loadQuickNotes(), 300);
            } else {
                loadQuickNotes();
            }
            // Se siamo nella pagina note, aggiorna anche la tabella
            if (typeof submitFilter === 'function') {
                submitFilter();
            }
        }
    } catch (e) {
        console.error('Errore toggle nota rapida:', e);
    }
}

// Inizializzazione globale al caricamento DOM
document.addEventListener('DOMContentLoaded', function() {
    // Caricamento notifiche e note rapide
    fetchNotifications();
    loadQuickNotes();

    // Polling notifiche ogni 90 secondi
    setInterval(fetchNotifications, 90000);

    // Event listener per aggiunta nota da Offcanvas
    const offcanvasForm = document.getElementById('offcanvasQuickAddForm');
    if (offcanvasForm) {
        offcanvasForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            const input = document.getElementById('offcanvasNoteTitle');
            const title = input.value.trim();
            if (!title) return;

            const formData = new FormData();
            formData.append('title', title);

            try {
                const res = await fetch('/notes/quick-add/', {
                    method: 'POST',
                    headers: { 'X-CSRFToken': getCookie('csrftoken') },
                    body: formData
                });
                const data = await res.json();
                if (data.status === 'ok') {
                    input.value = '';
                    loadQuickNotes();
                    showToast(`Promemoria "${data.title}" aggiunto!`, 'success');
                    if (typeof submitFilter === 'function') {
                        submitFilter();
                    }
                } else {
                    showToast(data.message || 'Errore', 'danger');
                }
            } catch (err) {
                console.error(err);
            }
        });
    }

    // Refresh note all'apertura dell'offcanvas
    const offcanvasEl = document.getElementById('quickNotesOffcanvas');
    if (offcanvasEl) {
        offcanvasEl.addEventListener('show.bs.offcanvas', function() {
            loadQuickNotes();
        });
    }
});
