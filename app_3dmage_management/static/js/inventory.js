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
    let currentItemId = null; // Variabile accessibile a tutto lo script

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

        const toggleSaleSection = () => {
            if (statusSelect.value === 'SOLD') {
                saleDetailsSection.classList.remove('d-none');
                if (suggestedPriceInput.value) {
                    salePriceInput.value = suggestedPriceInput.value;
                }
            } else {
                saleDetailsSection.classList.add('d-none');
            }
        };

        editModalEl.addEventListener('show.bs.modal', function(event) {
            const triggerRow = event.relatedTarget;
            currentItemId = triggerRow.dataset.itemId; // Imposta l'ID corrente
            form.action = `/ajax/stock_item/${currentItemId}/update/`;

            fetch(`/ajax/stock_item/${currentItemId}/details/`)
                .then(res => res.json())
                .then(data => {
                    modalTitle.textContent = `Gestisci: ${data.name}`;
                    form.querySelector('[name="name"]').value = data.name;
                    form.querySelector('[name="quantity"]').value = data.quantity;
                    form.querySelector('[name="suggested_price"]').value = data.suggested_price;
                    form.querySelector('[name="status"]').value = data.status;

                    document.getElementById('itemProjectName').textContent = data.project_name || 'N/A';
                    document.getElementById('itemProjectID').textContent = data.project_id ? `(#${data.project_id})` : '';

                    quantityToSellInput.max = data.quantity;
                    quantityToSellInput.value = data.quantity;

                    toggleSaleSection();
                });
        });

        statusSelect.addEventListener('change', toggleSaleSection);

        form.addEventListener('submit', function(e) {
            e.preventDefault();
            fetch(form.action, {
                method: 'POST',
                body: new FormData(form),
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
                    const errorMsg = data.message || Object.values(data.errors).join(' ');
                    showToast(errorMsg, 'error');
                }
            })
            .catch(error => {
                console.error('Fetch Error:', error);
                const errorMsg = error.message || (error.errors ? Object.values(error.errors).join(' ') : 'Si è verificato un errore di comunicazione con il server.');
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
                     const errorMsg = data.message || Object.values(data.errors).join(' ');
                     showToast(errorMsg, 'error');
                }
            })
            .catch(error => {
                console.error('Fetch Error:', error);
                const errorMsg = error.message || (error.errors ? Object.values(error.errors).join(' ') : 'Si è verificato un errore di comunicazione con il server.');
                showToast(errorMsg, 'error');
            });
        });
    }
});
