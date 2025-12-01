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
        let initialPaymentMethod = null; // Variabile per tracciare lo stato iniziale

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

                    document.getElementById('saleItemId').textContent = data.item_custom_id ? `#${data.item_custom_id}` : 'N/D';
                    document.getElementById('saleProjectId').textContent = data.project_id ? `#${data.project_id}` : 'N/D';

                    const totalCostEl = document.getElementById('saleTotalCost');
                    if (totalCostEl) {
                        const cost = parseFloat(data.total_cost);
                        totalCostEl.textContent = !isNaN(cost) ? `${cost.toFixed(2)}€` : '0.00€';
                    }

                    form.querySelector('[name="sold_at"]').value = data.sold_at;
                    salePriceInput.value = data.sale_price;

                    // Salviamo il metodo iniziale per capire se era "DA PAGARE" (null o vuoto)
                    initialPaymentMethod = data.payment_method;
                    paymentMethodSelect.value = data.payment_method || '';

                    form.querySelector('[name="sold_to"]').value = data.sold_to;
                    form.querySelector('[name="notes"]').value = data.notes;
                });
        });

        form.addEventListener('submit', function (e) {
            e.preventDefault();

            const originalPriceStr = salePriceInput.value;
            const originalPrice = parseFloat(originalPriceStr.replace(',', '.'));

            const selectedOption = paymentMethodSelect.options[paymentMethodSelect.selectedIndex];
            const methodName = selectedOption ? selectedOption.text.trim().toLowerCase() : '';

            let finalPrice = originalPrice;

            // LOGICA INTELLIGENTE: Applica la commissione SOLO se stiamo passando da "DA PAGARE" a un metodo con commissione.
            // Questo evita di applicare la commissione più volte se si modifica la vendita in futuro.
            const wasUnpaid = !initialPaymentMethod;

            if (!isNaN(originalPrice) && wasUnpaid) {
                if (methodName.indexOf('satispay business') !== -1) {
                    finalPrice = originalPrice * 0.99; // 1%
                } else if (methodName.indexOf('sumup') !== -1 || methodName.indexOf('sum up') !== -1) {
                    finalPrice = originalPrice * 0.9805; // 1.95%
                }
            }

            if (!isNaN(finalPrice) && finalPrice !== originalPrice) {
                 salePriceInput.value = finalPrice.toFixed(2);
            }

            const formData = new FormData(form);
            // Ripristina valore visibile (opzionale, dato che la pagina ricaricherà)
            salePriceInput.value = originalPriceStr;

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
                    alert('Errore durante il salvataggio: ' + (data.message || 'Errore sconosciuto'));
                }
            })
            .catch(err => {
                console.error(err);
                alert('Errore di comunicazione con il server.');
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
