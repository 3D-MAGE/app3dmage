document.addEventListener('DOMContentLoaded', function() {
    const csrftoken = getCookie('csrftoken');

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

    // Logica popup Modifica/Elimina Spesa
    const editExpenseModalEl = document.getElementById('editExpenseModal');
    if (editExpenseModalEl) {
        const modal = new bootstrap.Modal(editExpenseModalEl);
        const form = editExpenseModalEl.querySelector('form');
        const deleteBtn = document.getElementById('deleteExpenseBtn');

        document.getElementById('expenses-table')?.addEventListener('click', function(e) {
            const row = e.target.closest('tr.clickable-row');
            if (row) {
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
                if(data.status === 'ok') { window.location.reload(); }
                else { showToast('Errore durante la modifica.', 'error'); }
            });
        });

        deleteBtn.addEventListener('click', function() {
            if (confirm('Sei sicuro di voler eliminare questa spesa? L\'importo verrà riaccreditato sulla cassa selezionata.')) {
                fetch(this.dataset.deleteUrl, { method: 'POST', headers: {'X-CSRFToken': csrftoken} })
                .then(res => res.json()).then(data => {
                    if(data.status === 'ok') { window.location.reload(); }
                    else { showToast(data.message || 'Errore.', 'error'); }
                });
            }
        });
    }

    // Logica per annullare una vendita
    document.getElementById('income-table')?.addEventListener('click', function(e) {
        const row = e.target.closest('tr.clickable-row');
        if (!row || e.target.closest('button')) return;

        const confirmModalEl = document.getElementById('confirmationModal');
        const confirmModal = new bootstrap.Modal(confirmModalEl);

        document.getElementById('confirmationModalBody').textContent = `Sei sicuro di voler annullare la vendita per "${row.dataset.name}"? L'importo verrà stornato e l'oggetto tornerà disponibile in magazzino.`;

        document.getElementById('confirmActionBtn').onclick = function() {
            const form = document.createElement('form');
            form.method = 'post';
            form.action = `/sale/${row.dataset.id}/reverse/`;
            form.innerHTML = `{% csrf_token %}`;
            document.body.appendChild(form);
            form.submit();
        };
        confirmModal.show();
    });
});
