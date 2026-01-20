// --- STATO GLOBALE ---
let currentItemData = null;
let editModal = null;
let sellModal = null;
let confirmDeleteModal = null;
let isTransitioning = false;

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

// --- INIZIALIZZAZIONE STATICA (UNA SOLA VOLTA) ---
function initStaticModules() {
    const editModalEl = document.getElementById('editStockItemModal');
    const sellModalEl = document.getElementById('sellStockItemModal');
    const confirmDeleteModalEl = document.getElementById('confirmDeleteModal');
    
    if (editModalEl) editModal = new bootstrap.Modal(editModalEl);
    if (sellModalEl) sellModal = new bootstrap.Modal(sellModalEl);
    if (confirmDeleteModalEl) confirmDeleteModal = new bootstrap.Modal(confirmDeleteModalEl);

    // Listener chiusura modale modifica (rilascio lock)
    if (editModalEl) {
        editModalEl.addEventListener('hidden.bs.modal', async function() {
            if (currentItemData && !isTransitioning) {
                await releaseLock('stock_item', currentItemData.id);
                // Trigger refresh immediato per sbloccare visivamente l'oggetto
                htmx.trigger('body', 'refreshInventory');
            }
        });
    }

    // Apertura modale vendita dal modale di modifica
    const openSellBtn = document.getElementById('openSellModalBtn');
    if (openSellBtn) {
        openSellBtn.addEventListener('click', function () {
            if (currentItemData) {
                // Nascondiamo il modale di modifica senza rilasciare il lock
                isTransitioning = true;
                editModal.hide();
                sellModal.show();
                
                // Reset della flag dopo un breve delay per permettere all'evento hidden di scattare
                setTimeout(() => { isTransitioning = false; }, 500);
                
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
                
                const sellForm = document.getElementById('sellStockItemForm');
                const paySelect = sellForm.querySelector('[name="payment_method"]');
                if (paySelect) paySelect.selectedIndex = 0;

                updateNetPreview();
            }
        });
    }

    // Gestione eliminazione (apertura conferma)
    const deleteBtn = document.getElementById('deleteStockItemBtn');
    if (deleteBtn) {
        deleteBtn.addEventListener('click', function () {
            if (currentItemData) {
                document.getElementById('itemNameToDelete').textContent = currentItemData.name;
                isTransitioning = true;
                editModal.hide();
                confirmDeleteModal.show();
                setTimeout(() => { isTransitioning = false; }, 500);
            }
        });
    }

    // Conferma eliminazione effettiva
    const confirmDelBtn = document.getElementById('confirmDeleteBtn');
    if (confirmDelBtn) {
        confirmDelBtn.addEventListener('click', function () {
            if (!currentItemData) return;
            fetch(`/ajax/stock_item/${currentItemData.id}/delete/`, {
                method: 'POST',
                headers: { 'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value }
            })
            .then(res => res.json())
            .then(data => {
                if (data.status === 'ok') window.location.reload();
                else alert(data.message || 'Errore durante l\'eliminazione');
            });
        });
    }

    // Salvataggio Modifiche (Form Modifica)
    const editForm = document.getElementById('editStockItemForm');
    if (editForm) {
        editForm.addEventListener('submit', function (e) {
            e.preventDefault();
            const formData = new FormData(editForm);
            const actionUrl = editForm.action;

            fetch(actionUrl, {
                method: 'POST',
                body: formData,
                headers: { 'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value }
            })
            .then(res => res.json())
            .then(data => {
                if (data.status === 'ok') {
                    window.location.reload();
                } else {
                    alert(data.message || 'Errore durante l\'aggiornamento');
                }
            })
            .catch(err => {
                console.error(err);
                alert('Errore di comunicazione con il server.');
            });
        });
    }

    // Salvataggio Vendita (Form Vendita)
    const sellForm = document.getElementById('sellStockItemForm');
    if (sellForm) {
        const priceInput = document.getElementById('sell_price');
        const paySelect = sellForm.querySelector('[name="payment_method"]');
        
        if (priceInput) priceInput.addEventListener('input', updateNetPreview);
        if (paySelect) paySelect.addEventListener('change', updateNetPreview);

        sellForm.addEventListener('submit', function (e) {
            e.preventDefault();
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
            });
        });
    }

    // Anche per il Sell Modal e Confirm Delete Modal vogliamo rilasciare il lock se chiusi direttamente
    if (sellModalEl) {
        sellModalEl.addEventListener('hidden.bs.modal', async function() {
            if (currentItemData && !isTransitioning) {
                await releaseLock('stock_item', currentItemData.id);
                htmx.trigger('body', 'refreshInventory');
            }
        });
    }
    if (confirmDeleteModalEl) {
        confirmDeleteModalEl.addEventListener('hidden.bs.modal', async function() {
            if (currentItemData && !isTransitioning) {
                await releaseLock('stock_item', currentItemData.id);
                htmx.trigger('body', 'refreshInventory');
            }
        });
    }
}

