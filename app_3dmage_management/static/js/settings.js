document.addEventListener('DOMContentLoaded', function () {
    // --- Logica per ricordare l'accordion aperto ---
    const accordionTriggers = document.querySelectorAll('.add-plate-btn, .add-maintenance-log-btn, .edit-btn, .delete-btn');
    accordionTriggers.forEach(btn => {
        btn.addEventListener('click', function() {
            const collapseTarget = this.closest('.accordion-item')?.querySelector('.accordion-collapse');
            if (collapseTarget) {
                sessionStorage.setItem('openAccordionId', collapseTarget.id);
            }
        });
    });

    const openAccordionId = sessionStorage.getItem('openAccordionId');
    if (openAccordionId) {
        const collapseElement = document.getElementById(openAccordionId);
        if (collapseElement) {
            new bootstrap.Collapse(collapseElement, { toggle: true });
        }
        sessionStorage.removeItem('openAccordionId');
    }

    // --- Logica per i modal di modifica/aggiunta ---
    document.getElementById('addPlateModal')?.addEventListener('show.bs.modal', function(e) {
        const button = e.relatedTarget;
        if (button && button.dataset.printerId) {
            this.querySelector('select[name="printer"]').value = button.dataset.printerId;
        }
    });

    const editModal = document.getElementById('editModal');
    if(editModal) {
        const form = editModal.querySelector('form');
        const title = editModal.querySelector('.modal-title');
        const body = editModal.querySelector('.modal-body');

        editModal.addEventListener('show.bs.modal', function (event) {
            const button = event.relatedTarget;
            const type = button.dataset.type;
            const id = button.dataset.id;
            form.action = `/settings/${type}/${id}/edit/`;
            title.textContent = `Modifica ${type.replace(/_/g, ' ')}`;
            body.innerHTML = '<p class="text-center text-muted">Caricamento...</p>';

            fetch(`/settings/${type}/${id}/details/`)
            .then(res => res.json())
            .then(data => {
                // CORREZIONE: Usa i template HTML invece di stringhe JS
                const template = document.getElementById(`${type}-form-template`);
                if (!template) {
                    body.innerHTML = '<p class="text-danger">Errore: Template del form non trovato.</p>';
                    return;
                }

                const formContent = template.content.cloneNode(true);
                body.innerHTML = ''; // Pulisce il contenuto precedente
                body.appendChild(formContent);

                // Popola i campi con i dati ricevuti
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
            fetch(this.action, { method: 'POST', body: new FormData(this), headers: {'X-CSRFToken': csrftoken} })
            .then(res => res.json()).then(data => {
                if(data.status === 'ok') { window.location.reload(); }
                else { showToast(data.message || 'Errore durante la modifica.', 'error'); }
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
                    if(data.status === 'ok') { window.location.reload(); }
                    else { showToast(data.message || 'Errore.', 'error'); }
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
