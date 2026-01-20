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

        // Crea dinamicamente il preview del netto se non esiste
        let previewDiv = document.getElementById('sale_net_preview');
        if (!previewDiv && salePriceInput) {
            previewDiv = document.createElement('div');
            previewDiv.id = 'sale_net_preview';
            previewDiv.className = 'form-text text-info fw-bold mt-1';
            salePriceInput.parentNode.appendChild(previewDiv);
        }

        function updateNetPreview() {
            if (!salePriceInput || !previewDiv || !paymentMethodSelect) return;

            const grossPrice = parseFloat(salePriceInput.value.replace(',', '.'));
            const selectedOption = paymentMethodSelect.options[paymentMethodSelect.selectedIndex];
            const methodName = selectedOption ? selectedOption.text.trim() : '';

            if (isNaN(grossPrice)) {
                previewDiv.textContent = '';
                return;
            }

            if (typeof window.calculateNetPrice === 'function') {
                const netPrice = window.calculateNetPrice(grossPrice, methodName);
                if (netPrice !== grossPrice) {
                    previewDiv.textContent = `Netto ricevuto: ${netPrice.toFixed(2)}€ (dopo commissioni)`;
                } else {
                    previewDiv.textContent = 'Nessuna commissione applicata';
                }
            }
        }

        if (salePriceInput) salePriceInput.addEventListener('input', updateNetPreview);
        if (paymentMethodSelect) paymentMethodSelect.addEventListener('change', updateNetPreview);

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
                    paymentMethodSelect.value = data.payment_method || '';

                    form.querySelector('[name="sold_to"]').value = data.sold_to;
                    form.querySelector('[name="notes"]').value = data.notes;

                    // Aggiorna anteprima netto
                    updateNetPreview();
                });
        });

        form.addEventListener('submit', function (e) {
            e.preventDefault();

            // Il backend ora gestisce tutto basandosi sul prezzo lordo inviato.
            const formData = new FormData(form);

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
