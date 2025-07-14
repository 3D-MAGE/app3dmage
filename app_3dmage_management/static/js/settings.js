document.addEventListener('DOMContentLoaded', function () {
    const csrftoken = getCookie('csrftoken');

    // --- Logica per ricordare l'accordion/tab aperto ---
    const navLinks = document.querySelectorAll('.settings-nav .nav-link');
    navLinks.forEach(link => {
        link.addEventListener('click', function() {
            sessionStorage.setItem('activeSettingsTab', this.id);
        });
    });

    const activeTabId = sessionStorage.getItem('activeSettingsTab');
    if (activeTabId) {
        const activeTab = document.getElementById(activeTabId);
        if (activeTab) {
            new bootstrap.Tab(activeTab).show();
        }
    }

    // --- Logica per i modal di modifica/aggiunta ---
    document.getElementById('addPlateModal')?.addEventListener('show.bs.modal', function(e) {
        const button = e.relatedTarget;
        if (button && button.dataset.printerId) {
            this.querySelector('select[name="printer"]').value = button.dataset.printerId;
        }
    });

    const editModalEl = document.getElementById('editModal');
    if(editModalEl) {
        const editModal = new bootstrap.Modal(editModalEl);
        const form = editModalEl.querySelector('form');
        const title = editModalEl.querySelector('.modal-title');
        const body = editModalEl.querySelector('.modal-body');

        editModalEl.addEventListener('show.bs.modal', function (event) {
            const button = event.relatedTarget;
            const type = button.dataset.type;
            const id = button.dataset.id;
            form.action = `/settings/${type}/${id}/edit/`;
            title.textContent = `Modifica ${type.replace(/_/g, ' ')}`;
            body.innerHTML = '<p class="text-center text-muted">Caricamento...</p>';

            fetch(`/settings/${type}/${id}/details/`)
            .then(res => res.json())
            .then(data => {
                const template = document.getElementById(`${type}-form-template`);
                if (!template) {
                    body.innerHTML = '<p class="text-danger">Errore: Template del form non trovato.</p>';
                    return;
                }

                body.innerHTML = '';
                body.appendChild(template.content.cloneNode(true));

                for (const key in data) {
                    const field = body.querySelector(`[name="${key}"]`);
                    if (field) {
                        field.value = data[key];
                    }
                }
            });
        });

        form.addEventListener('submit', function(e) {
            e.preventDefault();
            fetch(this.action, {
                method: 'POST',
                body: new FormData(this),
                headers: {'X-CSRFToken': csrftoken}
            })
            .then(res => res.json())
            .then(data => {
                if(data.status === 'ok') {
                    editModal.hide();
                    showToast('Modifiche salvate con successo!', 'success');
                    setTimeout(() => window.location.reload(), 500);
                } else {
                    showToast(data.message || 'Errore durante la modifica.', 'error');
                }
            });
        });
    }

    document.querySelectorAll('.delete-btn').forEach(button => {
        button.addEventListener('click', function(e) {
            e.stopPropagation();
            if (confirm('Sei sicuro di voler eliminare questo elemento?')) {
                const type = this.dataset.type;
                const id = this.dataset.id;
                fetch(`/settings/${type}/${id}/delete/`, { method: 'POST', headers: {'X-CSRFToken': csrftoken} })
                .then(res => res.json()).then(data => {
                    if(data.status === 'ok') {
                        window.location.reload();
                    } else {
                        showToast(data.message || 'Errore.', 'error');
                    }
                });
            }
        });
    });

    // NUOVO: Logica per il reset del contatore di manutenzione
    document.querySelectorAll('.reset-maintenance-btn').forEach(button => {
        button.addEventListener('click', function() {
            const printerId = this.dataset.printerId;
            if (confirm(`Sei sicuro di voler azzerare il contatore parziale per questa stampante?`)) {
                fetch(`/settings/maintenance/reset_counter/${printerId}/`, {
                    method: 'POST',
                    headers: {'X-CSRFToken': csrftoken}
                })
                .then(res => res.json())
                .then(data => {
                    if (data.status === 'ok') {
                        showToast(data.message, 'success');
                        setTimeout(() => window.location.reload(), 500);
                    } else {
                        showToast(data.message || 'Errore durante il reset.', 'error');
                    }
                });
            }
        });
    });

    // --- Logica per lo switcher del tema ---
    const themeSwitcher = document.getElementById('theme-switcher');
    if (themeSwitcher) {
        const currentTheme = localStorage.getItem('theme') || 'dark';
        const currentThemeRadio = document.getElementById(`theme-${currentTheme}`);
        if (currentThemeRadio) {
            currentThemeRadio.checked = true;
        }

        themeSwitcher.addEventListener('change', function(e) {
            if (e.target.name === 'theme') {
                const newTheme = e.target.value;
                localStorage.setItem('theme', newTheme);
                if (newTheme === 'light') {
                    document.body.classList.add('light-theme');
                } else {
                    document.body.classList.remove('light-theme');
                }
            }
        });
    }
});

// Funzione helper per ottenere il cookie CSRF (se non già globale)
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

// Funzione helper per mostrare toast (se non già globale)
function showToast(message, type = 'success') {
    const toastEl = document.getElementById('appToast');
    if (toastEl) {
        const toastBody = toastEl.querySelector('.toast-body');
        toastEl.classList.remove('bg-success', 'bg-danger', 'bg-warning', 'bg-info');
        const bgColor = type === 'error' ? 'danger' : type;
        toastEl.classList.add(`bg-${bgColor}`);
        toastBody.textContent = message;
        new bootstrap.Toast(toastEl).show();
    } else {
        console.log(`Toast (${type}): ${message}`);
    }
}
