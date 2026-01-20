document.addEventListener('DOMContentLoaded', function() {
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

    const toastMessage = sessionStorage.getItem('toastMessage');
    if (toastMessage) {
        const toastType = sessionStorage.getItem('toastType') || 'success';
        showToast(toastMessage, toastType);
        sessionStorage.removeItem('toastMessage');
        sessionStorage.removeItem('toastType');
    }

    // --- Logica popup modifica saldo ---
    const correctBalanceModalEl = document.getElementById('correctBalanceModal');
    if (correctBalanceModalEl) {
        const form = correctBalanceModalEl.querySelector('form');

        correctBalanceModalEl.addEventListener('show.bs.modal', function(event) {
            const button = event.relatedTarget;
            // Imposta l'action URL corretto
            form.action = `/payment_method/${button.dataset.methodId}/correct/`;
            correctBalanceModalEl.querySelector('.modal-title').textContent = `Modifica Saldo: ${button.dataset.methodName}`;

            // Imposta il valore
            form.querySelector('[name="new_balance"]').value = button.dataset.methodBalance;
        });

        // GESTIONE SUBMIT AJAX PER IL MODIFICA SALDO
        form.addEventListener('submit', function(e) {
            e.preventDefault();

            const balanceInput = form.querySelector('[name="new_balance"]');
            const originalVal = balanceInput.value;
            // Sostituisci virgola con punto per il backend (se l'utente ha digitato col tastierino italiano)
            balanceInput.value = originalVal.replace(',', '.');

            const formData = new FormData(form);

            fetch(form.action, {
                method: 'POST',
                body: formData,
                headers: { 'X-CSRFToken': csrftoken }
            })
            .then(res => res.json())
            .then(data => {
                if (data.status === 'ok') {
                    const modal = bootstrap.Modal.getInstance(correctBalanceModalEl);
                    modal.hide();
                    showToast('Saldo aggiornato con successo!', 'success');
                    setTimeout(() => window.location.reload(), 1000);
                } else {
                    // Ripristina valore originale in caso di errore
                    balanceInput.value = originalVal;
                    showToast('Errore: ' + (data.errors ? Object.values(JSON.parse(data.errors)).join(' ') : data.message || 'Errore sconosciuto'), 'error');
                }
            })
            .catch(err => {
                console.error(err);
                balanceInput.value = originalVal;
                showToast('Errore di connessione.', 'error');
            });
        });
    }

    // --- Logica Modifica/Elimina Spesa ---
    const editExpenseModalEl = document.getElementById('editExpenseModal');
    if (editExpenseModalEl) {
        const modal = new bootstrap.Modal(editExpenseModalEl);
        const form = editExpenseModalEl.querySelector('form');
        const deleteBtn = document.getElementById('deleteExpenseBtn');
        const confirmModalEl = document.getElementById('confirmationModal');
        const confirmModal = new bootstrap.Modal(confirmModalEl);
        const confirmModalTitle = document.getElementById('confirmationModalTitle');
        const confirmModalBody = document.getElementById('confirmationModalBody');
        const confirmActionBtn = document.getElementById('confirmActionBtn');

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

        deleteBtn.addEventListener('click', function() {
            const deleteUrl = this.dataset.deleteUrl;
            if(confirmModalTitle) confirmModalTitle.textContent = 'Conferma Eliminazione Spesa';
            confirmModalBody.textContent = 'Sei sicuro di voler eliminare questa spesa? L\'importo verrà riaccreditato sulla cassa selezionata.';

            const deleteAction = () => {
                fetch(deleteUrl, { method: 'POST', headers: {'X-CSRFToken': csrftoken} })
                .then(res => res.json()).then(data => {
                    confirmModal.hide();
                    if(data.status === 'ok') {
                        showToast('Spesa eliminata con successo.', 'success');
                        modal.hide();
                        setTimeout(() => window.location.reload(), 500);
                    } else {
                        showToast(data.message || 'Errore durante l\'eliminazione.', 'error');
                    }
                });
            };
            confirmActionBtn.addEventListener('click', deleteAction, { once: true });
            confirmModal.show();
        });
    }

    // Logica per annullare una vendita
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
                    throw new Error('Errore del server.');
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
                showToast(error.message || 'Errore durante lo storno della vendita.', 'error');
            });
        };

        confirmActionBtn.addEventListener('click', reverseAction, { once: true });
        confirmModal.show();
    });
    // --- Logica scroll per header sticky e Back to Top ---
    const stickyHeader = document.getElementById('accountingStickyHeader');
    const backToTopBtn = document.getElementById('backToTop');

    window.addEventListener('scroll', function() {
        if (window.scrollY > 400) {
            if (backToTopBtn) backToTopBtn.style.display = 'flex';
        } else {
            if (backToTopBtn) backToTopBtn.style.display = 'none';
        }
    });

    backToTopBtn?.addEventListener('click', function() {
        window.scrollTo({
            top: 0,
            behavior: 'smooth'
        });
    });
});
