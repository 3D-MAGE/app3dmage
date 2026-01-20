document.addEventListener('DOMContentLoaded', async function () {
    // -----------------------------------------------------------------
    // SETUP INIZIALE E LETTURA DATI
    // -----------------------------------------------------------------
    const scriptUrlsTag = document.getElementById('project-detail-urls');
    if (!scriptUrlsTag) {
        console.error("Tag script con URL non trovato. Impossibile inizializzare la pagina.");
        return;
    }

    const csrftoken = getCookie('csrftoken');
    const projectId = scriptUrlsTag ? scriptUrlsTag.dataset.projectId : null;
    const referer = scriptUrlsTag ? scriptUrlsTag.dataset.referer : null;

    // --- Gestione Posizione Scroll ---
    const restoreScrollPos = () => {
        const scrollPos = sessionStorage.getItem('work_order_scroll_pos');
        if (scrollPos) {
            window.scrollTo(0, parseInt(scrollPos, 10));
            sessionStorage.removeItem('work_order_scroll_pos');
        }
    };

    const saveScrollPos = () => {
        sessionStorage.setItem('work_order_scroll_pos', window.scrollY);
    };

    const reloadWithScroll = () => {
        saveScrollPos();
        window.location.reload();
    };

    const redirectWithScroll = (url) => {
        saveScrollPos();
        window.location.href = url;
    };

    restoreScrollPos();

    // --- BLOCCAGGIO MULTI-UTENTE ---
    if (projectId) {
        const canEdit = await acquireLock('project', projectId);
        if (!canEdit) {
            // Disabilita i bottoni di salvataggio e aggiunta
            document.querySelectorAll('button[type="submit"], button[data-action="add"], .btn-primary-custom')
                .forEach(btn => {
                    btn.disabled = true;
                    btn.title = "Progetto bloccato da un altro utente";
                });
            showToast('Questo progetto è bloccato. Puoi solo visualizzarlo.', 'warning');
        } else {
            startLockHeartbeat('project', projectId);
        }
    }

    const URLS = {
        apiFilaments: scriptUrlsTag.dataset.apiFilamentsUrl,
        ajaxPlates: scriptUrlsTag.dataset.ajaxPlatesUrl,
        addFile: scriptUrlsTag.dataset.addFileUrl,
        cloneFile: scriptUrlsTag.dataset.cloneFileUrl,
        fileBase: scriptUrlsTag.dataset.fileUrlBase,
        projectBase: scriptUrlsTag.dataset.projectUrlBase,
        apiSpoolsUrlBase: scriptUrlsTag.dataset.apiSpoolsUrlBase
    };

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

    try {
        const filamentsResponse = await fetch(URLS.apiFilaments);
        if (!filamentsResponse.ok) {
            console.error("Impossibile caricare i dati dei filamenti.");
        } else {
            const allFilaments = await filamentsResponse.json();
            window.allFilaments = allFilaments; // Global fallback if needed

            // Re-initialize TomSelect functions if they were waiting for data
            // (In this script they are initialized inside functions called later)
        }
    } catch (e) {
        console.error("Errore fetch filamenti:", e);
    }

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
        statusContainer.addEventListener('click', function (e) {
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
    /**
     * MODIFICA: Funzione migliorata per determinare il colore del testo (bianco/nero)
     * in base alla luminosità dello sfondo per un contrasto ottimale.
     * @param {string} hexColor - Il colore di sfondo in formato esadecimale (es. "#RRGGBB").
     * @returns {string} Ritorna '#FFFFFF' per sfondi scuri e '#000000' per sfondi chiari.
     */
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

    /**
     * MODIFICA: Applica il colore del testo corretto a tutti gli elementi con la classe '.filament-pill'.
     */
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

    // Applica i colori corretti alle pillole già presenti nella pagina al caricamento
    applyPillContrastColor();

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
            options: window.allFilaments || [],
            create: false,
            render: {
                // MODIFICA: Renderizzazione personalizzata per le opzioni nel dropdown per garantire il contrasto
                option: function (data, escape) {
                    const textColor = getTextColorForBg(data.color_hex);
                    const textShadow = textColor === '#FFFFFF' ? '1px 1px 2px rgba(0,0,0,0.5)' : 'none';
                    return `<div style="color: ${textColor};">
                                <span class="filament-pill" style="background-color: ${data.color_hex}; color: ${textColor}; text-shadow: ${textShadow};">${escape(data.name)}</span>
                            </div>`;
                },
                // MODIFICA: Renderizzazione personalizzata per l'elemento selezionato
                item: function (data, escape) {
                    const textColor = getTextColorForBg(data.color_hex);
                    const textShadow = textColor === '#FFFFFF' ? '1px 1px 2px rgba(0,0,0,0.5)' : 'none';
                    return `<div class="filament-pill" style="background-color: ${data.color_hex}; color: ${textColor}; text-shadow: ${textShadow};">
                                ${escape(data.name)}
                             </div>`;
                }
            },
            onChange: function (value) {
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
        if (wastedWrapper) wastedWrapper.style.display = 'none';

        const actualWrapper = printFileModalEl.querySelector('#actual-quantity-wrapper');
        const actualInput = printFileModalEl.querySelector('[name="actual_quantity"]');
        if (actualWrapper) actualWrapper.style.display = 'none';
        if (actualInput) actualInput.required = false;

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

        const projectIdHiddenInput = form.querySelector('#id_work_order_hidden');
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
        if (form.querySelector('[name="project_part"]')) {
            form.querySelector('[name="project_part"]').value = data.project_part || "";
        }
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
    function saveInlineField(el) { fetch(`${URLS.projectBase}${el.dataset.projectId}/update_inline/`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrftoken }, body: JSON.stringify({ field: el.dataset.field, value: el.value }) }).then(res => res.json()).then(data => { if (data.status === 'ok') showToast('Progetto aggiornato!'); else showToast(`Errore: ${data.message}`, 'error'); }).catch(e => showToast('Errore di connessione.', 'error')); }

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
        row.addEventListener('click', function (e) {
            // Impedisce l'apertura del modale se si clicca su select, bottoni, link o celle contrassegnate
            if (e.target.closest('button, a, form, select, .ts-control, [data-no-modal="true"]')) return;
            showEditModal(this.dataset.fileId);
        });
    });

    function updatePrintFileSelectColor(select) {
        if (!select) return;
        const status = select.value.toLowerCase();
        select.classList.remove('select-status-todo', 'select-status-printing', 'select-status-done', 'select-status-failed');
        select.classList.add(`select-status-${status}`);
    }

    document.querySelectorAll('.print-file-status-select').forEach(select => {
        updatePrintFileSelectColor(select);

        // Impedisce l'apertura del modale riga quando si clicca sul menu a tendina
        select.addEventListener('click', e => {
            e.stopPropagation();
        });
        select.addEventListener('mousedown', e => {
            e.stopPropagation();
        });

        select.addEventListener('change', function (e) {
            e.stopPropagation();
            const fileId = this.dataset.fileId;
            const newStatus = this.value;

            showLoader();
            fetch(`/printfile/${fileId}/set_status/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrftoken
                },
                body: JSON.stringify({ new_status: newStatus })
            })
                .then(res => res.json())
                .then(data => {
                    if (data.status === 'ok') {
                        showToast('Stato file aggiornato!');
                        updatePrintFileSelectColor(this);

                        // Se abbiamo nuovi dati sul progresso, aggiorniamo la barra
                        if (data.new_progress_percentage !== undefined) {
                            const progressBar = document.getElementById('main-progress-bar');
                            const progressLabel = document.getElementById('progress-text-label');
                            if (progressBar) progressBar.style.width = `${data.new_progress_percentage}%`;
                            if (progressLabel) progressLabel.textContent = data.new_progress;
                        }

                        // Se lo stato è DONE o FAILED, forse è meglio ricaricare per aggiornare tutti i tempi e grammi
                        if (newStatus === 'DONE' || newStatus === 'FAILED') {
                            setTimeout(() => reloadWithScroll(), 800);
                        }
                    } else {
                        showToast(`Errore: ${data.message}`, 'error');
                    }
                })
                .catch(err => {
                    console.error('Errore status file:', err);
                    showToast('Errore di connessione.', 'error');
                })
                .finally(() => hideLoader());
        });
    });

    document.querySelectorAll('.form-select-inline').forEach(select => {
        updateSelectColor(select);
        select.addEventListener('change', e => {
            updateSelectColor(e.target);
            saveInlineField(e.target);
        });
    });

    document.getElementById('editProjectForm')?.addEventListener('submit', function (e) { e.preventDefault(); fetch(this.action, { method: 'POST', body: new FormData(this), headers: { 'X-CSRFToken': csrftoken } }).then(res => res.json()).then(data => { if (data.status === 'ok') reloadWithScroll(); }); });

    const mainForm = document.getElementById('printFileForm');
    if (mainForm) {
        mainForm.addEventListener('submit', function (e) {
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
                            setTimeout(() => redirectWithScroll(cleanUrl), 800);
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

    document.getElementById('confirm-auto-create-btn')?.addEventListener('click', function () {
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
                setTimeout(() => reloadWithScroll(), 800);
            })
            .catch(error => {
                console.error('Errore durante la clonazione:', error);
                showToast('Errore durante la clonazione dei file.', 'error');
            })
            .finally(() => { hideLoader(); });
    });

    document.getElementById('cancel-auto-create-btn')?.addEventListener('click', () => {
        reloadWithScroll();
    });

    const requeueModalInstance = requeueModalEl ? bootstrap.Modal.getInstance(requeueModalEl) : null;
    document.getElementById('confirm-requeue-btn')?.addEventListener('click', function () {
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
                setTimeout(() => reloadWithScroll(), 800);
            }).finally(() => hideLoader());
    });
    document.getElementById('requeue-no-btn')?.addEventListener('click', () => reloadWithScroll());

    const deleteBtn = printFileModalEl.querySelector('#delete-print-file-btn');
    if (deleteBtn) {
        deleteBtn.addEventListener('click', function () {
            const fileId = this.dataset.fileId;
            const fName = printFileModalEl.querySelector('input[name="name"]').value || "questo file";
            document.getElementById('print-file-name-to-delete').textContent = fName;
            document.getElementById('deletePrintFileForm').action = `${URLS.fileBase}${fileId}/delete/`;
            if (confirmDeleteModal) confirmDeleteModal.show();
        });
    }

    document.getElementById('clone-print-file-btn')?.addEventListener('click', async function () {
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
                setTimeout(() => reloadWithScroll(), 800);
            } else {
                hideLoader();
            }
        } catch (error) {
            console.error('Errore durante la clonazione:', error);
            showToast('Errore durante la clonazione del file.', 'error');
            hideLoader();
        }
    });

    const deleteConfirmForm = document.getElementById('deletePrintFileForm');
    if (deleteConfirmForm) {
        deleteConfirmForm.addEventListener('submit', function (e) {
            e.preventDefault();
            showLoader();
            fetch(this.action, { method: 'POST', headers: { 'X-CSRFToken': csrftoken } }).then(res => res.json()).then(data => {
                if (data.status === 'ok') { if (confirmDeleteModal) confirmDeleteModal.hide(); reloadWithScroll(); }
                else { showToast('Errore durante l\'eliminazione.', 'error'); hideLoader(); }
            }).catch(e => { showToast('Errore di connessione.', 'error'); hideLoader(); });
        });
    }

    const filamentContainer = printFileModalEl.querySelector('#filament-inputs-container');
    if (filamentContainer) {
        filamentContainer.addEventListener('change', function (e) {
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
        filamentContainer.addEventListener('input', function (e) { if (e.target.classList.contains('grams-input')) { checkWeightAndWarn(e.target); } });
    }

    printFileModalEl.querySelector('#filament-count-selector')?.addEventListener('click', function (e) {
        if (e.target.tagName === 'BUTTON') { this.querySelector('.active').classList.remove('active'); e.target.classList.add('active'); updateFilamentRows(parseInt(e.target.dataset.count, 10)); }
    });

    printFileModalEl.querySelector('select[name="printer"]')?.addEventListener('change', function () {
        loadAndSelectPlate(this.value);
    });

    function reopenProject(projectId) {
        if (!confirm('Sei sicuro di voler riaprire il progetto? Gli oggetti a magazzino invenduti verranno rimossi.')) {
            return;
        }

        // Costruisci l'URL dinamicamente o usa un data-attribute se preferisci
        const url = `/project/${projectId}/reopen/`;

        fetch(url, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCookie('csrftoken'),
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({})
        })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'ok') {
                    // Ricarica la pagina per mostrare il nuovo stato
                    reloadWithScroll();
                } else {
                    alert('Errore: ' + data.message);
                }
            })
            .catch(error => {
                console.error('Errore:', error);
                alert('Si è verificato un errore di connessione.');
            });
    }

    /**
     * Gestisce il controllo della riapertura, verificando se ci sono oggetti venduti.
     * @param {number} projectId 
     */
    window.handleReopenCheck = function (projectId) {
        fetch(`/project/${projectId}/reopen/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCookie('csrftoken'),
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({})
        })
            .then(res => res.json())
            .then(data => {
                if (data.status === 'ok') {
                    reloadWithScroll();
                } else if (data.status === 'sold') {
                    const soldModal = new bootstrap.Modal(document.getElementById('soldItemsModal'));
                    soldModal.show();
                } else {
                    showToast(data.message, 'error');
                }
            })
            .catch(err => {
                console.error("Reopen error:", err);
                showToast("Errore durante il controllo riapertura.", 'error');
            });
    };

    // -----------------------------------------------------------------
    // REOPEN AND REPRINT
    // -----------------------------------------------------------------
    const confirmReopenBtn = document.getElementById('confirmReopenBtn');
    const confirmReprintBtn = document.getElementById('confirmReprintBtn');
    const reopenModalEl = document.getElementById('reopenConfirmModal');
    const reprintModalEl = document.getElementById('reprintConfirmModal');

    if (confirmReopenBtn) {
        confirmReopenBtn.addEventListener('click', function () {
            // Nasconde il modale di conferma prima di procedere
            if (reopenModalEl) {
                const instance = bootstrap.Modal.getInstance(reopenModalEl);
                if (instance) instance.hide();
            }
            // Chiama la funzione di logica esistente
            handleReopenCheck(projectId);
        });
    }

    if (confirmReprintBtn) {
        confirmReprintBtn.addEventListener('click', function () {
            const form = document.getElementById('reprintOrderForm');
            if (form) {
                confirmReprintBtn.disabled = true;
                confirmReprintBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Ristampa...';
                form.submit();
            }
        });
    }

    // -----------------------------------------------------------------
    // SYNC TO MASTER
    // -----------------------------------------------------------------
    const confirmSyncBtn = document.getElementById('confirmSyncToMasterBtn');
    const syncModalEl = document.getElementById('syncMasterConfirmModal');
    const syncModal = syncModalEl ? new bootstrap.Modal(syncModalEl) : null;

    let activeSyncUrl = null;

    document.querySelectorAll('.syncToMasterBtn').forEach(btn => {
        btn.addEventListener('click', function () {
            activeSyncUrl = this.dataset.url;
            if (syncModal) syncModal.show();
        });
    });

    if (confirmSyncBtn) {
        confirmSyncBtn.addEventListener('click', function () {
            if (!activeSyncUrl) return;
            confirmSyncBtn.disabled = true;
            confirmSyncBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Sincronizzazione...';

            fetch(activeSyncUrl, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrftoken,
                    'Content-Type': 'application/json'
                }
            })
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'ok') {
                        showToast(data.message, 'success');
                        syncModal.hide();
                        // Chiudiamo anche il modale di modifica se presente
                        const editModalEl = document.getElementById('editProjectModal');
                        if (editModalEl) {
                            const instance = bootstrap.Modal.getInstance(editModalEl);
                            if (instance) instance.hide();
                        }
                        setTimeout(() => reloadWithScroll(), 1000);
                    } else {
                        showToast(data.message, 'danger');
                    }
                })
                .catch(error => {
                    showToast('Errore durante la sincronizzazione.', 'danger');
                    console.error('Sync error:', error);
                })
                .finally(() => {
                    confirmSyncBtn.disabled = false;
                    confirmSyncBtn.innerHTML = '<i class="bi bi-check-circle me-1"></i> Sì, Aggiorna Master';
                });
        });
    }

    // -----------------------------------------------------------------
    // PROMOTE TO MASTER
    // -----------------------------------------------------------------
    const confirmPromoteBtn = document.getElementById('confirmPromoteToMasterBtn');
    const promoteModalEl = document.getElementById('promoteMasterConfirmModal');
    const promoteModal = promoteModalEl ? new bootstrap.Modal(promoteModalEl) : null;

    let activePromoteUrl = null;

    document.querySelectorAll('.promoteToMasterBtn').forEach(btn => {
        btn.addEventListener('click', function () {
            activePromoteUrl = this.dataset.url;
            if (promoteModal) promoteModal.show();
        });
    });

    if (confirmPromoteBtn) {
        confirmPromoteBtn.addEventListener('click', function () {
            if (!activePromoteUrl) return;
            confirmPromoteBtn.disabled = true;
            confirmPromoteBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Promozione...';

            fetch(activePromoteUrl, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrftoken,
                    'Content-Type': 'application/json'
                }
            })
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'ok') {
                        showToast(data.message, 'success');
                        if (promoteModal) promoteModal.hide();
                        // Chiudiamo anche il modale di modifica se presente
                        const editModalEl = document.getElementById('editProjectModal');
                        if (editModalEl) {
                            const instance = bootstrap.Modal.getInstance(editModalEl);
                            if (instance) instance.hide();
                        }
                        setTimeout(() => reloadWithScroll(), 1000);
                    } else {
                        showToast(data.message, 'danger');
                    }
                })
                .catch(error => {
                    showToast('Errore durante la promozione.', 'danger');
                    console.error('Promote error:', error);
                })
                .finally(() => {
                    confirmPromoteBtn.disabled = false;
                    confirmPromoteBtn.innerHTML = '<i class="bi bi-check-circle me-1"></i> Sì, Promuovi a Master';
                });
        });
    }

    // -----------------------------------------------------------------
    // COMPLETE PROJECT MULTI-OUTPUT LOGIC
    // -----------------------------------------------------------------
    const completeProjectModalEl = document.getElementById('completeProjectModal');
    if (completeProjectModalEl) {
        completeProjectModalEl.addEventListener('show.bs.modal', function () {
            // Controlla se ci sono file non finiti
            const statusSelects = document.querySelectorAll('.print-file-status-select');
            let hasUnfinished = false;
            statusSelects.forEach(select => {
                const status = select.value;
                if (status === 'TODO' || status === 'PRINTING') {
                    hasUnfinished = true;
                }
            });

            const partialWarning = document.getElementById('partial-completion-warning');
            if (partialWarning) {
                partialWarning.style.display = hasUnfinished ? 'block' : 'none';
            }
        });
    }

    const completeProjectForm = document.getElementById('completeProjectForm');
    if (completeProjectForm) {
        completeProjectForm.addEventListener('submit', function (e) {
            const outputsScroll = [];
            const rows = document.querySelectorAll('.completion-output-row');
            let totalQty = 0;

            rows.forEach(row => {
                const name = row.querySelector('.output-name-input').value;
                const qty = parseInt(row.querySelector('.output-qty-input').value) || 0;
                if (qty > 0 && name.trim()) {
                    outputsScroll.push({ name: name, quantity: qty });
                    totalQty += qty;
                }
            });

            if (outputsScroll.length === 0) {
                e.preventDefault();
                alert("Inserisci almeno una quantità valida per completare l'ordine.");
                return;
            }

            document.getElementById('outputs_data_input').value = JSON.stringify(outputsScroll);
        });

        // Validazione istantanea quantità totale (opzionale)
        const qtyInputs = completeProjectForm.querySelectorAll('.output-qty-input');
        const maxTotal = parseInt(qtyInputs[0]?.max) || 999999;
        const warning = document.getElementById('completion-qty-warning');

        qtyInputs.forEach(input => {
            input.addEventListener('input', () => {
                let currentTotal = 0;
                qtyInputs.forEach(i => currentTotal += (parseInt(i.value) || 0));
                if (warning) warning.style.display = currentTotal > maxTotal ? 'block' : 'none';
            });
        });
    }

    // -----------------------------------------------------------------
    // BACK BUTTON LOGIC
    // -----------------------------------------------------------------
    const backBtn = document.getElementById('back-dashboard-btn');
    if (backBtn) {
        const lastUrl = localStorage.getItem('last_dashboard_url');
        if ((referer === 'active' || referer === 'completed') && lastUrl && lastUrl.startsWith('http')) {
            backBtn.href = lastUrl;
        } else if (referer === 'queue') {
            backBtn.href = scriptUrlsTag.dataset.urlQueue;
        } else if (referer === 'kanban') {
            backBtn.href = scriptUrlsTag.dataset.urlKanban;
        }
    }
});
