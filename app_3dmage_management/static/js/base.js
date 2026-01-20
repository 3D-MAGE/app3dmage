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
