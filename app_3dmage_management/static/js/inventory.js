// Utility globale per il calcolo del prezzo netto (commissioni)
window.calculateNetPrice = function (grossPrice, methodName) {
    if (isNaN(grossPrice)) return grossPrice;
    
    const method = methodName.toLowerCase();
    if (method.includes('satispay business')) {
        return Math.round(grossPrice * 0.99 * 100) / 100; // 1% fee
    } else if (method.includes('sumup') || method.includes('sum up')) {
        return Math.round(grossPrice * 0.9805 * 100) / 100; // 1.95% fee
    }
    return grossPrice;
};

document.addEventListener('DOMContentLoaded', function () {
    const editModalEl = document.getElementById('editStockItemModal');
    const sellModalEl = document.getElementById('sellStockItemModal');
    const sellForm = document.getElementById('sellStockItemForm');
    
    // Inizializzazione modali Bootstrap
    let editModal = null;
    let sellModal = null;
    if (editModalEl) editModal = new bootstrap.Modal(editModalEl);
    if (sellModalEl) sellModal = new bootstrap.Modal(sellModalEl);

    let currentItemData = null;

    if (editModalEl) {
        // Caricamento dati nel modale di modifica
        editModalEl.addEventListener('show.bs.modal', function (event) {
            const button = event.relatedTarget;
            const itemId = button.getAttribute('data-item-id');
            const form = document.getElementById('editStockItemForm');
            form.action = `/ajax/stock_item/${itemId}/update/`;

            fetch(`/ajax/stock_item/${itemId}/details/`)
                .then(response => response.json())
                .then(data => {
                    currentItemData = data;
                    document.getElementById('editStockItemModalLabel').textContent = `Modifica: ${data.name}`;
                    document.getElementById('itemProjectName').textContent = data.project_name || 'N/A';
                    document.getElementById('itemProjectID').textContent = data.project_custom_id ? `#${data.project_custom_id}` : '';
                    
                    form.querySelector('[name="name"]').value = data.name;
                    form.querySelector('[name="quantity"]').value = data.quantity;
                    form.querySelector('[name="suggested_price"]').value = data.suggested_price;
                    form.querySelector('[name="status"]').value = data.status;
                    
                    document.getElementById('itemMaterialCost').textContent = `${parseFloat(data.production_cost_per_unit).toFixed(2)}€`;
                    document.getElementById('itemLaborCost').textContent = `${parseFloat(data.labor_cost_unit_per_unit || data.labor_cost_per_unit).toFixed(2)}€`;

                    // Gestione note progetto (se presenti)
                    const notesWrapper = document.getElementById('project-notes-wrapper');
                    const notesTextarea = document.getElementById('id_project_notes');
                    if (data.project_notes) {
                        notesWrapper.style.display = 'block';
                        notesTextarea.value = data.project_notes;
                        notesTextarea.readOnly = true;
                    } else {
                        notesWrapper.style.display = 'none';
                    }
                });
        });

        // Apertura modale vendita
        document.getElementById('openSellModalBtn').addEventListener('click', function () {
            if (currentItemData) {
                editModal.hide();
                sellModal.show();
                
                // Popola i campi del modale vendita
                document.getElementById('sell_original_quantity').value = currentItemData.quantity;
                document.getElementById('sell_suggested_price_hidden').value = currentItemData.suggested_price;
                document.getElementById('sell_name').value = currentItemData.name;

                const qtyInput = document.getElementById('sell_quantity');
                qtyInput.max = currentItemData.quantity;
                qtyInput.value = 1;
                document.getElementById('sell_available_qty').textContent = currentItemData.quantity;

                document.getElementById('sell_date').valueAsDate = new Date();
                const priceInput = document.getElementById('sell_price');
                priceInput.value = currentItemData.suggested_price;

                document.getElementById('sell_sold_to').value = '';
                document.getElementById('sell_notes').value = '';
                
                const paySelect = sellForm.querySelector('[name="payment_method"]');
                if (paySelect) paySelect.selectedIndex = 0;

                // Aggiorna anteprima netto subito
                updateNetPreview();
            }
        });

        // Gestione eliminazione
        const deleteBtn = document.getElementById('deleteStockItemBtn');
        const confirmDeleteModal = new bootstrap.Modal(document.getElementById('confirmDeleteModal'));
        deleteBtn.addEventListener('click', function () {
            if (currentItemData) {
                document.getElementById('itemNameToDelete').textContent = currentItemData.name;
                editModal.hide();
                confirmDeleteModal.show();
            }
        });

        document.getElementById('confirmDeleteBtn').addEventListener('click', function () {
            fetch(`/ajax/stock_item/${currentItemData.id}/delete/`, {
                method: 'POST',
                headers: { 'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value }
            })
            .then(res => res.json())
            .then(data => {
                if (data.status === 'ok') window.location.reload();
            });
        });
    }

    // --- LOGICA VENDITA ---

    function updateNetPreview() {
        const priceInput = document.getElementById('sell_price');
        const previewDiv = document.getElementById('sell_net_preview');
        const paySelect = sellForm.querySelector('[name="payment_method"]');
        
        if (!priceInput || !previewDiv || !paySelect) return;

        const grossPrice = parseFloat(priceInput.value.replace(',', '.'));
        const selectedOption = paySelect.options[paySelect.selectedIndex];
        const methodName = selectedOption ? selectedOption.text.trim() : '';

        if (isNaN(grossPrice)) {
            previewDiv.textContent = '';
            return;
        }

        const netPrice = window.calculateNetPrice(grossPrice, methodName);
        if (netPrice !== grossPrice) {
            previewDiv.textContent = `Netto ricevuto: ${netPrice.toFixed(2)}€ (dopo commissioni)`;
        } else {
            previewDiv.textContent = 'Nessuna commissione applicata';
        }
    }

    if (sellForm) {
        const priceInput = document.getElementById('sell_price');
        const paySelect = sellForm.querySelector('[name="payment_method"]');

        priceInput.addEventListener('input', updateNetPreview);
        paySelect.addEventListener('change', updateNetPreview);

        sellForm.addEventListener('submit', function (e) {
            e.preventDefault();
            
            // Il backend ora si aspetta il prezzo LORDO e calcola lui il netto per il saldo.
            // Quindi inviamo i dati così come sono nel form.
            const formData = new FormData(sellForm);
            const itemId = currentItemData.id;

            fetch(`/ajax/stock_item/${itemId}/update/`, {
                method: 'POST',
                body: formData,
                headers: { 'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value }
            })
            .then(res => res.json())
            .then(data => {
                if (data.status === 'ok') {
                    window.location.reload();
                } else {
                    alert(data.message || 'Errore durante la vendita');
                }
            })
            .catch(err => {
                console.error(err);
                alert('Errore di comunicazione con il server.');
            });
        });
    }
});
