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

        const salePriceInput = form.querySelector('[name="sale_price"]');
        const paymentMethodSelect = form.querySelector('[name="payment_method"]');

        editSaleModalEl.addEventListener('show.bs.modal', function (event) {
            const triggerRow = event.relatedTarget;
            currentItemId = triggerRow.dataset.itemId;
            form.action = `/sales/${currentItemId}/edit/`;

            fetch(`/sales/${currentItemId}/details/`)
                .then(res => res.json())
                .then(data => {
                    modalTitle.textContent = `Modifica Vendita: ${data.name}`;

                    // CORREZIONE BUG 2: Popola gli ID con i dati corretti dalla view
                    document.getElementById('saleItemId').textContent = data.item_custom_id ? `#${data.item_custom_id}` : 'N/D';
                    document.getElementById('saleProjectId').textContent = data.project_id ? `#${data.project_id}` : 'N/D';

                    // CORREZIONE BUG 3: Popola il costo totale con il dato corretto dalla view
                    const totalCostEl = document.getElementById('saleTotalCost');
                    if (totalCostEl) {
                        const cost = parseFloat(data.total_cost);
                        totalCostEl.textContent = !isNaN(cost) ? `${cost.toFixed(2)}€` : '0.00€';
                    }

                    form.querySelector('[name="sold_at"]').value = data.sold_at;
                    salePriceInput.value = data.sale_price;
                    paymentMethodSelect.value = data.payment_method || '';
                    form.querySelector('[name="sold_to"]').value = data.sold_to;
                    form.querySelector('[name="notes"]').value = data.notes;
                });
        });

        form.addEventListener('submit', function (e) {
            e.preventDefault();

            const originalPrice = salePriceInput.value;
            const selectedOption = paymentMethodSelect.options[paymentMethodSelect.selectedIndex];
            const isSatispayBusiness = selectedOption && selectedOption.text.toLowerCase().includes('satispay business');

            if (isSatispayBusiness) {
                const discountedPrice = parseFloat(originalPrice) * 0.98;
                salePriceInput.value = discountedPrice.toFixed(2);
            }

            const formData = new FormData(form);
            salePriceInput.value = originalPrice;

            fetch(form.action, {
                method: 'POST',
                body: formData,
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
            const csrfToken = form.querySelector('[name=csrfmiddlewaretoken]').value;
            fetch(`/sale/${currentItemId}/reverse/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrfToken,
                    'Content-Type': 'application/json'
                 }
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
