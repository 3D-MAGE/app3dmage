document.addEventListener('click', function(e) {
    const row = e.target.closest('.clickable-row');
    if (!row) return;

    // Se la riga è bloccata, mostriamo un avviso e non facciamo nulla
    if (row.classList.contains('row-locked')) {
        if (typeof showToast === 'function') {
            showToast('Questo progetto è attualmente in modifica da un altro utente.', 'warning');
        }
        return;
    }

    // Impedisce al link di attivarsi se si clicca su un bottone o un link dentro la riga
    if (e.target.closest('button, a, form')) return;

    // SALVA LO STATO CORRENTE (URL con filtri)
    localStorage.setItem('last_dashboard_url', window.location.href);

    window.location.href = row.dataset.url;
});
