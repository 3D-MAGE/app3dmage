document.addEventListener('DOMContentLoaded', function () {
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
    let currentItemData = null; // Store fetched data

    // --- Gestione Modale per MODIFICARE un oggetto (StockItem) ---
    const editModalEl = document.getElementById('editStockItemModal');
    let editModal = null;
    if (editModalEl) {
        editModal = new bootstrap.Modal(editModalEl);
        const form = editModalEl.querySelector('#editStockItemForm');

        if (form) {
            const statusSelect = form.querySelector('[name="status"]');
            if (statusSelect) {
                // Rimuovi l'opzione "Venduto" dal dropdown se presente (UX richiesta)
                for (let i = 0; i < statusSelect.options.length; i++) {
                    if (statusSelect.options[i].value === 'SOLD') {
                        statusSelect.remove(i);
                        break;
                    }
                }
            } else {
                console.warn("Status select not found in edit form");
            }
        } else {
            console.error("Edit form not found in edit modal");
        }

        // Popola la modale quando viene aperta
        editModalEl.addEventListener('show.bs.modal', function (event) {
            const triggerRow = event.relatedTarget;
            currentItemId = triggerRow.dataset.itemId;
            form.action = `/ajax/stock_item/${currentItemId}/update/`;

            fetch(`/ajax/stock_item/${currentItemId}/details/`)
                .then(res => res.json())
                .then(data => {
                    currentItemData = data; // Save for Sell Modal
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
                });
        });

        // Gestisce l'invio del form di modifica
        form.addEventListener('submit', function (e) {
            e.preventDefault();
            const formData = new FormData(form);

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

        deleteBtn.addEventListener('click', function () {
            itemNameToDelete.textContent = form.querySelector('[name="name"]').value;
            editModal.hide();
            deleteModal.show();
        });

        confirmDeleteBtn.addEventListener('click', function () {
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

    // --- Gestione Modale per VENDERE un oggetto ---
    const sellModalEl = document.getElementById('sellStockItemModal');
    if (sellModalEl && editModalEl) {
        const sellModal = new bootstrap.Modal(sellModalEl);
        const sellForm = sellModalEl.querySelector('#sellStockItemForm');

        // Il bottone nel modale Edit potrebbe essere stato spostato nel DOM, 
        // ma ID dovrebbe essere univoco.
        const openSellBtn = document.getElementById('openSellModalBtn');

        if (openSellBtn) {
            openSellBtn.addEventListener('click', function () {
                if (!currentItemData) return;

                // Chiudi modale edit e apri modale sell
                editModal.hide();
                sellModal.show();

                // Pre-popola form di vendita
                sellForm.action = `/ajax/stock_item/${currentItemId}/update/`; // Usa lo stesso endpoint

                document.getElementById('sell_original_quantity').value = currentItemData.quantity;
                document.getElementById('sell_suggested_price_hidden').value = currentItemData.suggested_price;

                document.getElementById('sell_name').value = currentItemData.name;

                const qtyInput = document.getElementById('sell_quantity');
                qtyInput.max = currentItemData.quantity;
                qtyInput.value = 1;
                document.getElementById('sell_available_qty').textContent = currentItemData.quantity;

                // Imposta data odierna
                document.getElementById('sell_date').valueAsDate = new Date();

                // Prezzo
                document.getElementById('sell_price').value = currentItemData.suggested_price;

                // Reset altri campi
                document.getElementById('sell_sold_to').value = '';
                document.getElementById('sell_notes').value = '';
                // Reset select pagamento (se presente)
                const paySelect = sellForm.querySelector('[name="payment_method"]');
                if (paySelect) paySelect.selectedIndex = 0;
            });
        }

        sellForm.addEventListener('submit', function (e) {
            e.preventDefault();

            // Logica commissioni frontend (Satispay/SumUp)
            const priceInput = document.getElementById('sell_price');
            const originalPriceStr = priceInput.value;
            const originalPrice = parseFloat(originalPriceStr.replace(',', '.'));

            const paySelect = sellForm.querySelector('[name="payment_method"]');
            let finalPrice = originalPrice;

            if (paySelect && !isNaN(originalPrice)) {
                const selectedOption = paySelect.options[paySelect.selectedIndex];
                const methodName = selectedOption ? selectedOption.text.trim().toLowerCase() : '';

                if (methodName.indexOf('satispay business') !== -1) {
                    finalPrice = originalPrice * 0.99;
                }
                else if (methodName.indexOf('sumup') !== -1 || methodName.indexOf('sum up') !== -1) {
                    finalPrice = originalPrice * 0.9805;
                }
            }

            if (!isNaN(finalPrice) && finalPrice !== originalPrice) {
                priceInput.value = finalPrice.toFixed(2);
            }

            const formData = new FormData(sellForm);
            priceInput.value = originalPriceStr; // Ripristina per UX

            fetch(sellForm.action, {
                method: 'POST',
                body: formData,
                headers: { 'X-CSRFToken': csrftoken }
            })
                .then(res => {
                    if (!res.ok) return res.json().then(err => Promise.reject(err));
                    return res.json();
                })
                .then(data => {
                    sellModal.hide();
                    if (data.status === 'ok') {
                        showToast(data.message, 'success');
                        setTimeout(() => window.location.reload(), 1200);
                    } else {
                        const errorMsg = data.message || (data.errors ? Object.values(JSON.parse(data.errors)).join(' ') : 'Errore vendita');
                        showToast(errorMsg, 'error');
                    }
                })
                .catch(error => {
                    console.error('Fetch Error:', error);
                    showToast(error.message || 'Errore comunicazione server', 'error');
                });
        });
    }

    // Aggiunta manuale oggetto
    const addModalEl = document.getElementById('addStockItemModal');
    if (addModalEl) {
        const addForm = addModalEl.querySelector('#addStockItemForm');
        addForm.addEventListener('submit', function (e) {
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