function updateNetPreview() {
    const priceInput = document.getElementById('sell_price');
    const previewDiv = document.getElementById('sell_net_preview');
    const sellForm = document.getElementById('sellStockItemForm');
    if (!sellForm) return;
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

// --- INIZIALIZZAZIONE DINAMICA (TABELLA HTMX) ---
function initInventoryBoard() {
    // Gestione click sulle righe della tabella (delegation o ri-aggancio)
    // Dato che HTMX ricarica il body, ri-agganciamo i listener alle nuove righe.
    document.querySelectorAll('#inventory-table-body tr[data-item-id]').forEach(row => {
        row.removeAttribute('data-bs-toggle');
        row.removeAttribute('data-bs-target');
        
        row.addEventListener('click', async function() {
            const itemId = this.dataset.itemId;
            
            // 1. Tenta di acquisire il LOCK
            const hasLock = await acquireLock('stock_item', itemId);
            if (!hasLock) return;

            // 2. Se ho il lock, inizio heartbeat
            startLockHeartbeat('stock_item', itemId);

            // 3. Carico i dati
            loadItemData(itemId);
        });
    });
}

function loadItemData(itemId) {
    const form = document.getElementById('editStockItemForm');
    if (!form) return;
    form.action = `/ajax/stock_item/${itemId}/update/`;

    fetch(`/ajax/stock_item/${itemId}/details/`)
        .then(response => response.json())
        .then(data => {
            currentItemData = data;
            document.getElementById('editStockItemModalLabel').textContent = `Modifica: ${data.name}`;
            document.getElementById('itemProjectName').textContent = data.project_name || 'N/A';
            document.getElementById('itemProjectID').textContent = data.project_id || 'N/A';
            document.getElementById('itemStockID').textContent = data.custom_id ? `#${data.custom_id}` : 'N/A';
            
            form.querySelector('[name="name"]').value = data.name;
            form.querySelector('[name="quantity"]').value = data.quantity;
            form.querySelector('[name="suggested_price"]').value = data.suggested_price;
            form.querySelector('[name="status"]').value = data.status;
            
            document.getElementById('itemMaterialCost').textContent = `${parseFloat(data.production_cost_per_unit).toFixed(2)}€`;
            document.getElementById('itemLaborCost').textContent = `${parseFloat(data.labor_cost_unit_per_unit || data.labor_cost_per_unit).toFixed(2)}€`;

            const notesWrapper = document.getElementById('work-order-notes-wrapper');
            const notesTextarea = document.getElementById('id_work_order_notes');
            if (data.work_order_notes) {
                notesWrapper.style.display = 'block';
                notesTextarea.value = data.work_order_notes;
                notesTextarea.readOnly = true;
            } else {
                notesWrapper.style.display = 'none';
            }

            if (editModal) editModal.show();
        });
}

// --- EVENTI D'AVVIO ---
document.addEventListener('DOMContentLoaded', () => {
    initStaticModules();
    initInventoryBoard();
});

document.addEventListener('htmx:afterSettle', function(evt) {
    if (evt.detail.target.id === 'inventory-table-container') {
        initInventoryBoard();
    }
});
