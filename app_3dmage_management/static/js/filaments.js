document.addEventListener('DOMContentLoaded', async function() {
    const filamentsDataTag = document.getElementById('filaments-data');
    if (!filamentsDataTag) return;

    const URLS = {
        add_filament: filamentsDataTag.dataset.addFilamentUrl,
        add_spool: filamentsDataTag.dataset.addSpoolUrl,
        base_filament: filamentsDataTag.dataset.baseFilamentUrl,
        base_spool: filamentsDataTag.dataset.baseSpoolUrl,
        api_base_spool: filamentsDataTag.dataset.apiBaseSpoolUrl,
        toggle_spool_status: filamentsDataTag.dataset.toggleSpoolStatusUrl,
        api_filaments: filamentsDataTag.dataset.apiFilamentsUrl,
    };
    const csrftoken = getCookie('csrftoken');

    let allFilamentsData = [];
    async function loadFilamentsData() {
        try {
            const response = await fetch(URLS.api_filaments);
            if (response.ok) {
                allFilamentsData = await response.json();
            } else {
                console.error("Failed to load filament data for TomSelect.");
            }
        } catch (e) {
            console.error("Error fetching filament data:", e);
        }
    }
    await loadFilamentsData();


    function getTextColorForBg(hexColor) {
        if (!hexColor) return '#000000';
        try {
            let cleanHex = hexColor.startsWith('#') ? hexColor.slice(1) : hexColor;
            if (cleanHex.length === 3) {
                cleanHex = cleanHex.split('').map(char => char + char).join('');
            }
            const rgb = parseInt(cleanHex, 16);
            const r = (rgb >> 16) & 0xff;
            const g = (rgb >> 8) & 0xff;
            const b = (rgb >> 0) & 0xff;
            const luma = 0.2126 * r + 0.7152 * g + 0.0722 * b;
            return luma < 140 ? '#FFFFFF' : '#000000';
        } catch (e) {
            console.error("Invalid color format:", hexColor, e);
            return '#000000';
        }
    }

    function applyPillContrastColor() {
        document.querySelectorAll('.filament-pill').forEach(pill => {
            const styleAttr = pill.getAttribute('style');
            if (styleAttr && styleAttr.includes('background-color')) {
                const bgColorMatch = styleAttr.match(/#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})/);
                if (bgColorMatch) {
                    const hex = bgColorMatch[0];
                    pill.style.color = getTextColorForBg(hex);
                    if (pill.style.color === '#000000') {
                        pill.style.textShadow = 'none';
                    }
                }
            }
        });
    }
    applyPillContrastColor();

    const detailModalEl = document.getElementById('filamentDetailModal');
    if (!detailModalEl) return;
    const detailModal = new bootstrap.Modal(detailModalEl);

    const viewContainer = document.getElementById('filament-view-container');
    const editContainer = document.getElementById('filament-edit-container');
    const viewFooter = document.getElementById('footer-view-mode');
    const editFooter = document.getElementById('footer-edit-mode');

    const switchToEditBtn = document.getElementById('switchToEditModeBtn');
    const switchToViewBtn = document.getElementById('switchToViewModeBtn');
    const saveChangesBtn = document.getElementById('saveFilamentChangesBtn');
    const deleteBtnTrigger = document.getElementById('deleteFilamentBtnTrigger');
    const addSpoolBtnInModal = detailModalEl.querySelector('.add-spool-from-modal-btn');

    const editForm = document.getElementById('editFilamentForm');
    const title = document.getElementById('filamentDetailModalTitle');
    const editFormContainer = document.getElementById('editFilamentFormContainer');
    const readonlyDetailsContainer = document.getElementById('filament-details-readonly');
    const activeSpoolListContainer = document.getElementById('active-spool-list-container');
    const inactiveSpoolListContainer = document.getElementById('inactive-spool-list-container');

    const confirmDeleteFilamentModal = new bootstrap.Modal(document.getElementById('deleteFilamentConfirmModal'));
    const confirmDeleteFilamentBtn = document.getElementById('confirmDeleteFilamentBtn');
    const confirmDeleteSpoolModal = new bootstrap.Modal(document.getElementById('deleteSpoolConfirmModal'));
    const confirmDeleteSpoolBtn = document.getElementById('confirmDeleteSpoolBtn');

    const editSpoolModalEl = document.getElementById('editSpoolModal');
    const editSpoolModal = new bootstrap.Modal(editSpoolModalEl);
    const editSpoolForm = document.getElementById('editSpoolForm');
    const addSpoolModalEl = document.getElementById('addSpoolModal');
    const addFilamentModalEl = document.getElementById('addFilamentModal');
    const addFilamentModal = new bootstrap.Modal(addFilamentModalEl);

    let addSpoolTomSelect = null;
    if (addSpoolModalEl) {
        addSpoolModalEl.addEventListener('show.bs.modal', function() {
            const selectEl = document.getElementById('id_spool_form_filament');
            if (selectEl && !addSpoolTomSelect) {
                addSpoolTomSelect = new TomSelect(selectEl, {
                    valueField: 'id', labelField: 'name', searchField: 'name',
                    options: allFilamentsData, create: false,
                    render: {
                        option: function(data, escape) {
                            const textColor = getTextColorForBg(data.color_hex);
                            const textShadow = textColor === '#FFFFFF' ? '1px 1px 2px rgba(0,0,0,0.5)' : 'none';
                            return `<div><span class="filament-pill" style="background-color: ${data.color_hex}; color: ${textColor}; text-shadow: ${textShadow};">${escape(data.name)}</span></div>`;
                        },
                        item: function(data, escape) {
                             const textColor = getTextColorForBg(data.color_hex);
                             const textShadow = textColor === '#FFFFFF' ? '1px 1px 2px rgba(0,0,0,0.5)' : 'none';
                             return `<div class="filament-pill" style="background-color: ${data.color_hex}; color: ${textColor}; text-shadow: ${textShadow};">${escape(data.name)}</div>`;
                        }
                    }
                });
            }
            // BUG 3 FIX: Pre-seleziona il filamento se il modale è stato aperto dal dettaglio.
            const preselectId = addSpoolModalEl.dataset.preselectFilament;
            if (preselectId && addSpoolTomSelect) {
                addSpoolTomSelect.setValue(preselectId, true); // true = silent
                delete addSpoolModalEl.dataset.preselectFilament; // Pulisce per la prossima apertura
            } else if (addSpoolTomSelect) {
                // Se non c'è preselezione, pulisce il campo da valori precedenti
                addSpoolTomSelect.clear();
            }
        });
    }

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
                    ${spool.purchase_link ? `<a href="${spool.purchase_link}" target="_blank" class="btn btn-sm btn-outline-info" title="Vai al link di acquisto"><i class="bi bi-link-45deg"></i></a>` : ''}
                    <span class="badge bg-secondary ms-2">${spool.cost}</span>
                    <button type="button" class="btn btn-sm btn-outline-light edit-spool-btn ms-2" data-spool-id="${spool.id}" title="Modifica Bobina"><i class="bi bi-pencil-fill"></i></button>
                    <button type="button" class="btn btn-sm btn-outline-danger delete-spool-btn ms-2" data-spool-id="${spool.id}" title="Elimina Bobina"><i class="bi bi-trash-fill"></i></button>
                </div>
            </li>`;
    };

    const fetchAndRenderSpools = (filamentId) => {
        activeSpoolListContainer.innerHTML = '<p class="text-white-50 small fst-italic p-3">Caricamento bobine...</p>';
        inactiveSpoolListContainer.innerHTML = '';
        fetch(`${URLS.api_base_spool}${filamentId}/spools/`)
            .then(res => res.json())
            .then(data => {
                activeSpoolListContainer.innerHTML = data.active_spools.length > 0 ? `<ul class="list-group list-group-flush spool-list-group">${data.active_spools.map(renderSpool).join('')}</ul>` : '<p class="text-white-50 small">Nessuna bobina attiva.</p>';
                inactiveSpoolListContainer.innerHTML = data.inactive_spools.length > 0 ? `<ul class="list-group list-group-flush spool-list-group">${data.inactive_spools.map(renderSpool).join('')}</ul>` : '<p class="text-white-50 small">Nessuna bobina finita.</p>';
            }).catch(err => {
                console.error("Failed to fetch spools:", err);
                activeSpoolListContainer.innerHTML = '<p class="text-danger small">Errore nel caricamento delle bobine.</p>';
            });
    };

    const renderFilamentDetails = (data) => {
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

    detailModalEl.addEventListener('show.bs.modal', function(event) {
        const row = event.relatedTarget;
        if (!row || !row.dataset.filamentId) return;
        const filamentId = row.dataset.filamentId;

        editForm.action = `${URLS.base_filament}${filamentId}/edit/`;
        confirmDeleteFilamentBtn.dataset.deleteUrl = `${URLS.base_filament}${filamentId}/delete/`;
        addSpoolBtnInModal.dataset.filamentId = filamentId;

        viewContainer.style.display = 'block';
        editContainer.style.display = 'none';
        viewFooter.style.display = 'flex';
        editFooter.style.display = 'none';

        fetch(`${URLS.base_filament}${filamentId}/details/`)
            .then(res => res.json())
            .then(data => {
                title.textContent = `Dettaglio: ${data.material}-${data.color_code}-${data.brand}`;
                renderFilamentDetails(data);
                editFormContainer.innerHTML = document.getElementById('filament-form-template').innerHTML;
                for (const key in data) {
                    const field = editForm.querySelector(`[name="${key}"]`);
                    if (field) {
                        field.value = data[key] || (field.type === 'color' ? '#FFFFFF' : '');
                    }
                }
            });

        fetchAndRenderSpools(filamentId);
    });

    detailModalEl.addEventListener('hidden.bs.modal', function () {
        const nextAction = detailModalEl.dataset.nextAction;
        delete detailModalEl.dataset.nextAction;

        if (nextAction === 'editSpool') {
            const spoolId = detailModalEl.dataset.spoolIdToEdit;
            delete detailModalEl.dataset.spoolIdToEdit;
            if (spoolId) {
                editSpoolForm.action = `${URLS.base_spool}${spoolId}/edit/`;
                fetch(`${URLS.base_spool}${spoolId}/details/`)
                    .then(res => res.json())
                    .then(data => {
                        const modalBody = document.getElementById('editSpoolModalBody');
                        const template = document.getElementById('spool-edit-form-template');
                        modalBody.innerHTML = '';
                        modalBody.appendChild(template.content.cloneNode(true));
                        modalBody.querySelector('[name="cost"]').value = data.cost;
                        modalBody.querySelector('[name="purchase_link"]').value = data.purchase_link || '';
                        modalBody.querySelector('[name="is_active"]').checked = data.is_active;
                        modalBody.querySelector('[name="correction"]').value = '';
                        editSpoolModal.show();
                    }).catch(err => {
                        console.error("Failed to fetch spool details:", err);
                        showToast('Errore nel caricare i dati della bobina.', 'error');
                        window.location.reload();
                    });
            }
        } else if (nextAction === 'addSpool') {
             // BUG 3 FIX: Il filamento corretto viene ora impostato nell'evento 'show.bs.modal'
             // del modale 'addSpoolModal', usando l'attributo 'data-preselect-filament'.
            new bootstrap.Modal(document.getElementById('addSpoolModal')).show();
        } else {
            // Se non c'è azione pianificata, ricarica la pagina.
            // Il reload è stato spostato qui dall'evento 'hidden' dei modali secondari.
            window.location.reload();
        }
    });

    switchToEditBtn.addEventListener('click', function() {
        viewContainer.style.display = 'none';
        editContainer.style.display = 'block';
        viewFooter.style.display = 'none';
        editFooter.style.display = 'flex';
        title.textContent = title.textContent.replace('Dettaglio:', 'Modifica:');
    });

    switchToViewBtn.addEventListener('click', function() {
        viewContainer.style.display = 'block';
        editContainer.style.display = 'none';
        viewFooter.style.display = 'flex';
        editFooter.style.display = 'none';
        title.textContent = title.textContent.replace('Modifica:', 'Dettaglio:');
    });

    saveChangesBtn.addEventListener('click', function() {
        showLoader();
        fetch(editForm.action, {
                method: 'POST', body: new FormData(editForm),
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
            }).finally(() => hideLoader());
    });

    addSpoolBtnInModal.addEventListener('click', function() {
        detailModalEl.dataset.nextAction = 'addSpool';
        // BUG 3 FIX: Passa l'ID del filamento al modale Aggiungi Bobina
        const filamentId = this.dataset.filamentId;
        addSpoolModalEl.dataset.preselectFilament = filamentId;
        // BUG 2 FIX: Aggiunge un flag per indicare che è stato aperto dal modale dettaglio
        addSpoolModalEl.dataset.openedFromDetail = 'true';
        detailModal.hide();
    });

    deleteBtnTrigger.addEventListener('click', function() {
        document.getElementById('deleteFilamentConfirmBody').textContent = `Sei sicuro di voler eliminare questo tipo di filamento? L'azione è irreversibile.`;
        confirmDeleteFilamentModal.show();
    });

    confirmDeleteFilamentBtn.addEventListener('click', function() {
        showLoader();
        fetch(this.dataset.deleteUrl, {
                method: 'POST', headers: { 'X-CSRFToken': csrftoken }
            })
            .then(res => res.json())
            .then(data => {
                if (data.status === 'ok') {
                    window.location.reload();
                } else {
                    showToast(data.message || 'Errore durante l\'eliminazione.', 'error');
                    confirmDeleteFilamentModal.hide();
                    hideLoader();
                }
            }).catch(() => hideLoader());
    });

    // BUG 1 FIX: Gestione AJAX per l'aggiunta di un nuovo tipo di filamento
    const addFilamentForm = document.getElementById('addFilamentForm');
    addFilamentForm.addEventListener('submit', function(e) {
        e.preventDefault();
        showLoader();
        fetch(this.action, {
            method: 'POST', body: new FormData(this),
            headers: { 'X-CSRFToken': csrftoken }
        })
        .then(res => res.json())
        .then(data => {
            if (data.status === 'ok') {
                showToast('Tipo filamento aggiunto!', 'success');
                // Ricarica la pagina per aggiornare l'elenco e la tabella
                window.location.reload();
            } else {
                showToast('Errore: controlla i dati inseriti.', 'error');
            }
        }).catch(err => {
            console.error(err);
            showToast('Errore di comunicazione col server.', 'error');
        }).finally(() => hideLoader());
    });


    detailModalEl.addEventListener('click', function(e) {
        const deleteButton = e.target.closest('.delete-spool-btn');
        const editButton = e.target.closest('.edit-spool-btn');
        const toggleSwitch = e.target.closest('.spool-status-toggle');

        if (deleteButton) {
            e.stopPropagation();
            const spoolId = deleteButton.dataset.spoolId;
            confirmDeleteSpoolBtn.dataset.spoolId = spoolId;
            confirmDeleteSpoolModal.show();
        }

        if (editButton) {
            e.stopPropagation();
            const spoolId = editButton.dataset.spoolId;
            detailModalEl.dataset.nextAction = 'editSpool';
            detailModalEl.dataset.spoolIdToEdit = spoolId;
            detailModal.hide();
        }

        if (toggleSwitch) {
            const spoolId = toggleSwitch.dataset.spoolId;
            fetch(`${URLS.toggle_spool_status}${spoolId}/toggle_status/`, {
                method: 'POST', headers: { 'X-CSRFToken': csrftoken }
            }).then(res => res.json()).then(data => {
                if (data.status === 'ok') {
                    fetchAndRenderSpools(addSpoolBtnInModal.dataset.filamentId);
                    showToast(`Bobina ${data.is_active ? 'riattivata' : 'disattivata'}.`, 'info');
                } else {
                    showToast('Errore durante l\'aggiornamento dello stato.', 'error');
                    toggleSwitch.checked = !toggleSwitch.checked;
                }
            });
        }
    });

    confirmDeleteSpoolBtn.addEventListener('click', function() {
        const spoolId = this.dataset.spoolId;
        if (!spoolId) return;
        showLoader();
        fetch(`${URLS.base_spool}${spoolId}/delete/`, {
            method: 'POST', headers: { 'X-CSRFToken': csrftoken }
        })
        .then(res => res.json())
        .then(data => {
            if (data.status === 'ok') {
                showToast(data.message, 'success');
                fetchAndRenderSpools(addSpoolBtnInModal.dataset.filamentId);
            } else {
                showToast(data.message, 'error');
            }
        }).finally(() => {
            confirmDeleteSpoolModal.hide();
            hideLoader();
        });
    });

    editSpoolForm.addEventListener('submit', function(e) {
        e.preventDefault();
        showLoader();
        fetch(this.action, {
            method: 'POST', body: new FormData(this),
            headers: { 'X-CSRFToken': csrftoken }
        })
        .then(res => res.json())
        .then(data => {
            if (data.status === 'ok') {
                showToast('Bobina aggiornata con successo.', 'success');
                editSpoolModal.hide();
            } else {
                showToast('Errore durante la modifica.', 'error');
            }
        }).finally(() => hideLoader());
    });

    function reShowDetailModal() {
        if (!detailModalEl.classList.contains('show')) {
            detailModal.show();
        }
    };

    editSpoolModalEl.addEventListener('hidden.bs.modal', reShowDetailModal);

    if (addSpoolModalEl) {
        // BUG 2 FIX: Chiudendo il modale Aggiungi Bobina, riapre il dettaglio SOLO se
        // era stato aperto da lì. Altrimenti non fa nulla.
        addSpoolModalEl.addEventListener('hidden.bs.modal', function() {
            if (addSpoolModalEl.dataset.openedFromDetail === 'true') {
                reShowDetailModal();
            }
            // Pulisce il flag per la prossima apertura
            delete addSpoolModalEl.dataset.openedFromDetail;
        });
    }
});
