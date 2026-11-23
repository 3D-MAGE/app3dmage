document.addEventListener('DOMContentLoaded', function () {
    // 1. Logic for Master Template Files (Add/Edit)
    const modal = document.getElementById('masterFileModal');
    if (modal) {
        const form = document.getElementById('masterFileForm');
        const title = document.getElementById('masterFileModalTitle');
        const printerSelect = document.getElementById('id_printer');
        const plateSelect = document.getElementById('id_plate');
        const filamentContainer = document.getElementById('master-filament-inputs-container');
        const addFilamentBtn = document.getElementById('add-master-filament-btn');
        const filamentDataInput = document.getElementById('master_filament_data_input');

        // Helper for colors
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

        // Applica i colori corretti alle pillole già presenti nella pagina al caricamento
        applyPillContrastColor();

        const partSelect = document.getElementById('id_project_parts');
        let partTs = null;

        if (partSelect) {
            partTs = new TomSelect(partSelect, {
                plugins: ['remove_button'],
                create: false,
                persist: false,
            });
        }

        modal.addEventListener('show.bs.modal', function (event) {
            const button = event.relatedTarget;
            const action = button.getAttribute('data-action');

            if (action === 'add') {
                title.textContent = 'Aggiungi Template File';
                form.action = modal.dataset.urlAdd;
                form.reset();
                form.querySelector('[name="estimated_time_days"]').value = 0;
                form.querySelector('[name="estimated_time_hours"]').value = 0;
                form.querySelector('[name="estimated_time_minutes"]').value = 0;
                form.querySelector('[name="produced_quantity"]').value = 1;

                const partId = button.getAttribute('data-part-id');
                if (partTs) {
                    partTs.clear();
                    if (partId) {
                        partTs.setValue([partId]);
                    }
                }

                plateSelect.innerHTML = '<option value="">Seleziona Piatto</option>';
                filamentContainer.innerHTML = '';
                addFilamentRow();
            } else {
                title.textContent = 'Modifica Template File';
                const fileId = button.getAttribute('data-file-id');
                form.action = `/library/file/${fileId}/edit/`;

                fetch(`/library/file/${fileId}/details/`)
                    .then(r => r.json())
                    .then(data => {
                        form.querySelector('[name="name"]').value = data.name;
                        form.querySelector('[name="estimated_time_days"]').value = data.estimated_time_days;
                        form.querySelector('[name="estimated_time_hours"]').value = data.estimated_time_hours;
                        form.querySelector('[name="estimated_time_minutes"]').value = data.estimated_time_minutes;
                        form.querySelector('[name="produced_quantity"]').value = data.produced_quantity || 1;

                        if (partTs && data.project_parts) {
                            partTs.setValue(data.project_parts);
                        } else if (partTs) {
                            partTs.clear();
                        }

                        printerSelect.value = data.printer;

                        if (data.printer) {
                            loadPlates(data.printer, data.plate);
                        }

                        filamentContainer.innerHTML = '';
                        if (data.filaments && data.filaments.length > 0) {
                            data.filaments.forEach(f => addFilamentRow(f.filament_id, f.grams));
                        } else {
                            addFilamentRow();
                        }
                    })
                    .catch(err => console.error("Errore caricamento dettagli:", err));
            }
        });

        function loadPlates(printerId, selectedPlateId = null) {
            if (!printerId) {
                plateSelect.innerHTML = '<option value="">Seleziona Piatto</option>';
                return;
            }
            fetch(`/ajax/load-plates/?printer_id=${printerId}`)
                .then(r => r.json())
                .then(data => {
                    let html = '<option value="">Seleziona Piatto</option>';
                    data.forEach(p => {
                        html += `<option value="${p.id}" ${selectedPlateId == p.id ? 'selected' : ''}>${p.name}</option>`;
                    });
                    plateSelect.innerHTML = html;
                })
                .catch(err => console.error("Errore caricamento piatti:", err));
        }

        // Ensure plate loading works on manual change
        if (printerSelect) {
            printerSelect.addEventListener('change', function () {
                loadPlates(this.value);
            });
        }

        // --- FILTERING LOGIC ---
        const filterRadios = document.querySelectorAll('input[name="printer-filter"]');
        filterRadios.forEach(radio => {
            radio.addEventListener('change', function () {
                const filterValue = (this.value || '').toLowerCase().trim();
                console.log("Filtering by:", filterValue);
                const sections = document.querySelectorAll('.part-section');

                sections.forEach(section => {
                    const rows = section.querySelectorAll('.master-file-row');
                    const noFilesRow = section.querySelector('.no-files-row');
                    let visibleInPart = 0;

                    rows.forEach(row => {
                        // Use data-printer-id which should contain the ID or 'none'
                        const printerId = (row.getAttribute('data-printer-id') || 'none').toString();

                        if (filterValue === 'all' || printerId === filterValue) {
                            row.classList.remove('d-none');
                            visibleInPart++;
                        } else {
                            row.classList.add('d-none');
                        }
                    });

                    // Show/hide "No files" row based on visibility of regular rows
                    if (noFilesRow) {
                        if (visibleInPart === 0 && rows.length > 0) {
                            noFilesRow.classList.remove('d-none');
                        } else {
                            noFilesRow.classList.add('d-none');
                        }
                    }
                });
            });
        });

        if (addFilamentBtn) {
            addFilamentBtn.addEventListener('click', () => addFilamentRow());
        }

        // We assume allFilamentsData is available globally from the template script block
        // or we could pass it via data attribute too.
        function addFilamentRow(filamentId = '', grams = '') {
            const row = document.createElement('div');
            row.className = 'row mb-3 filament-row align-items-center';
            row.innerHTML = `
                <div class="col-7">
                    <select class="form-select select-filament-ts w-100" placeholder="Cerca codice, colore o materiale..."></select>
                </div>
                <div class="col-3">
                    <input type="number" class="form-control input-grams bg-dark text-white" value="${grams}" step="0.01" min="0" placeholder="grammi">
                </div>
                <div class="col-2 text-end">
                    <button type="button" class="btn btn-outline-danger btn-sm remove-filament-btn"><i class="bi bi-x"></i></button>
                </div>
            `;
            filamentContainer.appendChild(row);

            const selectEl = row.querySelector('.select-filament-ts');
            try {
                const allFilamentsData = JSON.parse(document.getElementById('all-filaments-data').textContent);
                const ts = new TomSelect(selectEl, {
                    valueField: 'id',
                    labelField: 'name',
                    searchField: ['name', 'color_name', 'material', 'color_code', 'brand'],
                    maxOptions: null,
                    placeholder: 'Cerca codice, colore o materiale...',
                    options: allFilamentsData || [],
                    create: false,
                    render: {
                        option: function (data, escape) {
                            const textColor = getTextColorForBg(data.color_hex);
                            const textShadow = textColor === '#FFFFFF' ? '1px 1px 2px rgba(0,0,0,0.5)' : 'none';
                            const colorLabel = data.color_name ? `<span class="ms-2 small text-white-50">${escape(data.color_name)}</span>` : '';
                            return `<div class="d-flex align-items-center">
                                        <span class="filament-pill mb-0" style="background-color: ${data.color_hex}; color: ${textColor}; text-shadow: ${textShadow}; border: 1px solid #444;">${escape(data.name)}</span>
                                        ${colorLabel}
                                    </div>`;
                        },
                        item: function (data, escape) {
                            const textColor = getTextColorForBg(data.color_hex);
                            const textShadow = textColor === '#FFFFFF' ? '1px 1px 2px rgba(0,0,0,0.5)' : 'none';
                            return `<div class="filament-pill" title="${escape(data.color_name || '')}" style="background-color: ${data.color_hex}; color: ${textColor}; text-shadow: ${textShadow}; border: 1px solid #444;">
                                        ${escape(data.name)}
                                    </div>`;
                        }
                    }
                });

                if (filamentId) {
                    ts.setValue(filamentId);
                }

                row.querySelector('.remove-filament-btn').addEventListener('click', () => {
                    ts.destroy();
                    row.remove();
                });
            } catch (e) {
                console.error("Errore TomSelect:", e);
            }
        }

        form.addEventListener('submit', function (e) {
            const rows = filamentContainer.querySelectorAll('.filament-row');
            const data = [];
            rows.forEach(r => {
                const selectEl = r.querySelector('.select-filament-ts');
                const fId = selectEl ? selectEl.value : '';
                const grams = r.querySelector('.input-grams').value;
                if (fId && grams) {
                    data.push({ filament_id: fId, grams: parseFloat(grams) });
                }
            });
            filamentDataInput.value = JSON.stringify(data);
        });
    }

    // 2. Logic for Create Order Modal (Enhanced with Split Prints/Batches)
    const createModal = document.getElementById('createOrderModal');
    if (createModal) {
        const createOrderForm = document.getElementById('createOrderForm');
        const batchContainer = document.getElementById('batches-container');
        const btnAddBatch = document.getElementById('btn-add-batch');
        const batchDataInput = document.getElementById('batch_data_input');
        const createOrderText = document.getElementById('createOrderText');
        const summaryContainer = document.getElementById('order-creation-summary');
        const summaryList = document.getElementById('summary-list');

        let projectName = '';
        let baseQty = 1;
        let partsInfo = []; // Array di {id, name, printers: [{id, name, tag}]}

        createModal.addEventListener('show.bs.modal', function (event) {
            const button = event.relatedTarget;
            const projectId = button.getAttribute('data-project-id');
            projectName = button.getAttribute('data-project-name');
            baseQty = parseInt(button.getAttribute('data-base-qty')) || 1;

            createOrderForm.action = `/library/${projectId}/create_order/`;
            createOrderText.innerHTML = `Stai configurando la creazione dell'ordine per <strong>${projectName}</strong>. Puoi dividere la produzione su più stampanti aggiungendo ulteriori set.`;

            // 1. Esplora le parti e le stampanti disponibili nella pagina
            partsInfo = [];
            document.querySelectorAll('.part-section').forEach(section => {
                const partId = section.getAttribute('data-part-id');
                const partName = section.querySelector('h6').textContent.trim();
                const printersInPartMap = new Map();
                const filesInPart = [];

                section.querySelectorAll('.master-file-row').forEach(row => {
                    const id = row.getAttribute('data-printer-id');
                    const tag = row.getAttribute('data-printer');
                    const name = row.getAttribute('data-printer-name');
                    const fileId = row.getAttribute('data-file-id');
                    const fileName = row.querySelector('td')?.textContent.trim() || 'File';
                    const producedQty = parseInt(row.getAttribute('data-produced-qty')) || 1;
                    const estimatedTime = row.querySelectorAll('td')[1]?.textContent.trim() || '';

                    if (fileId) {
                        filesInPart.push({
                            id: fileId,
                            name: fileName,
                            printerId: (id && id !== 'none') ? id : null,
                            printerName: name || tag,
                            printerTag: tag,
                            producedQty: producedQty,
                            estimatedTime: estimatedTime
                        });
                    }

                    if (id && id !== 'none') {
                        printersInPartMap.set(id, { id, name: name || tag, tag: tag });
                    }
                });

                if (filesInPart.length > 0) {
                    partsInfo.push({
                        id: partId,
                        name: partName,
                        printers: Array.from(printersInPartMap.values()),
                        files: filesInPart
                    });
                }
            });

            // 2. Resetta e aggiungi il primo set
            batchContainer.innerHTML = '';
            addBatch(baseQty);
            updateOrderSummary();
        });

        function addBatch(qty = 1) {
            const batchIndex = batchContainer.querySelectorAll('.order-batch-item').length;
            const batchId = Date.now(); // ID temporaneo univoco per i radio button
            const batchDiv = document.createElement('div');
            batchDiv.className = 'order-batch-item card bg-dark border-secondary mb-3 p-3';
            batchDiv.setAttribute('data-batch-index', batchIndex);

            let partsHtml = '';
            partsInfo.forEach(part => {
                let printerOptionsHtml = `
                    <div class="d-flex flex-wrap gap-2 mb-2">
                        <div class="printer-box-wrapper">
                            <input type="radio" class="btn-check printer-radio" name="printer_part_${part.id}_batch_${batchId}" id="skip_${part.id}_${batchId}" value="skip" autocomplete="off" data-part-id="${part.id}" data-batch-id="${batchId}">
                            <label class="btn btn-outline-secondary btn-xs" for="skip_${part.id}_${batchId}">Salta</label>
                        </div>
                `;

                part.printers.forEach((printer, pIdx) => {
                    const uniqueId = `b${batchId}_p${part.id}_pr${printer.id}`;
                    const isChecked = pIdx === 0 ? 'checked' : '';
                    printerOptionsHtml += `
                        <div class="printer-box-wrapper">
                            <input type="radio" class="btn-check printer-radio" name="printer_part_${part.id}_batch_${batchId}" id="${uniqueId}" value="${printer.id}" autocomplete="off" ${isChecked} data-part-id="${part.id}" data-printer-id="${printer.id}" data-batch-id="${batchId}">
                            <label class="btn btn-outline-orange btn-xs" for="${uniqueId}">${printer.name}</label>
                        </div>
                    `;
                });
                printerOptionsHtml += '</div>';

                // File variants per printer
                let fileVariantsHtml = '';
                part.printers.forEach((printer, pIdx) => {
                    const printerFiles = part.files.filter(f => !f.printerId || String(f.printerId) === String(printer.id));
                    const isPrinterChecked = pIdx === 0;

                    if (printerFiles.length > 1) {
                        // Scegli il file migliore in base a qty
                        let bestMatchId = printerFiles[0].id;
                        const exactMatch = printerFiles.find(f => f.producedQty === qty);
                        if (exactMatch) {
                            bestMatchId = exactMatch.id;
                        } else {
                            const smallerOrEqual = printerFiles.filter(f => f.producedQty <= qty).sort((a, b) => b.producedQty - a.producedQty);
                            if (smallerOrEqual.length > 0) {
                                bestMatchId = smallerOrEqual[0].id;
                            }
                        }

                        let radiosHtml = '';
                        printerFiles.forEach(f => {
                            const fChecked = (f.id === bestMatchId) ? 'checked' : '';
                            const fUniqueId = `f_${f.id}_b${batchId}_p${part.id}`;
                            radiosHtml += `
                                <div class="file-box-wrapper">
                                    <input type="radio" class="btn-check file-variant-radio" name="file_part_${part.id}_batch_${batchId}" id="${fUniqueId}" value="${f.id}" data-produced-qty="${f.producedQty}" ${fChecked} ${isPrinterChecked ? '' : 'disabled'}>
                                    <label class="btn btn-outline-info btn-xs" for="${fUniqueId}">
                                        ${f.name} <span class="badge bg-secondary ms-1">${f.producedQty} pz</span>
                                        <span class="text-white-50 ms-1 small">(${f.estimatedTime})</span>
                                    </label>
                                </div>
                            `;
                        });

                        fileVariantsHtml += `
                            <div class="file-variant-wrapper ms-1 ps-2 border-start border-warning" id="files_wrap_${part.id}_pr_${printer.id}_${batchId}" style="${isPrinterChecked ? '' : 'display: none;'}">
                                <div class="small text-warning-emphasis mb-1"><i class="bi bi-layers me-1"></i>Piatto G-code:</div>
                                <div class="d-flex flex-wrap gap-2">
                                    ${radiosHtml}
                                </div>
                            </div>
                        `;
                    } else if (printerFiles.length === 1) {
                        const singleFile = printerFiles[0];
                        fileVariantsHtml += `
                            <input type="hidden" class="single-file-input" name="file_part_${part.id}_batch_${batchId}" value="${singleFile.id}" data-produced-qty="${singleFile.producedQty}" data-printer-id="${printer.id}" ${isPrinterChecked ? '' : 'disabled'}>
                        `;
                    }
                });

                partsHtml += `
                    <div class="mb-3 part-selection-row" data-part-id="${part.id}">
                        <label class="small text-white-50 d-block mb-1">${part.name}</label>
                        ${printerOptionsHtml}
                        ${fileVariantsHtml}
                    </div>
                `;
            });

            const showRemove = batchIndex > 0;
            batchDiv.innerHTML = `
                <div class="d-flex justify-content-between align-items-center mb-3">
                    <h6 class="text-success mb-0"><i class="bi bi-box-seam me-2"></i>Lotto #${batchIndex + 1}</h6>
                    ${showRemove ? '<button type="button" class="btn btn-link btn-sm text-danger p-0 btn-remove-batch"><i class="bi bi-trash"></i> Rimuovi</button>' : ''}
                </div>
                <div class="row mb-1">
                    <div class="col-12">
                        <span class="badge bg-dark border border-secondary text-white-50 p-2">
                             <i class="bi bi-stack me-1"></i>Quantità: <strong>${qty} pezzi</strong>
                        </span>
                        <input type="hidden" class="batch-qty-input" value="${qty}">
                    </div>
                </div>
                <div class="batch-parts-selection">
                    ${partsHtml}
                </div>
            `;

            batchContainer.appendChild(batchDiv);

            // Listeners
            if (showRemove) {
                batchDiv.querySelector('.btn-remove-batch').addEventListener('click', () => {
                    batchDiv.remove();
                    reindexBatches();
                    updateOrderSummary();
                });
            }

            // Gestione cambio stampante per mostrare/nascondere file corretti
            batchDiv.querySelectorAll('.printer-radio').forEach(pRad => {
                pRad.addEventListener('change', function () {
                    const pRow = this.closest('.part-selection-row');
                    const partId = this.getAttribute('data-part-id');
                    const printerId = this.getAttribute('data-printer-id');
                    const isSkip = this.value === 'skip';

                    // Disabilita tutti i file della parte
                    pRow.querySelectorAll('.file-variant-wrapper').forEach(w => {
                        w.style.display = 'none';
                        w.querySelectorAll('input').forEach(inp => inp.disabled = true);
                    });
                    pRow.querySelectorAll('.single-file-input').forEach(inp => inp.disabled = true);

                    if (!isSkip && printerId) {
                        const targetWrap = pRow.querySelector(`#files_wrap_${partId}_pr_${printerId}_${batchId}`);
                        if (targetWrap) {
                            targetWrap.style.display = 'block';
                            targetWrap.querySelectorAll('input').forEach(inp => inp.disabled = false);
                            // Se nessun radio è checked, checka il primo
                            if (!targetWrap.querySelector('input:checked')) {
                                const firstRadio = targetWrap.querySelector('input[type="radio"]');
                                if (firstRadio) firstRadio.checked = true;
                            }
                        }
                        const targetSingle = pRow.querySelector(`.single-file-input[data-printer-id="${printerId}"]`);
                        if (targetSingle) {
                            targetSingle.disabled = false;
                        }
                    }
                    updateOrderSummary();
                });
            });

            batchDiv.querySelector('.batch-qty-input').addEventListener('input', updateOrderSummary);
            batchDiv.querySelectorAll('.file-variant-radio').forEach(fRad => {
                fRad.addEventListener('change', updateOrderSummary);
            });
        }

        function reindexBatches() {
            batchContainer.querySelectorAll('.order-batch-item').forEach((item, idx) => {
                item.setAttribute('data-batch-index', idx);
                const title = item.querySelector('h6');
                if (title) title.innerHTML = `<i class="bi bi-box-seam me-2"></i>Lotto #${idx + 1}`;
            });
        }

        btnAddBatch.addEventListener('click', () => {
            addBatch(baseQty);
            updateOrderSummary();
        });

        function updateOrderSummary() {
            let totalQty = 0;
            let totalFilesCount = 0;
            const batchSummaries = [];

            const batches = batchContainer.querySelectorAll('.order-batch-item');
            batches.forEach((batchDiv, idx) => {
                const qty = parseInt(batchDiv.querySelector('.batch-qty-input').value) || 0;
                totalQty += qty;

                let batchFiles = 0;
                batchDiv.querySelectorAll('.part-selection-row').forEach(row => {
                    const checkedPrinter = row.querySelector('.printer-radio:checked');
                    if (!checkedPrinter || checkedPrinter.value === 'skip') return;

                    const activeFile = row.querySelector('.file-variant-radio:not(:disabled):checked, .single-file-input:not(:disabled)');
                    if (activeFile) {
                        const producedQty = parseInt(activeFile.getAttribute('data-produced-qty')) || 1;
                        batchFiles += Math.ceil(qty / producedQty);
                    }
                });

                totalFilesCount += batchFiles;
                if (qty > 0) {
                    batchSummaries.push(`Lotto #${idx + 1}: <strong>${qty} pezzi</strong> (${batchFiles} file)`);
                }
            });

            if (totalQty > 0) {
                summaryContainer.classList.remove('d-none');
                summaryList.innerHTML = `
                    <li>Progetto: <strong>${projectName}</strong></li>
                    <li>Quantità Totale Ordine: <strong>${totalQty}</strong></li>
                    ${batchSummaries.map(s => `<li>${s}</li>`).join('')}
                    <hr class="my-2 border-secondary">
                    <p class="mt-2 text-muted mb-0"><i class="bi bi-info-circle me-1 text-muted"></i>Verranno creati <strong>${totalFilesCount}</strong> File di Stampa in totale.</p>
                `;
            } else {
                summaryContainer.classList.add('d-none');
            }
        }

        createOrderForm.addEventListener('submit', function (e) {
            e.preventDefault();

            const batches = [];
            batchContainer.querySelectorAll('.order-batch-item').forEach(batchDiv => {
                const qty = parseInt(batchDiv.querySelector('.batch-qty-input').value) || 0;
                const printerSelection = {};
                const fileSelection = {};

                batchDiv.querySelectorAll('.part-selection-row').forEach(row => {
                    const partId = row.getAttribute('data-part-id');
                    const checkedPrinter = row.querySelector('.printer-radio:checked');
                    if (checkedPrinter) {
                        printerSelection[partId] = checkedPrinter.value;
                    }
                    const activeFile = row.querySelector('.file-variant-radio:not(:disabled):checked, .single-file-input:not(:disabled)');
                    if (activeFile && checkedPrinter && checkedPrinter.value !== 'skip') {
                        fileSelection[partId] = activeFile.value;
                    }
                });

                if (qty > 0) {
                    batches.push({ quantity: qty, printers: printerSelection, files: fileSelection });
                }
            });

            if (batches.length === 0) {
                alert("Aggiungi almeno un set con quantità valida.");
                return;
            }

            const submitOrder = async (ignoreWarnings = false, replacements = {}) => {
                const formData = new FormData(createOrderForm);
                formData.set('batch_data', JSON.stringify(batches));
                formData.set('is_ajax', 'true');
                if (ignoreWarnings) formData.set('ignore_warnings', 'true');
                if (Object.keys(replacements).length > 0) {
                    formData.set('replacements', JSON.stringify(replacements));
                }

                if (typeof showLoader === 'function') showLoader();
                
                try {
                    const response = await fetch(createOrderForm.action, {
                        method: 'POST',
                        body: formData,
                        headers: {
                            'X-Requested-With': 'XMLHttpRequest',
                            'X-CSRFToken': getCookie('csrftoken')
                        }
                    });

                    if (!response.ok) {
                        const err = await response.json();
                        throw new Error(err.message || "Errore del server");
                    }

                    const result = await response.json();
                    if (typeof hideLoader === 'function') hideLoader();

                    if (result.status === 'warning') {
                        const newReplacements = {};
                        let missingList = "";
                        let hasAlternatives = false;

                        result.missing.forEach(item => {
                            if (item.alternative) {
                                missingList += `<li class="mb-2"><strong>${item.name}</strong><br><span class="text-success"><i class="bi bi-arrow-return-right"></i> Alternativa: ${item.alternative}</span></li>`;
                                hasAlternatives = true;
                            } else {
                                missingList += `<li class="mb-2"><strong>${item.name}</strong><br><span class="text-danger"><i class="bi bi-exclamation-triangle"></i> Nessuna alternativa trovata</span></li>`;
                            }
                        });

                        let warningModalHtml = `
                        <div class="modal fade" id="missingFilamentModal" tabindex="-1">
                            <div class="modal-dialog modal-dialog-centered">
                                <div class="modal-content bg-dark-card text-white border-warning">
                                    <div class="modal-header border-secondary border-bottom-0 pb-0">
                                        <h5 class="modal-title text-warning"><i class="bi bi-exclamation-triangle-fill me-2"></i>Filamenti Mancanti</h5>
                                        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                                    </div>
                                    <div class="modal-body">
                                        <p>I seguenti filamenti consigliati non hanno bobine attive al momento:</p>
                                        <ul class="list-unstyled bg-dark p-3 rounded mb-3 border border-secondary" style="font-size: 0.9em;">
                                            ${missingList}
                                        </ul>
                                        <p class="mb-0">${hasAlternatives ? "Vuoi usare le alternative suggerite e procedere con la creazione dell'ordine?" : "Vuoi procedere comunque senza assegnare bobine a questi filamenti?"}</p>
                                    </div>
                                    <div class="modal-footer border-secondary border-top-0 pt-0">
                                        <button type="button" class="btn btn-outline-light" data-bs-dismiss="modal">Annulla</button>
                                        <button type="button" class="btn btn-warning" id="confirmMissingFilamentBtn">Procedi</button>
                                    </div>
                                </div>
                            </div>
                        </div>`;

                        const existingMod = document.getElementById('missingFilamentModal');
                        if (existingMod) existingMod.remove();

                        document.body.insertAdjacentHTML('beforeend', warningModalHtml);
                        const warningModalEl = document.getElementById('missingFilamentModal');
                        const warningModal = new bootstrap.Modal(warningModalEl);

                        document.getElementById('confirmMissingFilamentBtn').addEventListener('click', function() {
                            if (hasAlternatives) {
                                result.missing.forEach(item => {
                                    if (item.alternative_id) {
                                        newReplacements[item.id] = item.alternative_id;
                                    }
                                });
                            }
                            warningModal.hide();
                            submitOrder(true, newReplacements);
                        });

                        warningModal.show();
                    } else if (result.status === 'ok') {
                        if (result.redirect_url) {
                            window.location.href = result.redirect_url;
                        } else {
                            if (typeof showToast === 'function') showToast(result.message || "Ordine creato!");
                            const bootstrapModal = bootstrap.Modal.getInstance(createModal);
                            if (bootstrapModal) bootstrapModal.hide();
                            setTimeout(() => window.location.reload(), 1000);
                        }
                    } else {
                        if (typeof showToast === 'function') showToast(result.message || "Errore sconosciuto", 'danger');
                        else alert(result.message || "Errore durante la creazione");
                    }
                } catch (error) {
                    if (typeof hideLoader === 'function') hideLoader();
                    console.error("Errore creazione ordine:", error);
                    if (typeof showToast === 'function') showToast(error.message || "Errore di connessione", 'danger');
                    else alert("Errore durante l'invio dell'ordine.");
                }
            };

            submitOrder();
        });
    }

    // 3. Logic for Manage Parts (now integrated in Edit Master Modal)
    const integratedPartsModal = document.getElementById('editMasterModal');
    if (integratedPartsModal) {
        const partsContainer = document.getElementById('parts-container');
        const addPartBtn = document.getElementById('add-part-btn');

        if (addPartBtn && partsContainer) {
            addPartBtn.addEventListener('click', function () {
                const rowCount = partsContainer.querySelectorAll('.part-row').length + 1;
                const projName = document.querySelector('#editMasterModal input[name="name"]')?.value?.trim();
                const defaultName = (rowCount === 1 && projName) ? projName : `Parte ${rowCount}`;
                const div = document.createElement('div');
                div.className = 'input-group mb-2 part-row';
                div.innerHTML = `
                    <input type="hidden" name="part_ids[]" value="">
                    <input type="text" name="part_names[]" class="form-control bg-dark text-white" value="${defaultName}" placeholder="Nome Parte" style="flex: 3;">
                    <span class="input-group-text bg-dark border-secondary text-white-50">Qtà x Oggetto</span>
                    <input type="number" name="part_pieces[]" class="form-control bg-dark text-white text-center" value="1" min="1" placeholder="Pz" style="max-width: 90px;">
                    <button type="button" class="btn btn-outline-danger remove-part-btn"><i class="bi bi-trash"></i></button>
                `;
                partsContainer.appendChild(div);

                div.querySelector('.remove-part-btn').addEventListener('click', function () {
                    div.remove();
                });
            });

            // Add remove listener to existing rows (delegation or initial loop)
            partsContainer.addEventListener('click', function (e) {
                if (e.target.closest('.remove-part-btn')) {
                    e.target.closest('.part-row').remove();
                }
            });
        }
    }

    // 4. Logic for Output Management in Edit Master Modal
    const editMasterModal = document.getElementById('editMasterModal');
    if (editMasterModal) {
        const outputsContainer = editMasterModal.querySelector('#outputs-container');
        const addOutputBtn = editMasterModal.querySelector('#add-output-btn');

        if (addOutputBtn && outputsContainer) {
            addOutputBtn.addEventListener('click', function () {
                const div = document.createElement('div');
                div.className = 'input-group mb-2 output-row';
                div.innerHTML = `
                    <input type="hidden" name="output_ids[]" value="">
                    <input type="text" name="output_names[]" class="form-control bg-dark text-white" value="" placeholder="Nome Output" style="flex: 2;">
                    <input type="number" name="output_quantities[]" class="form-control bg-dark text-white text-center" value="1" min="1" placeholder="Qtà" style="max-width: 80px;">
                    <button type="button" class="btn btn-outline-danger remove-output-btn"><i class="bi bi-trash"></i></button>
                `;
                outputsContainer.appendChild(div);

                div.querySelector('.remove-output-btn').addEventListener('click', function () {
                    div.remove();
                });
            });

            // Add remove listener to existing rows
            outputsContainer.addEventListener('click', function (e) {
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
    }

    // 2b. Logic for Add to Order Modal (Enhanced with Split Prints/Batches)
    const addToOrderModal = document.getElementById('addToOrderModal');
    if (addToOrderModal) {
        const addToOrderForm = document.getElementById('addToOrderForm');
        const batchContainer = document.getElementById('add-to-order-batches-container');
        const btnAddBatch = document.getElementById('btn-add-to-order-batch');
        const batchDataInput = document.getElementById('add_to_order_batch_data_input');
        const addToOrderText = document.getElementById('addToOrderText');
        const summaryContainer = document.getElementById('add-to-order-creation-summary');
        const summaryList = document.getElementById('add-to-order-summary-list');

        let projectName = '';
        let baseQty = 1;
        let partsInfo = []; // Array di {id, name, printers: [{id, name, tag}]}

        addToOrderModal.addEventListener('show.bs.modal', function (event) {
            const createBtn = document.querySelector('button[data-bs-target="#createOrderModal"]');
            const projectId = createBtn ? createBtn.getAttribute('data-project-id') : '';
            projectName = createBtn ? createBtn.getAttribute('data-project-name') : '';
            baseQty = createBtn ? parseInt(createBtn.getAttribute('data-base-qty')) || 1 : 1;

            addToOrderForm.action = `/library/${projectId}/add_to_order/`;
            addToOrderText.innerHTML = `Stai configurando l'aggiunta di parti del progetto <strong>${projectName}</strong> ad un ordine in corso. Puoi dividere la produzione su più stampanti aggiungendo ulteriori set.`;

            // 1. Esplora le parti e le stampanti disponibili nella pagina
            partsInfo = [];
            document.querySelectorAll('.part-section').forEach(section => {
                const partId = section.getAttribute('data-part-id');
                const partName = section.querySelector('h6').textContent.trim();
                const printersInPartMap = new Map();
                const filesInPart = [];

                section.querySelectorAll('.master-file-row').forEach(row => {
                    const id = row.getAttribute('data-printer-id');
                    const tag = row.getAttribute('data-printer');
                    const name = row.getAttribute('data-printer-name');
                    const fileId = row.getAttribute('data-file-id');
                    const fileName = row.querySelector('td')?.textContent.trim() || 'File';
                    const producedQty = parseInt(row.getAttribute('data-produced-qty')) || 1;
                    const estimatedTime = row.querySelectorAll('td')[1]?.textContent.trim() || '';

                    if (fileId) {
                        filesInPart.push({
                            id: fileId,
                            name: fileName,
                            printerId: (id && id !== 'none') ? id : null,
                            printerName: name || tag,
                            printerTag: tag,
                            producedQty: producedQty,
                            estimatedTime: estimatedTime
                        });
                    }

                    if (id && id !== 'none') {
                        printersInPartMap.set(id, { id, name: name || tag, tag: tag });
                    }
                });

                if (filesInPart.length > 0) {
                    partsInfo.push({
                        id: partId,
                        name: partName,
                        printers: Array.from(printersInPartMap.values()),
                        files: filesInPart
                    });
                }
            });

            // 2. Resetta e aggiungi il primo set
            batchContainer.innerHTML = '';
            addBatch(baseQty);
            updateOrderSummary();
        });

        function addBatch(qty = 1) {
            const batchIndex = batchContainer.querySelectorAll('.order-batch-item').length;
            const batchId = Date.now() + "_" + batchIndex; // ID temporaneo univoco per i radio button
            const batchDiv = document.createElement('div');
            batchDiv.className = 'order-batch-item card bg-dark border-secondary mb-3 p-3';
            batchDiv.setAttribute('data-batch-index', batchIndex);

            let partsHtml = '';
            partsInfo.forEach(part => {
                let printerOptionsHtml = `
                    <div class="d-flex flex-wrap gap-2 mb-2">
                        <div class="printer-box-wrapper">
                            <input type="radio" class="btn-check printer-radio-addtoorder" name="printer_part_${part.id}_addtoorder_${batchId}" id="add_to_order_skip_${part.id}_${batchId}" value="skip" autocomplete="off" data-part-id="${part.id}" data-batch-id="${batchId}">
                            <label class="btn btn-outline-secondary btn-xs" for="add_to_order_skip_${part.id}_${batchId}">Salta</label>
                        </div>
                `;

                part.printers.forEach((printer, pIdx) => {
                    const uniqueId = `add_to_order_b${batchId}_p${part.id}_pr${printer.id}`;
                    const isChecked = pIdx === 0 ? 'checked' : '';
                    printerOptionsHtml += `
                        <div class="printer-box-wrapper">
                            <input type="radio" class="btn-check printer-radio-addtoorder" name="printer_part_${part.id}_addtoorder_${batchId}" id="${uniqueId}" value="${printer.id}" autocomplete="off" ${isChecked} data-part-id="${part.id}" data-printer-id="${printer.id}" data-batch-id="${batchId}">
                            <label class="btn btn-outline-orange btn-xs" for="${uniqueId}">${printer.name}</label>
                        </div>
                    `;
                });
                printerOptionsHtml += '</div>';

                // File variants per printer
                let fileVariantsHtml = '';
                part.printers.forEach((printer, pIdx) => {
                    const printerFiles = part.files.filter(f => !f.printerId || String(f.printerId) === String(printer.id));
                    const isPrinterChecked = pIdx === 0;

                    if (printerFiles.length > 1) {
                        let bestMatchId = printerFiles[0].id;
                        const exactMatch = printerFiles.find(f => f.producedQty === qty);
                        if (exactMatch) {
                            bestMatchId = exactMatch.id;
                        } else {
                            const smallerOrEqual = printerFiles.filter(f => f.producedQty <= qty).sort((a, b) => b.producedQty - a.producedQty);
                            if (smallerOrEqual.length > 0) {
                                bestMatchId = smallerOrEqual[0].id;
                            }
                        }

                        let radiosHtml = '';
                        printerFiles.forEach(f => {
                            const fChecked = (f.id === bestMatchId) ? 'checked' : '';
                            const fUniqueId = `f_ato_${f.id}_b${batchId}_p${part.id}`;
                            radiosHtml += `
                                <div class="file-box-wrapper">
                                    <input type="radio" class="btn-check file-variant-radio-addtoorder" name="file_part_${part.id}_addtoorder_${batchId}" id="${fUniqueId}" value="${f.id}" data-produced-qty="${f.producedQty}" ${fChecked} ${isPrinterChecked ? '' : 'disabled'}>
                                    <label class="btn btn-outline-info btn-xs" for="${fUniqueId}">
                                        ${f.name} <span class="badge bg-secondary ms-1">${f.producedQty} pz</span>
                                        <span class="text-white-50 ms-1 small">(${f.estimatedTime})</span>
                                    </label>
                                </div>
                            `;
                        });

                        fileVariantsHtml += `
                            <div class="file-variant-wrapper ms-1 ps-2 border-start border-warning" id="files_wrap_ato_${part.id}_pr_${printer.id}_${batchId}" style="${isPrinterChecked ? '' : 'display: none;'}">
                                <div class="small text-warning-emphasis mb-1"><i class="bi bi-layers me-1"></i>Piatto G-code:</div>
                                <div class="d-flex flex-wrap gap-2">
                                    ${radiosHtml}
                                </div>
                            </div>
                        `;
                    } else if (printerFiles.length === 1) {
                        const singleFile = printerFiles[0];
                        fileVariantsHtml += `
                            <input type="hidden" class="single-file-input-addtoorder" name="file_part_${part.id}_addtoorder_${batchId}" value="${singleFile.id}" data-produced-qty="${singleFile.producedQty}" data-printer-id="${printer.id}" ${isPrinterChecked ? '' : 'disabled'}>
                        `;
                    }
                });

                partsHtml += `
                    <div class="mb-3 part-selection-row" data-part-id="${part.id}">
                        <label class="small text-white-50 d-block mb-1">${part.name}</label>
                        ${printerOptionsHtml}
                        ${fileVariantsHtml}
                    </div>
                `;
            });

            const showRemove = batchIndex > 0;
            batchDiv.innerHTML = `
                <div class="d-flex justify-content-between align-items-center mb-3">
                    <h6 class="text-success mb-0"><i class="bi bi-box-seam me-2"></i>Lotto #${batchIndex + 1}</h6>
                    ${showRemove ? '<button type="button" class="btn btn-link btn-sm text-danger p-0 btn-remove-batch"><i class="bi bi-trash"></i> Rimuovi</button>' : ''}
                </div>
                <div class="row mb-1">
                    <div class="col-12">
                        <span class="badge bg-dark border border-secondary text-white-50 p-2">
                             <i class="bi bi-stack me-1"></i>Quantità: <strong>${qty} pezzi</strong>
                        </span>
                        <input type="hidden" class="batch-qty-input" value="${qty}">
                    </div>
                </div>
                <div class="batch-parts-selection">
                    ${partsHtml}
                </div>
            `;

            batchContainer.appendChild(batchDiv);

            // Listeners
            if (showRemove) {
                batchDiv.querySelector('.btn-remove-batch').addEventListener('click', () => {
                    batchDiv.remove();
                    reindexBatches();
                    updateOrderSummary();
                });
            }

            // Gestione cambio stampante per mostrare/nascondere file corretti
            batchDiv.querySelectorAll('.printer-radio-addtoorder').forEach(pRad => {
                pRad.addEventListener('change', function () {
                    const pRow = this.closest('.part-selection-row');
                    const partId = this.getAttribute('data-part-id');
                    const printerId = this.getAttribute('data-printer-id');
                    const isSkip = this.value === 'skip';

                    // Disabilita tutti i file della parte
                    pRow.querySelectorAll('.file-variant-wrapper').forEach(w => {
                        w.style.display = 'none';
                        w.querySelectorAll('input').forEach(inp => inp.disabled = true);
                    });
                    pRow.querySelectorAll('.single-file-input-addtoorder').forEach(inp => inp.disabled = true);

                    if (!isSkip && printerId) {
                        const targetWrap = pRow.querySelector(`#files_wrap_ato_${partId}_pr_${printerId}_${batchId}`);
                        if (targetWrap) {
                            targetWrap.style.display = 'block';
                            targetWrap.querySelectorAll('input').forEach(inp => inp.disabled = false);
                            if (!targetWrap.querySelector('input:checked')) {
                                const firstRadio = targetWrap.querySelector('input[type="radio"]');
                                if (firstRadio) firstRadio.checked = true;
                            }
                        }
                        const targetSingle = pRow.querySelector(`.single-file-input-addtoorder[data-printer-id="${printerId}"]`);
                        if (targetSingle) {
                            targetSingle.disabled = false;
                        }
                    }
                    updateOrderSummary();
                });
            });

            batchDiv.querySelector('.batch-qty-input').addEventListener('input', updateOrderSummary);
            batchDiv.querySelectorAll('.file-variant-radio-addtoorder').forEach(fRad => {
                fRad.addEventListener('change', updateOrderSummary);
            });
        }

        function reindexBatches() {
            batchContainer.querySelectorAll('.order-batch-item').forEach((item, idx) => {
                item.setAttribute('data-batch-index', idx);
                const title = item.querySelector('h6');
                if (title) title.innerHTML = `<i class="bi bi-box-seam me-2"></i>Lotto #${idx + 1}`;
            });
        }

        btnAddBatch.addEventListener('click', () => {
            addBatch(baseQty);
            updateOrderSummary();
        });

        function updateOrderSummary() {
            let totalQty = 0;
            let totalFilesCount = 0;
            const batchSummaries = [];

            const batches = batchContainer.querySelectorAll('.order-batch-item');
            batches.forEach((batchDiv, idx) => {
                const qty = parseInt(batchDiv.querySelector('.batch-qty-input').value) || 0;
                totalQty += qty;

                let batchFiles = 0;
                batchDiv.querySelectorAll('.part-selection-row').forEach(row => {
                    const checkedPrinter = row.querySelector('.printer-radio-addtoorder:checked');
                    if (!checkedPrinter || checkedPrinter.value === 'skip') return;

                    const activeFile = row.querySelector('.file-variant-radio-addtoorder:not(:disabled):checked, .single-file-input-addtoorder:not(:disabled)');
                    if (activeFile) {
                        const producedQty = parseInt(activeFile.getAttribute('data-produced-qty')) || 1;
                        batchFiles += Math.ceil(qty / producedQty);
                    }
                });

                totalFilesCount += batchFiles;
                if (qty > 0) {
                    batchSummaries.push(`Lotto #${idx + 1}: <strong>${qty} pezzi</strong> (${batchFiles} file)`);
                }
            });

            if (totalQty > 0) {
                summaryContainer.classList.remove('d-none');
                summaryList.innerHTML = `
                    <li>Progetto: <strong>${projectName}</strong></li>
                    <li>Quantità Totale Aggiunta: <strong>${totalQty}</strong></li>
                    ${batchSummaries.map(s => `<li>${s}</li>`).join('')}
                    <hr class="my-2 border-secondary">
                    <p class="mt-2 text-muted mb-0"><i class="bi bi-info-circle me-1 text-muted"></i>Verranno aggiunti <strong>${totalFilesCount}</strong> File di Stampa in totale.</p>
                `;
            } else {
                summaryContainer.classList.add('d-none');
            }
        }

        addToOrderForm.addEventListener('submit', function (e) {
            e.preventDefault();

            const selectEl = document.getElementById('addToOrderSelect');
            if (!selectEl || !selectEl.value) {
                alert("Seleziona un ordine di destinazione valido.");
                return;
            }

            const batches = [];
            batchContainer.querySelectorAll('.order-batch-item').forEach(batchDiv => {
                const qty = parseInt(batchDiv.querySelector('.batch-qty-input').value) || 0;
                const printerSelection = {};
                const fileSelection = {};

                batchDiv.querySelectorAll('.part-selection-row').forEach(row => {
                    const partId = row.getAttribute('data-part-id');
                    const checkedPrinter = row.querySelector('.printer-radio-addtoorder:checked');
                    if (checkedPrinter) {
                        printerSelection[partId] = checkedPrinter.value;
                    }
                    const activeFile = row.querySelector('.file-variant-radio-addtoorder:not(:disabled):checked, .single-file-input-addtoorder:not(:disabled)');
                    if (activeFile && checkedPrinter && checkedPrinter.value !== 'skip') {
                        fileSelection[partId] = activeFile.value;
                    }
                });

                if (qty > 0) {
                    batches.push({ quantity: qty, printers: printerSelection, files: fileSelection });
                }
            });

            if (batches.length === 0) {
                alert("Aggiungi almeno un set con quantità valida.");
                return;
            }

            const submitOrder = async (ignoreWarnings = false, replacements = {}) => {
                const formData = new FormData(addToOrderForm);
                formData.set('batch_data', JSON.stringify(batches));
                formData.set('is_ajax', 'true');
                if (ignoreWarnings) formData.set('ignore_warnings', 'true');
                if (Object.keys(replacements).length > 0) {
                    formData.set('replacements', JSON.stringify(replacements));
                }

                if (typeof showLoader === 'function') showLoader();
                
                try {
                    const response = await fetch(addToOrderForm.action, {
                        method: 'POST',
                        body: formData,
                        headers: {
                            'X-Requested-With': 'XMLHttpRequest',
                            'X-CSRFToken': getCookie('csrftoken')
                        }
                    });

                    if (!response.ok) {
                        const err = await response.json();
                        throw new Error(err.message || "Errore del server");
                    }

                    const result = await response.json();
                    if (typeof hideLoader === 'function') hideLoader();

                    if (result.status === 'warning') {
                        const newReplacements = {};
                        let missingList = "";
                        let hasAlternatives = false;

                        result.missing.forEach(item => {
                            if (item.alternative) {
                                missingList += `<li class="mb-2"><strong>${item.name}</strong><br><span class="text-success"><i class="bi bi-arrow-return-right"></i> Alternativa: ${item.alternative}</span></li>`;
                                hasAlternatives = true;
                            } else {
                                missingList += `<li class="mb-2"><strong>${item.name}</strong><br><span class="text-danger"><i class="bi bi-exclamation-triangle"></i> Nessuna alternativa trovata</span></li>`;
                            }
                        });

                        let warningModalHtml = `
                        <div class="modal fade" id="addToOrderMissingFilamentModal" tabindex="-1">
                            <div class="modal-dialog modal-dialog-centered">
                                <div class="modal-content bg-dark-card text-white border-warning">
                                    <div class="modal-header border-secondary border-bottom-0 pb-0">
                                        <h5 class="modal-title text-warning"><i class="bi bi-exclamation-triangle-fill me-2"></i>Filamenti Mancanti</h5>
                                        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                                    </div>
                                    <div class="modal-body">
                                        <p>I seguenti filamenti consigliati non hanno bobine attive al momento:</p>
                                        <ul class="list-unstyled bg-dark p-3 rounded mb-3 border border-secondary" style="font-size: 0.9em;">
                                            ${missingList}
                                        </ul>
                                        <p class="mb-0">${hasAlternatives ? "Vuoi usare le alternative suggerite e procedere con l'aggiunta?" : "Vuoi procedere comunque senza assegnare bobine a questi filamenti?"}</p>
                                    </div>
                                    <div class="modal-footer border-secondary border-top-0 pt-0">
                                        <button type="button" class="btn btn-outline-light" data-bs-dismiss="modal">Annulla</button>
                                        <button type="button" class="btn btn-warning" id="confirmAddToOrderMissingFilamentBtn">Procedi</button>
                                    </div>
                                </div>
                            </div>
                        </div>`;

                        const existingMod = document.getElementById('addToOrderMissingFilamentModal');
                        if (existingMod) existingMod.remove();

                        document.body.insertAdjacentHTML('beforeend', warningModalHtml);
                        const warningModalEl = document.getElementById('addToOrderMissingFilamentModal');
                        const warningModal = new bootstrap.Modal(warningModalEl);

                        document.getElementById('confirmAddToOrderMissingFilamentBtn').addEventListener('click', function() {
                            if (hasAlternatives) {
                                result.missing.forEach(item => {
                                    if (item.alternative_id) {
                                        newReplacements[item.id] = item.alternative_id;
                                    }
                                });
                            }
                            warningModal.hide();
                            submitOrder(true, newReplacements);
                        });

                        warningModal.show();
                    } else if (result.status === 'ok') {
                        if (result.redirect_url) {
                            window.location.href = result.redirect_url;
                        } else {
                            if (typeof showToast === 'function') showToast(result.message || "Parti aggiunte!");
                            const bootstrapModal = bootstrap.Modal.getInstance(addToOrderModal);
                            if (bootstrapModal) bootstrapModal.hide();
                            setTimeout(() => window.location.reload(), 1000);
                        }
                    } else {
                        if (typeof showToast === 'function') showToast(result.message || "Errore sconosciuto", 'danger');
                        else alert(result.message || "Errore durante l'aggiunta");
                    }
                } catch (error) {
                    if (typeof hideLoader === 'function') hideLoader();
                    console.error("Errore aggiunta ordine:", error);
                    if (typeof showToast === 'function') showToast(error.message || "Errore di connessione", 'danger');
                    else alert("Errore durante l'invio della richiesta.");
                }
            };

            submitOrder();
        });
    }
});
