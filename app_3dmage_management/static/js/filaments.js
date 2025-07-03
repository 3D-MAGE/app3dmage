document.addEventListener('DOMContentLoaded', function() {
    const filamentsDataTag = document.getElementById('filaments-data');
    if (!filamentsDataTag) return;

    const URLS = {
        add_filament: filamentsDataTag.dataset.addFilamentUrl,
        add_spool: filamentsDataTag.dataset.addSpoolUrl,
        base_filament: filamentsDataTag.dataset.baseFilamentUrl,
        base_spool: filamentsDataTag.dataset.baseSpoolUrl,
        api_base_spool: filamentsDataTag.dataset.apiBaseSpoolUrl,
    };
    // getCookie() è già disponibile da base.js, quindi lo usiamo direttamente
    const csrftoken = getCookie('csrftoken');

    const getContrastYIQ = (hexcolor) => {
        hexcolor = hexcolor.replace("#", "");
        const r = parseInt(hexcolor.substr(0, 2), 16);
        const g = parseInt(hexcolor.substr(2, 2), 16);
        const b = parseInt(hexcolor.substr(4, 2), 16);
        const yiq = ((r * 299) + (g * 587) + (b * 114)) / 1000;
        return (yiq >= 128) ? 'black' : 'white';
    };

    document.querySelectorAll('.filament-pill').forEach(pill => {
        const bgColor = pill.style.backgroundColor;
        if (bgColor) pill.style.color = getContrastYIQ(bgColor);
    });

    const editModalEl = document.getElementById('editFilamentModal');
    if (!editModalEl) return;

    const editModal = new bootstrap.Modal(editModalEl);
    const form = document.getElementById('editFilamentForm');
    const title = document.getElementById('editFilamentModalTitle');
    const deleteBtnTrigger = document.getElementById('deleteFilamentBtnTrigger');
    const spoolListContainer = document.getElementById('spool-list-container');
    const addSpoolBtnInModal = editModalEl.querySelector('.add-spool-from-modal-btn');
    const confirmDeleteModal = new bootstrap.Modal(document.getElementById('deleteFilamentConfirmModal'));
    const confirmDeleteBtn = document.getElementById('confirmDeleteFilamentBtn');
    const editFormContainer = document.getElementById('editFilamentFormContainer');

    const fetchAndRenderSpools = (filamentId) => {
        spoolListContainer.innerHTML = '<p class="text-white-50 small fst-italic p-3">Caricamento bobine...</p>';

        fetch(`${URLS.api_base_spool}${filamentId}/spools/`).then(res => res.json()).then(spools => {
            if (spools.length > 0) {
                let spoolsHtml = '<ul class="list-group list-group-flush spool-list-group">';
                spools.forEach(spool => {
                    const remainingGrams = parseFloat(spool.remaining);

                    spoolsHtml += `<li class="list-group-item d-flex justify-content-between align-items-center" id="spool-item-${spool.id}">
                        <div>${spool.text} (${remainingGrams.toFixed(0)}g rim.)</div>
                        <div>
                            ${spool.purchase_link ? `<a href="${spool.purchase_link}" target="_blank" class="btn btn-sm btn-outline-info" title="Vai al link di acquisto" onclick="event.stopPropagation();"><i class="bi bi-link-45deg"></i></a>` : ''}
                            <span class="badge bg-secondary ms-2">${spool.cost}</span>
                            <button type="button" class="btn btn-sm btn-outline-danger delete-spool-btn ms-2" data-spool-id="${spool.id}" onclick="event.stopPropagation();" title="Elimina Bobina"><i class="bi bi-trash-fill"></i></button>
                        </div>
                    </li>`;
                });
                spoolsHtml += '</ul>';
                spoolListContainer.innerHTML = spoolsHtml;
            } else {
                spoolListContainer.innerHTML = '<p class="text-muted small p-3">Nessuna bobina per questo filamento.</p>';
            }
        });
    };

    editModalEl.addEventListener('show.bs.modal', function(event) {
        const row = event.relatedTarget;
        if (!row || !row.dataset.filamentId) return;
        const filamentId = row.dataset.filamentId;

        form.action = `${URLS.base_filament}${filamentId}/edit/`;
        confirmDeleteBtn.dataset.deleteUrl = `${URLS.base_filament}${filamentId}/delete/`;
        addSpoolBtnInModal.dataset.filamentId = filamentId;

        fetch(`${URLS.base_filament}${filamentId}/details/`).then(res => res.json()).then(data => {
            title.textContent = `Modifica: ${data.material}-${data.color_code}-${data.brand}`;
            editFormContainer.innerHTML = document.getElementById('filament-form-template').innerHTML;
            for (const key in data) {
                const field = form.querySelector(`[name="${key}"]`);
                if (field) {
                    if (field.type === 'color') { field.value = data[key] || '#FFFFFF'; }
                    else { field.value = data[key] || ''; }
                }
            }
        });
        fetchAndRenderSpools(filamentId);
    });

    addSpoolBtnInModal.addEventListener('click', function() {
        const filamentId = this.dataset.filamentId;
        document.querySelector('#addSpoolModal select[name="filament"]').value = filamentId;
        editModal.hide();
        new bootstrap.Modal(document.getElementById('addSpoolModal')).show();
    });

    form.addEventListener('submit', function(e) {
        e.preventDefault();
        fetch(this.action, { method: 'POST', body: new FormData(this), headers: {'X-CSRFToken': csrftoken} })
        .then(res => res.json()).then(data => {
            if(data.status === 'ok') { window.location.reload(); }
            else { showToast('Errore durante la modifica.', 'error'); }
        });
    });

    deleteBtnTrigger.addEventListener('click', function() {
        document.getElementById('deleteFilamentConfirmBody').textContent = `Sei sicuro di voler eliminare questo tipo di filamento? L'azione è irreversibile.`;
        confirmDeleteModal.show();
    });

    confirmDeleteBtn.addEventListener('click', function() {
        fetch(this.dataset.deleteUrl, { method: 'POST', headers: {'X-CSRFToken': csrftoken} })
        .then(res => res.json()).then(data => {
            if(data.status === 'ok') { window.location.reload(); }
            else { showToast(data.message || 'Errore durante l\'eliminazione.', 'error'); }
        });
    });

    spoolListContainer.addEventListener('click', function(e) {
        const deleteButton = e.target.closest('.delete-spool-btn');
        if (deleteButton) {
            e.stopPropagation();
            const spoolId = deleteButton.dataset.spoolId;
            if (confirm('Sei sicuro di voler eliminare questa bobina? L\'azione cancellerà anche la spesa associata e non è reversibile.')) {
                fetch(`${URLS.base_spool}${spoolId}/delete/`, { method: 'POST', headers: {'X-CSRFToken': csrftoken} })
                .then(res => res.json())
                .then(data => {
                    if (data.status === 'ok') {
                        showToast(data.message, 'success');
                        document.getElementById(`spool-item-${spoolId}`).remove();
                    } else {
                        showToast(data.message, 'error');
                    }
                });
            }
        }
    });
});
