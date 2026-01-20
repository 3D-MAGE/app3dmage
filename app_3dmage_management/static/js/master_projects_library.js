document.addEventListener('DOMContentLoaded', function() {
    const createModal = document.getElementById('createOrderModal');
    if (createModal) {
        createModal.addEventListener('show.bs.modal', function(event) {
            const button = event.relatedTarget;
            const projectId = button.getAttribute('data-project-id');
            const projectName = button.getAttribute('data-project-name');
            const baseQty = button.getAttribute('data-base-qty');
            
            const form = document.getElementById('createOrderForm');
            const text = document.getElementById('createOrderText');
            const qtyInput = document.getElementById('createOrderQuantity');
            
            form.action = `/library/${projectId}/create_order/`;
            text.innerHTML = `Stai creando un ordine per <strong>${projectName}</strong>.`;
            qtyInput.value = baseQty || 1;
        });
    }
    // -----------------------------------------------------------------
    // GESTIONE OUTPUT NEL NUOVO MASTER
    // -----------------------------------------------------------------
    const addOutputBtn = document.getElementById('add-output-btn-new');
    const outputsContainer = document.getElementById('outputs-container-new');

    if (addOutputBtn && outputsContainer) {
        addOutputBtn.addEventListener('click', function() {
            const newRow = document.createElement('div');
            newRow.className = 'row g-2 mb-2 output-row';
            newRow.innerHTML = `
                <div class="col-8">
                    <input type="text" name="output_names[]" class="form-control bg-dark text-white" placeholder="Nome Output (es. Bambola RUMI)">
                </div>
                <div class="col-3">
                    <input type="number" name="output_quantities[]" class="form-control bg-dark text-white" value="1" min="1" placeholder="Qtà">
                </div>
                <div class="col-1">
                    <button type="button" class="btn btn-link text-danger remove-output-btn p-1"><i class="bi bi-trash"></i></button>
                </div>
            `;
            outputsContainer.appendChild(newRow);
        });

        outputsContainer.addEventListener('click', function(e) {
            if (e.target.closest('.remove-output-btn')) {
                const row = e.target.closest('.output-row');
                if (outputsContainer.querySelectorAll('.output-row').length > 1) {
                    row.remove();
                } else {
                    alert("Almeno un output è richiesto.");
                }
            }
        });
    }
});
