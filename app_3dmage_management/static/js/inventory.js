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
    let currentItemId = null; // Variabile per l'ID dell'oggetto corrente, accessibile globalmente

    // --- Gestione Modale per MODIFICARE/VENDERE un oggetto ---
    const editModalEl = document.getElementById('editStockItemModal');
    if (editModalEl) {
        const editModal = new bootstrap.Modal(editModalEl);
        const form = editModalEl.querySelector('#editStockItemForm');
        const modalTitle = editModalEl.querySelector('#editStockItemModalLabel');
        const statusSelect = form.querySelector('[name="status"]');
        const saleDetailsSection = form.querySelector('#sale-details-section');
        const salePriceInput = form.querySelector('[name="sale_price"]');
        const suggestedPriceInput = form.querySelector('[name="suggested_price"]');
        const quantityToSellInput = form.querySelector('[name="quantity_to_sell"]');
        const paymentMethodSelect = form.querySelector('[name="payment_method"]');
        // MODIFIED: Reference to the sale date field
        const soldAtInput = form.querySelector('[name="sold_at"]');

        // Mostra o nasconde la sezione di vendita in base allo stato
        const toggleSaleSection = () => {
            if (statusSelect.value === 'SOLD') {
                saleDetailsSection.classList.remove('d-none');
                // Imposta il prezzo di vendita uguale a quello suggerito quando la sezione appare
                if (!salePriceInput.value) {
                    salePriceInput.value = suggestedPriceInput.value;
                }
                // MODIFIED: Default sale date to today if not already set
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
                    modalTitle.textContent = `Gestisci: ${data.name}`;
                    form.querySelector('[name="name"]').value = data.name;
                    form.querySelector('[name="quantity"]').value = data.quantity;
                    form.querySelector('[name="suggested_price"]').value = data.suggested_price;
                    form.querySelector('[name="status"]').value = data.status;

                    // NEW: Populate material cost
                    const materialCostEl = document.getElementById('itemMaterialCost');
                    if (materialCostEl) {
                        materialCostEl.textContent = `${parseFloat(data.material_cost_per_unit).toFixed(2)}€`;
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

        // Aggiunge l'event listener per il cambio di stato
        statusSelect.addEventListener('change', toggleSaleSection);

        // Gestisce l'invio del form di modifica/vendita
        form.addEventListener('submit', function(e) {
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
                    const errorMsg = data.message || Object.values(JSON.parse(data.errors)).join(' ');
                    showToast(errorMsg, 'error');
                }
            })
            .catch(error => {
                console.error('Fetch Error:', error);
                const errorMsg = error.message || (error.errors ? Object.values(JSON.parse(error.errors)).join(' ') : 'Si è verificato un errore di comunicazione con il server.');
                showToast(errorMsg, 'error');
            });
        });

        // --- Gestione Eliminazione Oggetto ---
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

    // --- Gestione Modale per AGGIUNGERE un oggetto manualmente ---
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
                     const errorMsg = data.message || Object.values(JSON.parse(data.errors)).join(' ');
                     showToast(errorMsg, 'error');
                }
            })
            .catch(error => {
                console.error('Fetch Error:', error);
                const errorMsg = error.message || (error.errors ? Object.values(JSON.parse(error.errors)).join(' ') : 'Si è verificato un errore di comunicazione con il server.');
                showToast(errorMsg, 'error');
            });
        });
    }
});
