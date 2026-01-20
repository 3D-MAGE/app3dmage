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

            console.log(`fetching details for ${type} ${id}`);
            fetch(`/settings/${type}/${id}/details/`)
            .then(res => {
                if(!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
                return res.json();
            })
            .then(data => {
                console.log("details data:", data);
                const template = document.getElementById(`${type}-form-template`);
                if (!template) {
                    body.innerHTML = `<p class="text-danger">Errore: Template '${type}-form-template' non trovato.</p>`;
                    return;
                }

                body.innerHTML = '';
                body.appendChild(template.content.cloneNode(true));

                for (const key in data) {
                    const field = body.querySelector(`[name="${key}"]`);
                    if (field) {
                        if (field.type === 'checkbox') {
                            field.checked = !!data[key];
                        } else {
                            field.value = data[key];
                        }
                    }
                }
            })
            .catch(err => {
                console.error("Fetch error:", err);
                body.innerHTML = `<p class="text-danger">Errore durante il caricamento: ${err.message}</p>`;
            });
        });

        form.addEventListener('submit', function(e) {
            e.preventDefault();
            const submitBtn = this.querySelector('button[type="submit"]');
            const originalBtnText = submitBtn.innerHTML;
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Salvataggio...';

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
                    console.error("Save error:", data);
                    let errMsg = 'Errore durante la modifica.';
                    if (data.errors) {
                       try {
                           const errors = JSON.parse(data.errors);
                           errMsg = Object.values(errors).map(e => e[0].message).join(', ');
                       } catch(ex) { errMsg = 'Dati non validi.'; }
                    }
                    showToast(errMsg, 'error');
                }
            })
            .catch(err => {
                console.error("Submit error:", err);
                showToast('Errore di rete o del server.', 'error');
            })
            .finally(() => {
                submitBtn.disabled = false;
                submitBtn.innerHTML = originalBtnText;
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
                    document.documentElement.classList.add('light-theme');
                } else {
                    document.documentElement.classList.remove('light-theme');
                }
            }
        });
    }

    // NUOVO: Logica per l'auto-submit del filtro per anno
    const yearFilterForm = document.getElementById('yearFilterForm');
    if (yearFilterForm) {
        const yearSelect = yearFilterForm.querySelector('select');
        yearSelect.addEventListener('change', function() {
            yearFilterForm.submit();
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

function showToast(message, type = 'success') {
    const toastEl = document.getElementById('appToast');
    if (toastEl) {
        const toast = new bootstrap.Toast(toastEl);
        const body = toastEl.querySelector('.toast-body');
        body.textContent = message;
        toastEl.classList.remove('bg-success', 'bg-danger', 'bg-info', 'bg-warning');
        
        if (type === 'error' || type === 'danger') toastEl.classList.add('bg-danger');
        else if (type === 'success') toastEl.classList.add('bg-success');
        else if (type === 'warning') toastEl.classList.add('bg-warning');
        else toastEl.classList.add('bg-info');
        
        toast.show();
    } else {
        console.log(`Toast (${type}): ${message}`);
    }
}
