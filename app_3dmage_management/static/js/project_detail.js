document.addEventListener('DOMContentLoaded', async function() {
    // -----------------------------------------------------------------
    // SETUP INIZIALE E LETTURA DATI
    // -----------------------------------------------------------------
    const scriptUrlsTag = document.getElementById('project-detail-urls');
    if (!scriptUrlsTag) {
        console.error("Tag script con URL non trovato. Impossibile inizializzare la pagina.");
        return;
    }

    const projectId = scriptUrlsTag.dataset.projectId;
    const referer = scriptUrlsTag.dataset.referer;

    const URLS = {
        apiFilaments: scriptUrlsTag.dataset.apiFilamentsUrl,
        ajaxPlates: scriptUrlsTag.dataset.ajaxPlatesUrl,
        addFile: scriptUrlsTag.dataset.addFileUrl,
        cloneFile: scriptUrlsTag.dataset.cloneFileUrl,
        fileBase: scriptUrlsTag.dataset.fileUrlBase,
        projectBase: scriptUrlsTag.dataset.projectUrlBase,
        apiSpoolsUrlBase: scriptUrlsTag.dataset.apiSpoolsUrlBase
    };

    const csrftoken = getCookie('csrftoken');

    // Modali
    const printFileModalEl = document.getElementById('printFileModal');
    const printFileModal = new bootstrap.Modal(printFileModalEl);

    const requeueModalEl = document.getElementById('requeuePrintModal');
    const requeueModal = requeueModalEl ? new bootstrap.Modal(requeueModalEl) : null;

    const confirmDeleteModalEl = document.getElementById('deletePrintFileConfirmModal');
    const confirmDeleteModal = confirmDeleteModalEl ? new bootstrap.Modal(confirmDeleteModalEl) : null;

    const autoCreateModalEl = document.getElementById('autoCreateFilesModal');
    const autoCreateModal = autoCreateModalEl ? new bootstrap.Modal(autoCreateModalEl) : null;

    let lastFailedFileId = null;
    let lastPlannedFilamentUsage = null;

    let tomSelectInstances = new Map();

    const filamentsResponse = await fetch(URLS.apiFilaments);
    if (!filamentsResponse.ok) { console.error("Impossibile caricare i dati dei filamenti."); return; }
    const allFilaments = await filamentsResponse.json();

    const toggleActualQuantity = (status) => {
        const actualWrapper = printFileModalEl.querySelector('#actual-quantity-wrapper');
        const producedInput = printFileModalEl.querySelector('[name="produced_quantity"]');
        const actualInput = printFileModalEl.querySelector('[name="actual_quantity"]');

        if (actualWrapper && actualInput) {
            const isVisible = (status === 'DONE' || status === 'FAILED');
            actualWrapper.style.display = isVisible ? 'block' : 'none';
            actualInput.required = isVisible;

            if (isVisible) {
                if (status === 'DONE' && producedInput) {
                    actualInput.value = producedInput.value;
                } else if (status === 'FAILED') {
                    actualInput.value = 0;
                }
            }
        }
    };


    const statusContainer = printFileModalEl.querySelector('#status-btn-container');
    if (statusContainer) {
      statusContainer.addEventListener('click', function(e) {
        const btn = e.target.closest('.status-btn');
        if (btn) {
          const status = btn.dataset.status;
          setActiveStatus(status);
          toggleWastedGrams(status);
          toggleActualQuantity(status);
        }
      });
    }

    // -----------------------------------------------------------------
    // FUNZIONI HELPER
    // -----------------------------------------------------------------
    const getContrastYIQ = (hexcolor) => {
        if (!hexcolor) return 'black';
        hexcolor = hexcolor.replace("#", "");
        if (hexcolor.length === 3) {
            hexcolor = hexcolor.split('').map(char => char + char).join('');
        }
        if (hexcolor.length !== 6) {
            return 'black';
        }
        const r = parseInt(hexcolor.substr(0, 2), 16);
        const g = parseInt(hexcolor.substr(2, 2), 16);
        const b = parseInt(hexcolor.substr(4, 2), 16);
        const yiq = ((r * 299) + (g * 587) + (b * 114)) / 1000;
        return (yiq >= 128) ? 'black' : 'white';
    };

    const createFilamentRow = () => {
        const row = document.createElement('div');
        row.className = 'row align-items-center filament-row mb-2';
        row.innerHTML = `
            <div class="col-md-5">
                <select class="form-select tom-select-filament" placeholder="Seleziona Filamento..."></select>
            </div>
            <div class="col-md-4">
                <select class="form-select spool-select" disabled>
                    <option value="">Scegli un filamento</option>
                </select>
            </div>
            <div class="col-md-3">
                <input type="number" class="form-control grams-input" placeholder="grammi" min="0.01" step="0.01">
                <div class="form-text text-warning warning-message small" style="display: none;">Scorta insufficiente!</div>
            </div>`;
        return row;
    };

    const initializeTomSelect = (selectElement) => {
        if (!selectElement) return;
        const instance = new TomSelect(selectElement, {
            valueField: 'id',
            labelField: 'name',
            searchField: 'name',
            options: allFilaments,
            create: false,
            render: {
                option: function(data, escape) {
                    return `<div style="background-color:${data.color_hex}; color:${getContrastYIQ(data.color_hex)}; padding: 5px 10px;">${escape(data.name)}</div>`;
                },
                item: function(data, escape) {
                    return `<div style="background-color:${data.color_hex}; color:${getContrastYIQ(data.color_hex)};">${escape(data.name)}</div>`;
                }
            },
            onChange: function(value) {
                const changeEvent = new Event('change', { bubbles: true });
                selectElement.dispatchEvent(changeEvent);
            }
        });
        tomSelectInstances.set(selectElement, instance);
    };

    const updateFilamentRows = (desiredCount) => {
        const container = printFileModalEl.querySelector('#filament-inputs-container');
        const currentRows = container.querySelectorAll('.filament-row');
        const currentCount = currentRows.length;

        if (desiredCount > currentCount) {
            for (let i = currentCount; i < desiredCount; i++) {
                const newRow = createFilamentRow();
                container.appendChild(newRow);
                initializeTomSelect(newRow.querySelector('.tom-select-filament'));
            }
        } else if (desiredCount < currentCount) {
            for (let i = currentCount; i > desiredCount; i--) {
                const rowToRemove = container.lastChild;
                const selectToDestroy = rowToRemove.querySelector('.tom-select-filament');
                if (tomSelectInstances.has(selectToDestroy)) {
                    tomSelectInstances.get(selectToDestroy).destroy();
                    tomSelectInstances.delete(selectToDestroy);
                }
                container.removeChild(rowToRemove);
            }
        }
    };

    const setActiveStatus = (statusValue) => { const sHidden = printFileModalEl.querySelector('#id_status_hidden'); const sContainer = printFileModalEl.querySelector('#status-btn-container'); if (sHidden && sContainer) { sHidden.value = statusValue; sContainer.querySelectorAll('.status-btn').forEach(b => { b.classList.remove('active'); if (b.dataset.status === statusValue) b.classList.add('active'); }); } };
    const checkWeightAndWarn = (gramsInput) => { const r = gramsInput.closest('.row'); if (!r) return; const s = r.querySelector('.spool-select'); const w = r.querySelector('.warning-message'); const opt = s.options[s.selectedIndex]; if (!opt || !opt.value || !opt.dataset.remaining) { w.style.display = 'none'; return; } const g = parseFloat(gramsInput.value) || 0; const a = parseFloat(opt.dataset.remaining); w.style.display = g > a ? 'block' : 'none'; };
    const toggleWastedGrams = (status) => {
        const wastedWrapper = printFileModalEl.querySelector('#wasted-grams-wrapper');
        if (status === 'FAILED') {
            let totalGrams = 0;
            printFileModalEl.querySelectorAll('.grams-input').forEach(input => {
                totalGrams += parseFloat(input.value) || 0;
            });
            printFileModalEl.querySelector('#wasted_grams_input').value = totalGrams.toFixed(2);
            wastedWrapper.style.display = 'block';
        } else {
            wastedWrapper.style.display = 'none';
        }
    };

    function resetPrintFileForm() {
        const form = document.getElementById('printFileForm');
        form.reset();
        form.querySelector('input[name="name"]').value = '';
        form.querySelector('input[name="print_time_days"]').value = '0';
        form.querySelector('input[name="print_time_hours"]').value = '0';
        form.querySelector('input[name="print_time_minutes"]').value = '0';
        form.querySelector('select[name="printer"]').value = '';
        const plateSelect = form.querySelector('select[name="plate"]');
        plateSelect.innerHTML = '<option value="">Scegli prima una stampante</option>';
        plateSelect.disabled = true;

        printFileModalEl.querySelector('#printFileModalLabel').textContent = 'Aggiungi File di Stampa';
        form.action = URLS.addFile;
        printFileModalEl.querySelector('#status-field-wrapper').style.display = 'none';
        printFileModalEl.querySelector('#delete-print-file-btn').style.display = 'none';
        printFileModalEl.querySelector('#clone-print-file-btn').style.display = 'none';

        const wastedWrapper = printFileModalEl.querySelector('#wasted-grams-wrapper');
        if(wastedWrapper) wastedWrapper.style.display = 'none';

        const actualWrapper = printFileModalEl.querySelector('#actual-quantity-wrapper');
        const actualInput = printFileModalEl.querySelector('[name="actual_quantity"]');
        if(actualWrapper) actualWrapper.style.display = 'none';
        if(actualInput) actualInput.required = false;

        const countSelector = printFileModalEl.querySelector('#filament-count-selector');
        countSelector.querySelector('.active')?.classList.remove('active');
        countSelector.querySelector('[data-count="1"]').classList.add('active');

        tomSelectInstances.forEach(instance => instance.destroy());
        tomSelectInstances.clear();
        const cont = printFileModalEl.querySelector('#filament-inputs-container');
        cont.innerHTML = '';

        const firstRow = createFilamentRow();
        cont.appendChild(firstRow);
        initializeTomSelect(firstRow.querySelector('.tom-select-filament'));

        setActiveStatus('TODO');

        const projectIdHiddenInput = form.querySelector('#id_project_hidden');
        if (projectIdHiddenInput && projectId) {
            projectIdHiddenInput.value = projectId;
        }
    }

    async function loadAndSelectPlate(printerId, plateIdToSelect = null) {
        const plateSelect = printFileModalEl.querySelector('select[name="plate"]');
        plateSelect.innerHTML = '<option value="">Caricamento...</option>';
        plateSelect.disabled = true;
        if (!printerId) { plateSelect.innerHTML = '<option value="">Scegli una stampante</option>'; return; }
        try {
            const response = await fetch(`${URLS.ajaxPlates}?printer_id=${printerId}`);
            const data = await response.json();
            plateSelect.innerHTML = '<option value="">Seleziona Piatto</option>';
            data.forEach(plate => { plateSelect.innerHTML += `<option value="${plate.id}">${plate.name}</option>`; });
            plateSelect.disabled = false;
            if (plateIdToSelect) plateSelect.value = plateIdToSelect;
        } catch (error) { plateSelect.innerHTML = '<option value="">Errore</option>'; }
    }

    async function showEditModal(fileId) {
        if (!fileId) return;
        resetPrintFileForm();
        const form = document.getElementById('printFileForm');
        form.action = `${URLS.fileBase}${fileId}/edit/`;
        printFileModalEl.querySelector('#printFileModalLabel').textContent = 'Modifica File di Stampa';
        printFileModalEl.querySelector('#status-field-wrapper').style.display = 'block';
        const deleteBtn = printFileModalEl.querySelector('#delete-print-file-btn');
        deleteBtn.style.display = 'block';
        deleteBtn.dataset.fileId = fileId;
        const cloneBtn = printFileModalEl.querySelector('#clone-print-file-btn');
        cloneBtn.style.display = 'block';
        cloneBtn.dataset.fileId = fileId;
        const response = await fetch(`${URLS.fileBase}${fileId}/details/`);
        const data = await response.json();
        form.querySelector('input[name="name"]').value = data.name;
        const totalSeconds = data.print_time_seconds || 0;
        const days = Math.floor(totalSeconds / 86400);
        const remainingSecondsAfterDays = totalSeconds % 86400;
        const hours = Math.floor(remainingSecondsAfterDays / 3600);
        const minutes = Math.floor((remainingSecondsAfterDays % 3600) / 60);
        form.querySelector('input[name="print_time_days"]').value = days;
        form.querySelector('input[name="print_time_hours"]').value = hours;
        form.querySelector('input[name="print_time_minutes"]').value = minutes;
        form.querySelector('select[name="printer"]').value = data.printer;
        setActiveStatus(data.status);
        toggleWastedGrams(data.status);

        form.querySelector('[name="produced_quantity"]').value = data.produced_quantity;
        form.querySelector('[name="actual_quantity"]').value = data.actual_quantity;
        toggleActualQuantity(data.status);

        await loadAndSelectPlate(data.printer, data.plate);
        const filamentsUsed = data.filaments_used || [];
        const countSelector = printFileModalEl.querySelector('#filament-count-selector');
        countSelector.querySelector('.active')?.classList.remove('active');
        const btnToActivate = countSelector.querySelector(`[data-count="${filamentsUsed.length || 1}"]`);
        if (btnToActivate) btnToActivate.classList.add('active');

        updateFilamentRows(filamentsUsed.length || 1);

        const rows = printFileModalEl.querySelectorAll('.filament-row');
        for (let i = 0; i < filamentsUsed.length; i++) {
            const usage = filamentsUsed[i];
            const row = rows[i];
            const filamentSelect = row.querySelector('.tom-select-filament');
            const spoolSelect = row.querySelector('.spool-select');

            const tomInstance = tomSelectInstances.get(filamentSelect);
            if (tomInstance) {
                tomInstance.setValue(usage.spool__filament_id, true);
            }

            const spoolUrl = URLS.apiSpoolsUrlBase.replace('0', usage.spool__filament_id);
            const spoolsResponse = await fetch(spoolUrl);
            const spoolsData = await spoolsResponse.json();
            const spools = spoolsData.active_spools || [];
            spoolSelect.innerHTML = '<option value="">Seleziona Bobina...</option>';
            if (spools.length > 0) {
              spools.forEach(spool => {
                  spoolSelect.innerHTML += `<option value="${spool.id}" data-remaining="${spool.remaining}">${spool.text}</option>`;
              });
              spoolSelect.disabled = false;
              spoolSelect.value = usage.spool_id;
            } else {
              spoolSelect.innerHTML = '<option value="">Nessuna bobina</option>';
            }

            row.querySelector('.grams-input').value = usage.grams_used;
            checkWeightAndWarn(row.querySelector('.grams-input'));
        }
        printFileModal.show();
    }
    function updateSelectColor(select) { if (!select) return; select.className = 'form-select-inline'; const f = select.dataset.field, v = select.value; if (f && v) select.classList.add(`select-${f}-${v.toLowerCase()}`); }
    function saveInlineField(el) { fetch(`${URLS.projectBase}${el.dataset.projectId}/update_inline/`, { method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrftoken}, body: JSON.stringify({ field: el.dataset.field, value: el.value }) }).then(res => res.json()).then(data => { if (data.status === 'ok') showToast('Progetto aggiornato!'); else showToast(`Errore: ${data.message}`, 'error'); }).catch(e => showToast('Errore di connessione.','error'));}

    // ... (Il resto del file rimane identico fino alla fine)
    const tooltipTriggerList = Array.from(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.forEach(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl));

    const urlParams = new URLSearchParams(window.location.search);
    const fileIdToOpen = urlParams.get('open_file_modal');
    if (fileIdToOpen) {
        showEditModal(fileIdToOpen);
    }

    document.querySelector('button[data-action="add"]')?.addEventListener('click', () => {
        resetPrintFileForm();
        printFileModal.show();
    });

    document.querySelectorAll('tr.clickable-row[data-file-id]').forEach(row => {
        row.addEventListener('click', function(e) {
            if (e.target.closest('button, a, form')) return;
            showEditModal(this.dataset.fileId);
        });
    });

    document.querySelectorAll('.form-select-inline').forEach(select => {
        updateSelectColor(select);
        select.addEventListener('change', e => {
            updateSelectColor(e.target);
            saveInlineField(e.target);
        });
    });

    document.getElementById('editProjectForm')?.addEventListener('submit', function(e) { e.preventDefault(); fetch(this.action, { method: 'POST', body: new FormData(this), headers: {'X-CSRFToken': csrftoken }}).then(res => res.json()).then(data => { if(data.status === 'ok') window.location.reload(); }); });

    const mainForm = document.getElementById('printFileForm');
    if (mainForm) {
        mainForm.addEventListener('submit', function(e) {
            e.preventDefault();
            showLoader(); // Mostra l'overlay
            const formData = new FormData(this);

            const fCont = printFileModalEl.querySelector('#filament-inputs-container');
            const fUsages = [];
            fCont.querySelectorAll('.filament-row').forEach(r => {
                const s_id = r.querySelector('.spool-select')?.value;
                const g = r.querySelector('.grams-input')?.value;
                if (s_id && g && parseFloat(g) > 0) {
                    fUsages.push({ spool_id: s_id, grams: g });
                }
            });

            const days = parseInt(mainForm.querySelector('input[name="print_time_days"]').value, 10) || 0;
            const hours = parseInt(mainForm.querySelector('input[name="print_time_hours"]').value, 10) || 0;
            const minutes = parseInt(mainForm.querySelector('input[name="print_time_minutes"]').value, 10) || 0;
            const totalMinutes = (days * 1440) + (hours * 60) + minutes;
            if (totalMinutes < 1) {
                showToast('Il tempo di stampa deve essere di almeno 1 minuto.', 'error');
                hideLoader();
                return;
            }
            if (fUsages.length === 0) {
                showToast('Devi specificare almeno un filamento e i grammi utilizzati.', 'error');
                hideLoader();
                return;
            }

            lastPlannedFilamentUsage = fUsages;
            formData.append('filament_data', JSON.stringify(fUsages));

            fetch(this.action, {
                method: 'POST',
                body: formData,
                headers: { 'X-CSRFToken': csrftoken }
            })
            .then(res => { if (!res.ok) return res.json().then(err => Promise.reject(err)); return res.json(); })
            .then(data => {
                printFileModal.hide();
                if (data.status === 'ok' || data.status === 'ok_suggestion') {
                    showToast(data.message || 'Modifiche salvate!');

                    if (data.new_print_status === 'FAILED') {
                        lastFailedFileId = this.action.match(/\/printfile\/(\d+)\/edit\//)[1];
                        if (requeueModal) requeueModal.show();
                    } else if (data.status === 'ok_suggestion') {
                        let message = '';
                        if (data.suggestion.count > 0) {
                            message += `Vuoi creare altre ${data.suggestion.count} copie? `;
                        }
                        if (data.suggestion.remainder > 0) {
                            message += `Attenzione: per completare l'ordine dovrai creare manualmente un'ultima stampa da ${data.suggestion.remainder} oggetto/i.`;
                        }

                        document.getElementById('auto-create-message').textContent = message;
                        const confirmBtn = document.getElementById('confirm-auto-create-btn');

                        if (data.suggestion.count > 0) {
                            confirmBtn.style.display = 'inline-block';
                            confirmBtn.dataset.fileId = data.suggestion.file_id;
                            confirmBtn.dataset.count = data.suggestion.count;
                        } else {
                            confirmBtn.style.display = 'none';
                        }

                        if (autoCreateModal) autoCreateModal.show();

                    } else {
                        const cleanUrl = `${window.location.pathname}?from=${referer}`;
                        setTimeout(() => window.location.href = cleanUrl, 800);
                    }
                }
            }).catch(err => {
                printFileModal.hide();
                const errorMessage = err.message || (err.errors ? Object.values(err.errors).join(' ') : 'Errore durante il salvataggio.');
                showToast(errorMessage, 'error');
            }).finally(() => {
                hideLoader(); // Nasconde l'overlay
            });
        });
    }

    document.getElementById('confirm-auto-create-btn')?.addEventListener('click', function() {
        const fileId = this.dataset.fileId;
        const count = this.dataset.count;
        showLoader();
        fetch(URLS.cloneFile, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrftoken },
            body: JSON.stringify({ file_id: fileId, count: count })
        })
        .then(res => res.json())
        .then(data => {
            showToast(data.message, data.status === 'ok' ? 'success' : 'error');
            if (autoCreateModal) autoCreateModal.hide();
            setTimeout(() => window.location.reload(), 800);
        })
        .catch(error => {
            console.error('Errore durante la clonazione:', error);
            showToast('Errore durante la clonazione dei file.', 'error');
        })
        .finally(() => { hideLoader(); });
    });

    document.getElementById('cancel-auto-create-btn')?.addEventListener('click', () => {
        window.location.reload();
    });

    const requeueModalInstance = requeueModalEl ? bootstrap.Modal.getInstance(requeueModalEl) : null;
    document.getElementById('confirm-requeue-btn')?.addEventListener('click', function() {
        if (!lastFailedFileId) return;
        showLoader();
        fetch(`${URLS.fileBase}${lastFailedFileId}/requeue/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrftoken },
            body: JSON.stringify({ filaments: lastPlannedFilamentUsage })
        })
        .then(res => res.json()).then(data => {
            showToast(data.message || 'Errore', data.status === 'ok' ? 'success' : 'error');
            if (requeueModalInstance) requeueModalInstance.hide();
            setTimeout(() => window.location.reload(), 800);
        }).finally(() => hideLoader());
    });
    document.getElementById('requeue-no-btn')?.addEventListener('click', () => window.location.reload());

    const deleteBtn = printFileModalEl.querySelector('#delete-print-file-btn');
    if(deleteBtn) {
        deleteBtn.addEventListener('click', function() {
            const fileId = this.dataset.fileId;
            const fName = printFileModalEl.querySelector('input[name="name"]').value || "questo file";
            document.getElementById('print-file-name-to-delete').textContent = fName;
            document.getElementById('deletePrintFileForm').action = `${URLS.fileBase}${fileId}/delete/`;
            if (confirmDeleteModal) confirmDeleteModal.show();
        });
    }

    document.getElementById('clone-print-file-btn')?.addEventListener('click', async function() {
        const fileId = this.dataset.fileId;
        if (!fileId) return;

        showLoader(); // Mostra l'overlay

        printFileModal.hide();

        try {
            const response = await fetch(URLS.cloneFile, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrftoken },
                body: JSON.stringify({ file_id: fileId, count: 1 })
            });
            const data = await response.json();
            showToast(data.message || 'Errore', data.status === 'ok' ? 'success' : 'error');
            if (data.status === 'ok') {
                setTimeout(() => window.location.reload(), 800);
            }
        } catch (error) {
            console.error('Errore durante la clonazione:', error);
            showToast('Errore durante la clonazione del file.', 'error');
        } finally {
            // Nasconde l'overlay solo dopo che il toast è stato mostrato e il timeout è partito
            if (! (await response.json()).status === 'ok') {
                hideLoader();
            }
        }
    });

    const deleteConfirmForm = document.getElementById('deletePrintFileForm');
    if (deleteConfirmForm) {
        deleteConfirmForm.addEventListener('submit', function(e) {
            e.preventDefault();
            showLoader();
            fetch(this.action, { method: 'POST', headers: { 'X-CSRFToken': csrftoken } }).then(res => res.json()).then(data => {
                if (data.status === 'ok') { if (confirmDeleteModal) confirmDeleteModal.hide(); window.location.reload(); }
                else { showToast('Errore durante l\'eliminazione.', 'error'); hideLoader(); }
            }).catch(e => {showToast('Errore di connessione.', 'error'); hideLoader();});
        });
    }

    const filamentContainer = printFileModalEl.querySelector('#filament-inputs-container');
    if(filamentContainer) {
        filamentContainer.addEventListener('change', function(e) {
            const target = e.target;
            if (target.classList.contains('tom-select-filament')) {
                const fId = target.value;
                const spoolSelect = target.closest('.filament-row').querySelector('.spool-select');
                spoolSelect.innerHTML = '<option>Caricamento...</option>';
                spoolSelect.disabled = true;
                if (fId) {
                    const spoolUrl = URLS.apiSpoolsUrlBase.replace('0', fId);
                    fetch(spoolUrl).then(res => res.json()).then(data => {
                        spoolSelect.innerHTML = '<option value="">Seleziona Bobina...</option>';
                        const spools = data.active_spools || [];
                        if (spools.length > 0) {
                            spools.forEach(spool => {
                                spoolSelect.innerHTML += `<option value="${spool.id}" data-remaining="${spool.remaining}">${spool.text}</option>`;
                            });
                            spoolSelect.disabled = false;
                            spoolSelect.value = spools[0].id;
                        } else {
                            spoolSelect.innerHTML = '<option value="">Nessuna bobina</option>';
                        }
                    });

                } else { spoolSelect.innerHTML = '<option value="">Scegli un filamento</option>'; spoolSelect.classList.remove('is-empty'); }
            }
            if (target.classList.contains('spool-select')) { checkWeightAndWarn(target.closest('.filament-row').querySelector('.grams-input')); }
        });
        filamentContainer.addEventListener('input', function(e) { if (e.target.classList.contains('grams-input')) { checkWeightAndWarn(e.target); } });
    }

    printFileModalEl.querySelector('#filament-count-selector')?.addEventListener('click', function(e) {
        if (e.target.tagName === 'BUTTON') { this.querySelector('.active').classList.remove('active'); e.target.classList.add('active'); updateFilamentRows(parseInt(e.target.dataset.count, 10)); }
    });

    printFileModalEl.querySelector('select[name="printer"]')?.addEventListener('change', function() {
        loadAndSelectPlate(this.value);
    });
});
