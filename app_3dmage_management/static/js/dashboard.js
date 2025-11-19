document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('.clickable-row').forEach(row => {
        row.addEventListener('click', function(e) {
            // Questo controllo impedisce al link di attivarsi se si clicca su un bottone o un link dentro la riga (se mai ce ne fossero)
            if (e.target.closest('button, a, form')) return;

            // SALVA LO STATO CORRENTE (URL con filtri)
            localStorage.setItem('last_dashboard_url', window.location.href);

            window.location.href = this.dataset.url;
        });
    });
});
