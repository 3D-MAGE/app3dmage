document.addEventListener('DOMContentLoaded', function() {
    // Funzione per ottenere il valore di un cookie, necessario per il token CSRF
    const getCookie = (name) => {
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

    // Funzione per mostrare messaggi toast (assumendo che esista in base.js)
    const showToast = (message, type = 'success') => {
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
    };

    // Check for a toast message from a previous page (e.g., after a redirect)
    const toastMessage = sessionStorage.getItem('toastMessage');
    if (toastMessage) {
        const toastType = sessionStorage.getItem('toastType') || 'success';
        showToast(toastMessage, toastType);
        // Clear the message so it doesn't show again on refresh
        sessionStorage.removeItem('toastMessage');
        sessionStorage.removeItem('toastType');
    }

    // Logica popup modifica saldo
    const correctBalanceModal = document.getElementById('correctBalanceModal');
    if (correctBalanceModal) {
        correctBalanceModal.addEventListener('show.bs.modal', function(event) {
            const button = event.relatedTarget;
            const form = correctBalanceModal.querySelector('form');
            form.action = `/payment_method/${button.dataset.methodId}/correct/`;
            correctBalanceModal.querySelector('.modal-title').textContent = `Modifica Saldo: ${button.dataset.methodName}`;
            form.querySelector('[name="new_balance"]').value = button.dataset.methodBalance.replace(',', '.');
        });
    }

    // --- Logica Modifica/Elimina Spesa ---
    const editExpenseModalEl = document.getElementById('editExpenseModal');
    if (editExpenseModalEl) {
        const modal = new bootstrap.Modal(editExpenseModalEl);
        const form = editExpenseModalEl.querySelector('form');
        const deleteBtn = document.getElementById('deleteExpenseBtn');

        // Modals di conferma
        const confirmModalEl = document.getElementById('confirmationModal');
        const confirmModal = new bootstrap.Modal(confirmModalEl);
        const confirmModalTitle = document.getElementById('confirmationModalTitle');
        const confirmModalBody = document.getElementById('confirmationModalBody');
        const confirmActionBtn = document.getElementById('confirmActionBtn');

        // Apri modal di modifica
        document.getElementById('expenses-table')?.addEventListener('click', function(e) {
            const row = e.target.closest('tr.clickable-row');
            if (row && row.dataset.action === 'edit-expense') {
                const expenseId = row.dataset.id;
                form.action = `/expense/${expenseId}/edit/`;
                deleteBtn.dataset.deleteUrl = `/expense/${expenseId}/delete/`;

                fetch(`/expense/${expenseId}/details/`).then(res => res.json()).then(data => {
                    for (const key in data) {
                        const field = form.querySelector(`[name="${key}"]`);
                        if (field) field.value = data[key] || '';
                    }
                    modal.show();
                });
            }
        });

        // Salva modifiche
        form.addEventListener('submit', function(e) {
            e.preventDefault();
            fetch(this.action, { method: 'POST', body: new FormData(this), headers: {'X-CSRFToken': csrftoken} })
            .then(res => res.json()).then(data => {
                if(data.status === 'ok') {
                    showToast('Modifiche salvate con successo!', 'success');
                    setTimeout(() => window.location.reload(), 1000);
                } else {
                    showToast('Errore durante la modifica.', 'error');
                }
            });
        });

        // CORREZIONE: Usa il modal di conferma per l'eliminazione
        deleteBtn.addEventListener('click', function() {
            const deleteUrl = this.dataset.deleteUrl;

            // Imposta il modal di conferma
            if(confirmModalTitle) confirmModalTitle.textContent = 'Conferma Eliminazione Spesa';
            confirmModalBody.textContent = 'Sei sicuro di voler eliminare questa spesa? L\'importo verrà riaccreditato sulla cassa selezionata.';

            // Definisce l'azione del pulsante di conferma
            const deleteAction = () => {
                fetch(deleteUrl, { method: 'POST', headers: {'X-CSRFToken': csrftoken} })
                .then(res => res.json()).then(data => {
                    confirmModal.hide(); // Nasconde il modal di conferma
                    if(data.status === 'ok') {
                        showToast('Spesa eliminata con successo.', 'success');
                        modal.hide(); // Nasconde il modal di modifica
                        setTimeout(() => window.location.reload(), 500);
                    } else {
                        showToast(data.message || 'Errore durante l\'eliminazione.', 'error');
                    }
                });
            };

            // Aggiunge l'evento al pulsante di conferma, assicurandosi che venga eseguito una sola volta
            confirmActionBtn.addEventListener('click', deleteAction, { once: true });

            // Mostra il modal di conferma
            confirmModal.show();
        });
    }

    // Logica per annullare una vendita dalla tabella delle entrate
    document.getElementById('income-table')?.addEventListener('click', function(e) {
        const row = e.target.closest('tr.clickable-row');
        if (!row || row.dataset.action !== 'reverse' || e.target.closest('button')) return;

        const confirmModalEl = document.getElementById('confirmationModal');
        const confirmModal = new bootstrap.Modal(confirmModalEl);
        const confirmModalTitle = document.getElementById('confirmationModalTitle');
        const confirmModalBody = document.getElementById('confirmationModalBody');
        const confirmActionBtn = document.getElementById('confirmActionBtn');

        if(confirmModalTitle) confirmModalTitle.textContent = 'Conferma Storno Vendita';
        confirmModalBody.textContent = `Sei sicuro di voler annullare la vendita per "${row.dataset.name}"? L'importo verrà stornato e l'oggetto/entrata verrà rimosso o ripristinato.`;

        const reverseAction = () => {
            const saleId = row.dataset.id;
            fetch(`/sale/${saleId}/reverse/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrftoken,
                    'X-Requested-With': 'XMLHttpRequest',
                    'Accept': 'application/json'
                }
            })
            .then(response => {
                const contentType = response.headers.get("content-type");
                if (response.ok && contentType && contentType.indexOf("application/json") !== -1) {
                    return response.json();
                }
                if (response.ok) {
                    return { redirect_url: window.location.href, status: 'ok' };
                }
                return response.text().then(text => {
                    try {
                        const errorData = JSON.parse(text);
                        throw new Error(errorData.message || 'Errore del server');
                    } catch (e) {
                        console.error("Server returned non-JSON error:", text);
                        throw new Error('Errore del server. Risposta non valida.');
                    }
                });
            })
            .then(data => {
                if (data.redirect_url) {
                    sessionStorage.setItem('toastMessage', 'Operazione di storno completata!');
                    sessionStorage.setItem('toastType', 'success');
                    window.location.href = data.redirect_url;
                } else {
                    showToast('Operazione di storno completata!', 'success');
                    setTimeout(() => window.location.reload(), 1000);
                }
            })
            .catch(error => {
                console.error('Errore durante lo storno:', error);
                showToast(error.message || 'Errore durante lo storno della vendita.', 'error');
            });
        };

        confirmActionBtn.addEventListener('click', reverseAction, { once: true });
        confirmModal.show();
    });
});
