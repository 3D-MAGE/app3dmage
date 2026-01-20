document.addEventListener('DOMContentLoaded', function() {
    let costs = { electricity_cost_kwh: 0.25, filaments: [] };
    const AVG_PRINTER_WATTAGE = 150;
    const csrftoken = getCookie('csrftoken');

    const materialsContainer = document.getElementById('materials-container');
    const addMaterialBtn = document.getElementById('add-material-btn');
    const rowTemplate = document.getElementById('material-row-template');
    const quoteNameInput = document.getElementById('quoteName');
    const printHoursInput = document.getElementById('printHours');
    const printMinutesInput = document.getElementById('printMinutes');
    const resultTitle = document.getElementById('result-title');
    const costBreakdown = document.getElementById('cost-breakdown');
    const totalCostEl = document.getElementById('total-cost');
    const saveQuoteBtn = document.getElementById('save-quote-btn');
    const createProjectBtn = document.getElementById('create-project-btn');
    const savedQuotesTable = document.getElementById('saved-quotes-table');

    const createProjectConfirmModalEl = document.getElementById('createProjectConfirmModal');
    const createProjectConfirmModal = new bootstrap.Modal(createProjectConfirmModalEl);
    const confirmCreateProjectBtn = document.getElementById('confirmCreateProjectBtn');
    const projectNameInModal = document.getElementById('projectNameInModal');

    const getContrastYIQ = (hex) => {
        if (!hex) return 'white';
        const c = hex.substring(1);
        const rgb = parseInt(c, 16);
        const r = (rgb >> 16) & 0xff;
        const g = (rgb >> 8) & 0xff;
        const b = (rgb >> 0) & 0xff;
        const yiq = ((r * 299) + (g * 587) + (b * 114)) / 1000;
        return (yiq >= 128) ? 'black' : 'white';
    };

    function calculateAndDisplay() {
        const hours = parseFloat(printHoursInput.value) || 0;
        const minutes = parseFloat(printMinutesInput.value) || 0;
        const totalHours = hours + (minutes / 60);

        const electricityKwh = totalHours * (AVG_PRINTER_WATTAGE / 1000);
        const electricityCost = electricityKwh * costs.electricity_cost_kwh;

        let totalMaterialCost = 0;
        let breakdownHtml = `<p class="d-flex justify-content-between mb-1"><span>Costo Elettricità <small class="text-muted">(${electricityKwh.toFixed(2)} kWh)</small></span> <span>${electricityCost.toFixed(2)}€</span></p>`;

        materialsContainer.querySelectorAll('.material-row').forEach(row => {
            const selectElement = row.querySelector('select'); // Prende il select standard (ora gestito da TomSelect)
            const filamentId = selectElement.value;
            const grams = parseFloat(row.querySelector('.grams-input').value) || 0;

            if (filamentId && grams > 0) {
                const filament = costs.filaments.find(f => f.id == filamentId);
                if (filament) {
                    const materialCost = grams * filament.cost_per_gram;
                    totalMaterialCost += materialCost;
                    breakdownHtml += `<p class="d-flex justify-content-between mb-1"><span>${filament.name} <small class="text-muted">(${grams}g)</small></span> <span>${materialCost.toFixed(2)}€</span></p>`;
                }
            }
        });

        const totalCost = electricityCost + totalMaterialCost;
        costBreakdown.innerHTML = breakdownHtml || '<p class="text-muted">Nessun costo da mostrare.</p>';
        totalCostEl.textContent = `${totalCost.toFixed(2)}€`;
        const name = quoteNameInput.value.trim();
        resultTitle.textContent = name ? `Riepilogo Costi: ${name}` : 'Riepilogo Costi';
    }

    function addMaterialRow(usage = {}) {
        const newRow = rowTemplate.content.cloneNode(true).firstElementChild;
        const selectContainer = newRow.querySelector('.select-container');
        const gramsInput = newRow.querySelector('.grams-input');

        // Crea dinamicamente l'elemento SELECT
        const selectEl = document.createElement('select');
        selectEl.classList.add('form-select');
        selectEl.setAttribute('placeholder', 'Seleziona materiale...');
        selectContainer.appendChild(selectEl);

        // Prepara le opzioni per Tom Select
        const options = costs.filaments.map(f => ({
            id: f.id,
            title: f.name,
            cost: f.cost_per_gram,
            color: f.color_hex,
            contrast: getContrastYIQ(f.color_hex)
        }));

        // Inizializza Tom Select
        const ts = new TomSelect(selectEl, {
            options: options,
            valueField: 'id',
            labelField: 'title',
            searchField: 'title',
            placeholder: 'Cerca materiale...',
            render: {
                option: function(data, escape) {
                    return `<div>
                        <span style="display:inline-block; width:10px; height:10px; border-radius:50%; background-color:${escape(data.color)}; margin-right:5px;"></span>
                        ${escape(data.title)} (~${parseFloat(data.cost).toFixed(3)}€/g)
                    </div>`;
                },
                item: function(data, escape) {
                    return `<div style="background-color: ${escape(data.color)}; color: ${escape(data.contrast)}; border-radius: 99px; padding: 2px 10px; font-weight: 500;">
                        ${escape(data.title)}
                    </div>`;
                }
            },
            onChange: function(value) {
                calculateAndDisplay();
            }
        });

        // Imposta valore iniziale se presente
        if (usage.filament_id) {
            ts.setValue(usage.filament_id);
        }
        if (usage.grams) {
            gramsInput.value = usage.grams;
        }

        gramsInput.addEventListener('input', calculateAndDisplay);

        newRow.querySelector('.remove-row-btn').addEventListener('click', () => {
            ts.destroy(); // Pulisci l'istanza Tom Select
            newRow.remove();
            calculateAndDisplay();
        });

        materialsContainer.appendChild(newRow);
    }

    function getQuoteData() {
        const quoteName = quoteNameInput.value.trim();
        const hours = parseInt(printHoursInput.value, 10) || 0;
        const minutes = parseInt(printMinutesInput.value, 10) || 0;

        if (!quoteName) {
            showToast('Inserisci un nome per il preventivo.', 'error');
            return null;
        }
        if (hours === 0 && minutes === 0) {
            showToast('Inserisci un tempo di stampa valido.', 'error');
            return null;
        }

        const materials = [];
        let hasInvalidMaterial = false;
        materialsContainer.querySelectorAll('.material-row').forEach(row => {
            // Con Tom Select, il valore è sull'elemento select originale (che è nascosto ma aggiornato)
            // O meglio, cerchiamo il select dentro .select-container
            const selectEl = row.querySelector('select');
            const filamentId = selectEl.value;
            const grams = row.querySelector('.grams-input').value;

            if (filamentId && grams && parseFloat(grams) > 0) {
                materials.push({
                    filament_id: filamentId,
                    grams: grams,
                });
            } else if (filamentId || (grams && parseFloat(grams) > 0)) {
                hasInvalidMaterial = true;
            }
        });

        if (materials.length === 0) {
            showToast('Aggiungi almeno un materiale con un peso valido.', 'error');
            return null;
        }
        if (hasInvalidMaterial) {
            showToast('Completa tutte le righe dei materiali o rimuovi quelle vuote.', 'error');
            return null;
        }

        return {
            name: quoteName,
            hours: hours,
            minutes: minutes,
            total_cost: parseFloat(totalCostEl.textContent.replace('€', '')),
            materials: materials
        };
    }

    function initializeApp() {
        addMaterialRow();
        calculateAndDisplay();

        addMaterialBtn.addEventListener('click', () => addMaterialRow());
        quoteNameInput.addEventListener('input', calculateAndDisplay);
        printHoursInput.addEventListener('input', calculateAndDisplay);
        printMinutesInput.addEventListener('input', calculateAndDisplay);

        saveQuoteBtn.addEventListener('click', function() {
            const quoteData = getQuoteData();
            if (!quoteData) return;

            const dataToSave = {
                name: quoteData.name,
                total_cost: quoteData.total_cost,
                details: quoteData
            };

            fetch("/quotes/save/", {
                method: 'POST',
                headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrftoken},
                body: JSON.stringify(dataToSave)
            }).then(res => {
                if (res.ok) {
                    showToast('Preventivo salvato!');
                    setTimeout(() => window.location.reload(), 1000);
                } else { showToast('Errore nel salvataggio.', 'error'); }
            });
        });

        createProjectBtn.addEventListener('click', function() {
            const quoteData = getQuoteData();
            if (!quoteData) return;

            projectNameInModal.textContent = quoteData.name;
            createProjectConfirmModal.show();
        });

        confirmCreateProjectBtn.addEventListener('click', function() {
            const quoteData = getQuoteData();
            if (!quoteData) return;

            createProjectConfirmModal.hide();

            fetch("/quotes/create_project/", {
                method: 'POST',
                headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrftoken},
                body: JSON.stringify(quoteData)
            }).then(res => res.json()).then(data => {
                if (data.status === 'ok') {
                    showToast('Progetto creato con successo!');
                    window.location.href = data.project_url;
                } else {
                    showToast(data.message || 'Errore nella creazione del progetto.', 'error');
                }
            }).catch(err => {
                showToast('Errore di comunicazione con il server.', 'error');
            });
        });

        savedQuotesTable.addEventListener('click', function(e) {
            const target = e.target;
            const row = target.closest('tr.saved-quote-row');
            if (!row) return;

            if (target.closest('.delete-quote-btn')) {
                e.stopPropagation();
                if (confirm('Sei sicuro di voler eliminare questo preventivo?')) {
                    const quoteId = target.closest('.delete-quote-btn').dataset.id;
                    fetch(`/quotes/${quoteId}/delete/`, { method: 'POST', headers: {'X-CSRFToken': csrftoken} })
                    .then(res => {
                        if (res.ok) {
                            row.remove();
                            showToast('Preventivo eliminato.');
                            if (savedQuotesTable.getElementsByTagName('tr').length === 0) {
                                savedQuotesTable.innerHTML = '<tr><td colspan="4" class="text-center text-muted py-4">Nessun preventivo salvato.</td></tr>';
                            }
                        } else {
                            showToast('Errore durante l\'eliminazione.', 'error');
                        }
                    });
                }
            } else {
                const quoteId = row.dataset.quoteId;
                fetch(`/quotes/${quoteId}/details/`)
                .then(res => res.json())
                .then(data => {
                    const details = data.details;
                    quoteNameInput.value = details.name;
                    printHoursInput.value = details.hours;
                    printMinutesInput.value = details.minutes;

                    materialsContainer.innerHTML = '';
                    if(details.materials && details.materials.length > 0) {
                        details.materials.forEach(mat => addMaterialRow(mat));
                    } else {
                        addMaterialRow();
                    }

                    setTimeout(() => {
                        calculateAndDisplay();
                        window.scrollTo({ top: 0, behavior: 'smooth' });
                    }, 50);

                }).catch(err => {
                    console.error("Failed to load quote details:", err);
                    showToast("Impossibile caricare i dati del preventivo.", "error");
                });
            }
        });
    }

    fetch("/api/costs/").then(res => res.json()).then(data => {
        costs = data;
        initializeApp();
    }).catch(err => {
        console.error("Could not load cost data:", err);
        costBreakdown.innerHTML = `<p class="text-danger">Errore nel caricamento dei dati iniziali.</p>`;
    });

    function getCookie(name) {
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
});
