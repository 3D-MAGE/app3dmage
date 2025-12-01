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
    let currentItemId = null;

    // --- Gestione Modale per MODIFICARE/VENDERE un oggetto ---
    const editModalEl = document.getElementById('editStockItemModal');
    if (editModalEl) {
        const editModal = new bootstrap.Modal(editModalEl);
        const form = editModalEl.querySelector('#editStockItemForm');
        const statusSelect = form.querySelector('[name="status"]');
        const saleDetailsSection = form.querySelector('#sale-details-section');
        const salePriceInput = form.querySelector('[name="sale_price"]');
        const suggestedPriceInput = form.querySelector('[name="suggested_price"]');
        const quantityToSellInput = form.querySelector('[name="quantity_to_sell"]');
        const paymentMethodSelect = form.querySelector('[name="payment_method"]');
        const soldAtInput = form.querySelector('[name="sold_at"]');

        // Mostra o nasconde la sezione di vendita in base allo stato
        const toggleSaleSection = () => {
            if (statusSelect.value === 'SOLD') {
                saleDetailsSection.classList.remove('d-none');
                if (!salePriceInput.value) {
                    salePriceInput.value = suggestedPriceInput.value;
                }
                if (!soldAtInput.value) {
                    soldAtInput.valueAsDate = new Date();
                }
            } else {
                saleDetailsSection.classList.add('d-none');
            }
        };

        // Popola la modale quando viene aperta
        editModalEl.addEventListener('show.bs.modal', function(event) {
            const triggerRow = event.relatedTarget;
            currentItemId = triggerRow.dataset.itemId;
            form.action = `/ajax/stock_item/${currentItemId}/update/`;

            fetch(`/ajax/stock_item/${currentItemId}/details/`)
                .then(res => res.json())
                .then(data => {
                    const modalTitle = editModalEl.querySelector('#editStockItemModalLabel');
                    modalTitle.textContent = `Gestisci: ${data.name} (#${data.custom_id})`;
                    form.querySelector('[name="name"]').value = data.name;
                    form.querySelector('[name="quantity"]').value = data.quantity;
                    form.querySelector('[name="suggested_price"]').value = data.suggested_price;
                    form.querySelector('[name="status"]').value = data.status;

                    const materialCostEl = document.getElementById('itemMaterialCost');
                    const laborCostEl = document.getElementById('itemLaborCost');

                    if (materialCostEl) {
                        materialCostEl.textContent = `${parseFloat(data.production_cost_per_unit).toFixed(2)}€`;
                    }
                    if (laborCostEl) {
                        laborCostEl.textContent = `${parseFloat(data.labor_cost_per_unit).toFixed(2)}€`;
                    }

                    document.getElementById('itemProjectName').textContent = data.project_name || 'N/A';
                    document.getElementById('itemProjectID').textContent = data.project_id ? `(#${data.project_id})` : '';

                    const notesWrapper = document.getElementById('project-notes-wrapper');
                    const notesTextarea = document.getElementById('id_project_notes');
                    if (data.project_id) {
                        notesTextarea.value = data.project_notes || '';
                        notesWrapper.style.display = 'block';
                    } else {
                        notesWrapper.style.display = 'none';
                    }

                    quantityToSellInput.max = data.quantity;
                    quantityToSellInput.value = data.quantity;

                    toggleSaleSection();
                });
        });

        statusSelect.addEventListener('change', toggleSaleSection);

        // Gestisce l'invio del form di modifica/vendita
        form.addEventListener('submit', function(e) {
            e.preventDefault();

            const originalPriceStr = salePriceInput.value;
            // Gestione virgola -> punto per i calcoli JS
            const originalPrice = parseFloat(originalPriceStr.replace(',', '.'));

            const selectedOption = paymentMethodSelect.options[paymentMethodSelect.selectedIndex];
            const methodName = selectedOption ? selectedOption.text.trim().toLowerCase() : '';

            let finalPrice = originalPrice;

            // LOGICA COMMISSIONI
            if (!isNaN(originalPrice) && statusSelect.value === 'SOLD') {
                // Satispay Business: ora 1% (era 2%)
                if (methodName.indexOf('satispay business') !== -1) {
                    finalPrice = originalPrice * 0.99;
                }
                // SumUp: 1.95%
                else if (methodName.indexOf('sumup') !== -1 || methodName.indexOf('sum up') !== -1) {
                    finalPrice = originalPrice * 0.9805;
                }
            }

            // AGGIORNA L'INPUT PRIMA DI CREARE IL FORMDATA
            if (!isNaN(finalPrice) && finalPrice !== originalPrice) {
                 salePriceInput.value = finalPrice.toFixed(2);
            }

            const formData = new FormData(form);

            // Ripristina il valore originale nell'input per l'utente (UX)
            salePriceInput.value = originalPriceStr;

            fetch(form.action, {
                method: 'POST',
                body: formData,
                headers: { 'X-CSRFToken': csrftoken }
            })
            .then(res => {
                if (!res.ok) return res.json().then(err => Promise.reject(err));
                return res.json();
            })
            .then(data => {
                editModal.hide();
                if (data.status === 'ok') {
                    showToast(data.message, 'success');
                    setTimeout(() => window.location.reload(), 1200);
                } else {
                    const errorMsg = data.message || (data.errors ? Object.values(JSON.parse(data.errors)).join(' ') : 'Errore sconosciuto');
                    showToast(errorMsg, 'error');
                }
            })
            .catch(error => {
                console.error('Fetch Error:', error);
                const errorMsg = error.message || 'Si è verificato un errore di comunicazione con il server.';
                showToast(errorMsg, 'error');
            });
        });

        // Gestione eliminazione
        const deleteModalEl = document.getElementById('confirmDeleteModal');
        const deleteModal = new bootstrap.Modal(deleteModalEl);
        const deleteBtn = editModalEl.querySelector('#deleteStockItemBtn');
        const confirmDeleteBtn = deleteModalEl.querySelector('#confirmDeleteBtn');
        const itemNameToDelete = deleteModalEl.querySelector('#itemNameToDelete');

        deleteBtn.addEventListener('click', function() {
            itemNameToDelete.textContent = form.querySelector('[name="name"]').value;
            editModal.hide();
            deleteModal.show();
        });

        confirmDeleteBtn.addEventListener('click', function() {
            fetch(`/ajax/stock_item/${currentItemId}/delete/`, {
                method: 'POST',
                headers: { 'X-CSRFToken': csrftoken }
            })
            .then(res => res.json())
            .then(data => {
                deleteModal.hide();
                if (data.status === 'ok') {
                    showToast(data.message, 'success');
                    setTimeout(() => window.location.reload(), 1200);
                } else {
                    showToast(data.message, 'error');
                }
            })
            .catch(error => {
                deleteModal.hide();
                showToast('Errore durante l\'eliminazione.', 'error');
            });
        });
    }

    // Aggiunta manuale oggetto
    const addModalEl = document.getElementById('addStockItemModal');
    if (addModalEl) {
        const addForm = addModalEl.querySelector('#addStockItemForm');
        addForm.addEventListener('submit', function(e) {
            e.preventDefault();
            fetch(addForm.action, {
                method: 'POST',
                body: new FormData(addForm),
                headers: { 'X-CSRFToken': csrftoken }
            })
            .then(res => {
                if (!res.ok) return res.json().then(err => Promise.reject(err));
                return res.json();
            })
            .then(data => {
                const addModal = bootstrap.Modal.getInstance(addModalEl);
                addModal.hide();
                if (data.status === 'ok') {
                    showToast('Oggetto aggiunto manualmente con successo!', 'success');
                    setTimeout(() => window.location.reload(), 1200);
                } else {
                     const errorMsg = data.message || (data.errors ? Object.values(JSON.parse(data.errors)).join(' ') : 'Errore');
                     showToast(errorMsg, 'error');
                }
            })
            .catch(error => {
                console.error('Fetch Error:', error);
                showToast(error.message || 'Errore comunicazione server', 'error');
            });
        });
    }
});
