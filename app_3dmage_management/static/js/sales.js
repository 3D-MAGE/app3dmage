document.addEventListener('DOMContentLoaded', function () {
    const editSaleModalEl = document.getElementById('editSaleModal');
    const confirmReverseModalEl = document.getElementById('confirmReverseSaleModal');
    let confirmReverseModal = null;
    if (confirmReverseModalEl) {
        confirmReverseModal = new bootstrap.Modal(confirmReverseModalEl);
    }

    if (editSaleModalEl) {
        const editSaleModal = new bootstrap.Modal(editSaleModalEl);
        const form = editSaleModalEl.querySelector('#editSaleForm');
        const modalTitle = editSaleModalEl.querySelector('#editSaleModalLabel');
        let currentItemId = null;

        editSaleModalEl.addEventListener('show.bs.modal', function (event) {
            const triggerRow = event.relatedTarget;
            currentItemId = triggerRow.dataset.itemId;
            form.action = `/sales/${currentItemId}/edit/`;

            fetch(`/sales/${currentItemId}/details/`)
                .then(res => res.json())
                .then(data => {
                    modalTitle.textContent = `Modifica Vendita: ${data.name}`;
                    document.getElementById('saleProjectId').textContent = `#${data.project_custom_id}` || 'N/D';
                    document.getElementById('saleItemId').textContent = `#${data.id}`;

                    form.querySelector('[name="sold_at"]').value = data.sold_at;
                    form.querySelector('[name="sale_price"]').value = data.sale_price;
                    form.querySelector('[name="payment_method"]').value = data.payment_method;
                    form.querySelector('[name="sold_to"]').value = data.sold_to;
                    form.querySelector('[name="notes"]').value = data.notes;
                });
        });

        form.addEventListener('submit', function (e) {
            e.preventDefault();
            fetch(form.action, {
                method: 'POST',
                body: new FormData(form),
                headers: { 'X-CSRFToken': form.querySelector('[name=csrfmiddlewaretoken]').value }
            })
            .then(res => res.json())
            .then(data => {
                if (data.status === 'ok') {
                    window.location.reload();
                } else {
                    alert('Errore durante il salvataggio');
                }
            });
        });

        document.getElementById('reverseSaleBtn').addEventListener('click', function() {
            if(confirmReverseModal) confirmReverseModal.show();
        });

        document.getElementById('confirmReverseSaleBtn')?.addEventListener('click', function() {
            fetch(`/sale/${currentItemId}/reverse/`, {
                method: 'POST',
                headers: { 'X-CSRFToken': form.querySelector('[name=csrfmiddlewaretoken]').value }
            })
            .then(res => {
                if (res.ok) {
                    window.location.reload();
                } else {
                    alert('Errore durante lo storno della vendita.');
                }
            });
        });
    }
});
