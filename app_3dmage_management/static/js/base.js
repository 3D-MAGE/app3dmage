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
