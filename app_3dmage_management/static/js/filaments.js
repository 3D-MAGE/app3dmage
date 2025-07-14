document.addEventListener('DOMContentLoaded', function() {
    const filamentsDataTag = document.getElementById('filaments-data');
    if (!filamentsDataTag) return;

    // URLs used in the script
    const URLS = {
        add_filament: filamentsDataTag.dataset.addFilamentUrl,
        add_spool: filamentsDataTag.dataset.addSpoolUrl,
        base_filament: filamentsDataTag.dataset.baseFilamentUrl,
        base_spool: filamentsDataTag.dataset.baseSpoolUrl,
        api_base_spool: filamentsDataTag.dataset.apiBaseSpoolUrl,
        toggle_spool_status: filamentsDataTag.dataset.toggleSpoolStatusUrl,
    };
    const csrftoken = getCookie('csrftoken');

    // Flag to prevent reload when switching modals
    let isSwitchingModals = false;

    // Function to determine text color based on background hex
    const getContrastYIQ = (hexcolor) => {
        hexcolor = hexcolor.replace("#", "");
        const r = parseInt(hexcolor.substr(0, 2), 16);
        const g = parseInt(hexcolor.substr(2, 2), 16);
        const b = parseInt(hexcolor.substr(4, 2), 16);
        const yiq = ((r * 299) + (g * 587) + (b * 114)) / 1000;
        return (yiq >= 128) ? 'black' : 'white';
    };

    // Apply contrast color to filament pills on page load
    document.querySelectorAll('.filament-pill').forEach(pill => {
        const bgColor = pill.style.backgroundColor;
        if (bgColor) pill.style.color = getContrastYIQ(bgColor);
    });

    // Main modal and its components
    const detailModalEl = document.getElementById('filamentDetailModal');
    if (!detailModalEl) return;
    const detailModal = new bootstrap.Modal(detailModalEl);

    // Modal containers for view/edit modes
    const viewContainer = document.getElementById('filament-view-container');
    const editContainer = document.getElementById('filament-edit-container');

    // Modal footers for view/edit modes
    const viewFooter = document.getElementById('footer-view-mode');
    const editFooter = document.getElementById('footer-edit-mode');

    // Buttons
    const switchToEditBtn = document.getElementById('switchToEditModeBtn');
    const switchToViewBtn = document.getElementById('switchToViewModeBtn');
    const saveChangesBtn = document.getElementById('saveFilamentChangesBtn');
    const deleteBtnTrigger = document.getElementById('deleteFilamentBtnTrigger');
    const addSpoolBtnInModal = detailModalEl.querySelector('.add-spool-from-modal-btn');

    // Form and title
    const editForm = document.getElementById('editFilamentForm');
    const title = document.getElementById('filamentDetailModalTitle');
    const editFormContainer = document.getElementById('editFilamentFormContainer');
    const readonlyDetailsContainer = document.getElementById('filament-details-readonly');

    // Spool list containers
    const activeSpoolListContainer = document.getElementById('active-spool-list-container');
    const inactiveSpoolListContainer = document.getElementById('inactive-spool-list-container');

    // Confirmation Modals
    const confirmDeleteFilamentModal = new bootstrap.Modal(document.getElementById('deleteFilamentConfirmModal'));
    const confirmDeleteFilamentBtn = document.getElementById('confirmDeleteFilamentBtn');
    const confirmDeleteSpoolModal = new bootstrap.Modal(document.getElementById('deleteSpoolConfirmModal'));
    const confirmDeleteSpoolBtn = document.getElementById('confirmDeleteSpoolBtn');

    /**
     * Renders a single spool item as an HTML string.
     * @param {object} spool - The spool data object.
     * @returns {string} - The HTML string for the list item.
     */
    const renderSpool = (spool) => {
        const remainingGrams = parseFloat(spool.remaining);
        const checked = spool.is_active ? 'checked' : '';
        return `
            <li class="list-group-item d-flex justify-content-between align-items-center" id="spool-item-${spool.id}" data-spool-id="${spool.id}">
                <div class="form-check form-switch">
                    <input class="form-check-input spool-status-toggle" type="checkbox" role="switch" id="spool-toggle-${spool.id}" data-spool-id="${spool.id}" ${checked}>
                    <label class="form-check-label" for="spool-toggle-${spool.id}">
                        ${spool.text} (${remainingGrams.toFixed(0)}g rim.)
                    </label>
                </div>
                <div>
                    ${spool.purchase_link ? `<a href="${spool.purchase_link}" target="_blank" class="btn btn-sm btn-outline-info" title="Vai al link di acquisto" onclick="event.stopPropagation();"><i class="bi bi-link-45deg"></i></a>` : ''}
                    <span class="badge bg-secondary ms-2">${spool.cost}</span>
                    <button type="button" class="btn btn-sm btn-outline-danger delete-spool-btn ms-2" data-spool-id="${spool.id}" title="Elimina Bobina"><i class="bi bi-trash-fill"></i></button>
                </div>
            </li>`;
    };

    /**
     * Fetches and renders both active and inactive spools for a given filament.
     * @param {string} filamentId - The ID of the filament.
     */
    const fetchAndRenderSpools = (filamentId) => {
        activeSpoolListContainer.innerHTML = '<p class="text-white-50 small fst-italic p-3">Caricamento bobine...</p>';
        inactiveSpoolListContainer.innerHTML = '';

        fetch(`${URLS.api_base_spool}${filamentId}/spools/`)
            .then(res => res.json())
            .then(data => {
                // Render active spools
                if (data.active_spools.length > 0) {
                    activeSpoolListContainer.innerHTML = `<ul class="list-group list-group-flush spool-list-group">${data.active_spools.map(renderSpool).join('')}</ul>`;
                } else {
                    activeSpoolListContainer.innerHTML = '<p class="text-white-50 small">Nessuna bobina attiva per questo filamento.</p>';
                }
                // Render inactive spools
                if (data.inactive_spools.length > 0) {
                    inactiveSpoolListContainer.innerHTML = `<ul class="list-group list-group-flush spool-list-group">${data.inactive_spools.map(renderSpool).join('')}</ul>`;
                } else {
                    inactiveSpoolListContainer.innerHTML = '<p class="text-white-50 small">Nessuna bobina finita.</p>';
                }
            });
    };

    /**
     * Renders the read-only details of the filament.
     * @param {object} data - The filament data object.
     */
    const renderFilamentDetails = (data) => {
        // MODIFICA: Semplificata la vista per mostrare solo i campi richiesti.
        readonlyDetailsContainer.innerHTML = `
            <div class="col-md-6 col-lg-4">
                <strong class="text-white-50">Nome Colore</strong>
                <p class="d-flex align-items-center">
                    <span class="d-inline-block me-2" style="width: 20px; height: 20px; background-color: ${data.color_hex}; border: 1px solid #555; border-radius: 4px;"></span>
                    ${data.color_name || 'N/D'}
                </p>
            </div>
            <div class="col-md-6 col-lg-4">
                <strong class="text-white-50">Temp. Ugello</strong>
                <p>${data.nozzle_temp}°C</p>
            </div>
            <div class="col-md-6 col-lg-4">
                <strong class="text-white-50">Temp. Piatto</strong>
                <p>${data.bed_temp}°C</p>
            </div>
             <div class="col-md-6 col-lg-4">
                <strong class="text-white-50">Velocità Volumetrica</strong>
                <p>${data.volumetric_speed} mm³/s</p>
            </div>
            <div class="col-12">
                <strong class="text-white-50">Note</strong>
                <p class="text-break">${data.notes || 'Nessuna nota.'}</p>
            </div>
        `;
    };

    // Event listener for when the modal is about to be shown
    detailModalEl.addEventListener('show.bs.modal', function(event) {
        const row = event.relatedTarget;
        if (!row || !row.dataset.filamentId) return;
        const filamentId = row.dataset.filamentId;

        // Set URLs and data attributes for forms and buttons
        editForm.action = `${URLS.base_filament}${filamentId}/edit/`;
        confirmDeleteFilamentBtn.dataset.deleteUrl = `${URLS.base_filament}${filamentId}/delete/`;
        addSpoolBtnInModal.dataset.filamentId = filamentId;

        // Reset to view mode
        viewContainer.style.display = 'block';
        editContainer.style.display = 'none';
        viewFooter.style.display = 'flex';
        editFooter.style.display = 'none';

        // Fetch filament data
        fetch(`${URLS.base_filament}${filamentId}/details/`)
            .then(res => res.json())
            .then(data => {
                title.textContent = `Dettaglio: ${data.material}-${data.color_code}-${data.brand}`;
                // Populate both read-only view and edit form
                renderFilamentDetails(data);
                editFormContainer.innerHTML = document.getElementById('filament-form-template').innerHTML;
                for (const key in data) {
                    const field = editForm.querySelector(`[name="${key}"]`);
                    if (field) {
                        field.value = data[key] || (field.type === 'color' ? '#FFFFFF' : '');
                    }
                }
            });

        // Fetch and display spools
        fetchAndRenderSpools(filamentId);
    });

    // Refresh page on modal close to reflect main table changes
    detailModalEl.addEventListener('hidden.bs.modal', function () {
        if (!isSwitchingModals) {
            window.location.reload();
        }
        // Reset the flag
        isSwitchingModals = false;
    });

    // Switch to edit mode
    switchToEditBtn.addEventListener('click', function() {
        viewContainer.style.display = 'none';
        editContainer.style.display = 'block';
        viewFooter.style.display = 'none';
        editFooter.style.display = 'flex';
        title.textContent = title.textContent.replace('Dettaglio:', 'Modifica:');
    });

    // Switch back to view mode
    switchToViewBtn.addEventListener('click', function() {
        viewContainer.style.display = 'block';
        editContainer.style.display = 'none';
        viewFooter.style.display = 'flex';
        editFooter.style.display = 'none';
        title.textContent = title.textContent.replace('Modifica:', 'Dettaglio:');
    });

    // Save changes from edit form
    saveChangesBtn.addEventListener('click', function() {
        fetch(editForm.action, {
                method: 'POST',
                body: new FormData(editForm),
                headers: { 'X-CSRFToken': csrftoken }
            })
            .then(res => res.json())
            .then(data => {
                if (data.status === 'ok') {
                    showToast('Filamento aggiornato con successo.', 'success');
                    const filamentId = addSpoolBtnInModal.dataset.filamentId;
                    fetch(`${URLS.base_filament}${filamentId}/details/`).then(r => r.json()).then(renderFilamentDetails);
                    switchToViewBtn.click();
                } else {
                    showToast('Errore durante la modifica.', 'error');
                }
            });
    });

    // Open "Add Spool" modal
    addSpoolBtnInModal.addEventListener('click', function() {
        const filamentId = this.dataset.filamentId;
        document.querySelector('#addSpoolModal select[name="filament"]').value = filamentId;

        isSwitchingModals = true;

        detailModal.hide();
        new bootstrap.Modal(document.getElementById('addSpoolModal')).show();
    });

    // Trigger filament delete confirmation
    deleteBtnTrigger.addEventListener('click', function() {
        document.getElementById('deleteFilamentConfirmBody').textContent = `Sei sicuro di voler eliminare questo tipo di filamento? L'azione è irreversibile.`;
        confirmDeleteFilamentModal.show();
    });

    // Confirm and execute filament deletion
    confirmDeleteFilamentBtn.addEventListener('click', function() {
        fetch(this.dataset.deleteUrl, {
                method: 'POST',
                headers: { 'X-CSRFToken': csrftoken }
            })
            .then(res => res.json())
            .then(data => {
                if (data.status === 'ok') {
                    window.location.reload();
                } else {
                    showToast(data.message || 'Errore durante l\'eliminazione.', 'error');
                    confirmDeleteFilamentModal.hide();
                }
            });
    });

    // Event delegation for dynamically created spool buttons (delete and toggle)
    detailModalEl.addEventListener('click', function(e) {
        // Handle spool deletion
        const deleteButton = e.target.closest('.delete-spool-btn');
        if (deleteButton) {
            e.stopPropagation();
            const spoolId = deleteButton.dataset.spoolId;
            confirmDeleteSpoolBtn.dataset.spoolId = spoolId;
            confirmDeleteSpoolModal.show();
        }

        // Handle spool status toggle
        const toggleSwitch = e.target.closest('.spool-status-toggle');
        if (toggleSwitch) {
            const spoolId = toggleSwitch.dataset.spoolId;
            fetch(`${URLS.toggle_spool_status}${spoolId}/toggle_status/`, {
                method: 'POST',
                headers: { 'X-CSRFToken': csrftoken }
            }).then(res => res.json()).then(data => {
                if (data.status === 'ok') {
                    const spoolItem = document.getElementById(`spool-item-${spoolId}`);
                    if (data.is_active) {
                        let list = activeSpoolListContainer.querySelector('.spool-list-group');
                        if (!list) {
                            list = document.createElement('ul');
                            list.className = 'list-group list-group-flush spool-list-group';
                            activeSpoolListContainer.innerHTML = '';
                            activeSpoolListContainer.appendChild(list);
                        }
                        list.appendChild(spoolItem);
                    } else {
                        let list = inactiveSpoolListContainer.querySelector('.spool-list-group');
                        if (!list) {
                            list = document.createElement('ul');
                            list.className = 'list-group list-group-flush spool-list-group';
                            inactiveSpoolListContainer.innerHTML = '';
                            inactiveSpoolListContainer.appendChild(list);
                        }
                        list.appendChild(spoolItem);
                    }
                    showToast(`Bobina ${data.is_active ? 'riattivata' : 'disattivata'}.`, 'info');
                } else {
                    showToast('Errore durante l\'aggiornamento dello stato.', 'error');
                    toggleSwitch.checked = !toggleSwitch.checked;
                }
            });
        }
    });

    // Add event listener for the new spool delete confirmation button
    confirmDeleteSpoolBtn.addEventListener('click', function() {
        const spoolId = this.dataset.spoolId;
        if (!spoolId) return;

        fetch(`${URLS.base_spool}${spoolId}/delete/`, {
            method: 'POST',
            headers: { 'X-CSRFToken': csrftoken }
        })
        .then(res => res.json())
        .then(data => {
            confirmDeleteSpoolModal.hide();
            if (data.status === 'ok') {
                showToast(data.message, 'success');
                const spoolItem = document.getElementById(`spool-item-${spoolId}`);
                if (spoolItem) {
                    spoolItem.remove();
                }
                // Check if lists are empty and show placeholder text
                const activeList = activeSpoolListContainer.querySelector('.spool-list-group');
                if (activeList && activeList.children.length === 0) {
                    activeSpoolListContainer.innerHTML = '<p class="text-white-50 small">Nessuna bobina attiva per questo filamento.</p>';
                }
                const inactiveList = inactiveSpoolListContainer.querySelector('.spool-list-group');
                if (inactiveList && inactiveList.children.length === 0) {
                    inactiveSpoolListContainer.innerHTML = '<p class="text-white-50 small">Nessuna bobina finita.</p>';
                }
            } else {
                showToast(data.message, 'error');
            }
        });
    });
});
