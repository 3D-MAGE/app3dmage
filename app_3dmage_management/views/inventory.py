import csv
from decimal import Decimal
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db import transaction
from django.db.models import F, Case, When, Value, DecimalField, Q
from django.forms.models import model_to_dict

from ..models import StockItem, PaymentMethod
from ..forms import StockItemForm, ManualStockItemForm, SaleEditForm

@login_required
def inventory_dashboard(request):
    from ..models import GlobalSetting
    # Intelligent Polling Check
    try:
        setting = GlobalSetting.objects.get(key='app_last_updated')
        if setting.value is None or str(setting.value) == '':
            raise ValueError("Empty value")
        current_server_version = str(setting.value)
    except Exception:
        # Corrupt data, reset it
        from django.utils import timezone
        from decimal import Decimal
        ts = str(timezone.now().timestamp())
        new_val = Decimal(ts)
        # Avoid reading corrupt data
        GlobalSetting.objects.filter(key='app_last_updated').delete()
        GlobalSetting.objects.create(key='app_last_updated', value=new_val)
        current_server_version = str(new_val)

    if request.headers.get('HX-Request'):
        client_version = request.GET.get('v')
        if client_version == current_server_version:
            return HttpResponse(status=204)

    search_query = request.GET.get('q', '')
    status_filter = request.GET.get('status', '')
    sort_by = request.GET.get('sort', 'created_at')
    order = request.GET.get('order', 'desc')

    filters_applied = bool(search_query or status_filter)
    order_prefix = '-' if order == 'desc' else ''

    stock_items_query = StockItem.objects.exclude(status='SOLD').select_related('work_order__category').annotate(
        annotated_total_cost=F('material_cost') + F('labor_cost'),
        cost_per_unit=Case(
            When(quantity__gt=0, then=(F('material_cost') + F('labor_cost')) / F('quantity')),
            default=Value(0),
            output_field=DecimalField(decimal_places=2)
        )
    )

    if search_query:
        stock_items_query = stock_items_query.filter(
            Q(name__icontains=search_query) |
            Q(custom_id__icontains=search_query)
        )
    if status_filter:
        stock_items_query = stock_items_query.filter(status=status_filter)

    valid_sort_fields = ['custom_id', 'quantity', 'name', 'status', 'suggested_price', 'total_cost']
    if sort_by not in valid_sort_fields:
        sort_by = 'created_at'

    stock_items = stock_items_query.order_by(f'{order_prefix}{sort_by}')

    context = {
        'stock_items': stock_items,
        'form': StockItemForm(),
        'manual_form': ManualStockItemForm(),
        'page_title': 'Magazzino',
        'all_statuses': StockItem.Status.choices,
        'search_query': search_query,
        'status_filter': status_filter,
        'sort_by': sort_by,
        'order': order,
        'filters_applied': filters_applied,
        'server_version': current_server_version,
    }

    if request.headers.get('HX-Request'):
        return render(request, 'app_3dmage_management/partials/inventory_table.html', context)

    return render(request, 'app_3dmage_management/inventory.html', context)

@login_required
@require_POST
def add_stock_item(request):
    form = ManualStockItemForm(request.POST)
    if form.is_valid():
        current_year = timezone.now().year
        last_item = StockItem.objects.filter(
            custom_id__startswith=f"{current_year % 100:02d}"
        ).order_by('custom_id').last()

        if last_item and last_item.custom_id.isdigit():
             last_sequential = int(last_item.custom_id[2:])
             new_sequential = last_sequential + 1
        else:
            new_sequential = 1

        new_custom_id = f"{current_year % 100:02d}{new_sequential:03d}"

        item = form.save(commit=False)
        item.custom_id = new_custom_id
        item.work_order = None
        item.status = 'IN_STOCK'
        item.save()
        return JsonResponse({'status': 'ok'})
    return JsonResponse({'status': 'error', 'errors': form.errors.as_json()}, status=400)

@login_required
def get_stock_item_details(request, item_id):
    item = get_object_or_404(StockItem.objects.select_related('work_order'), id=item_id)
    data = model_to_dict(item)
    data['project_name'] = item.work_order.name if item.work_order else 'Manuale'
    data['project_id'] = item.work_order.id if item.work_order else None
    data['project_custom_id'] = item.work_order.custom_id if item.work_order else 'N/A'
    data['work_order_notes'] = item.work_order.notes if item.work_order else ''

    # Standardize keys to match inventory.js (production_cost_per_unit, labor_cost_per_unit)
    if item.quantity > 0:
        data['production_cost_per_unit'] = str((item.material_cost / item.quantity).quantize(Decimal('0.01')))
        data['labor_cost_per_unit'] = str((item.labor_cost / item.quantity).quantize(Decimal('0.01')))
    else:
        data['production_cost_per_unit'] = '0.00'
        data['labor_cost_per_unit'] = '0.00'

    return JsonResponse(data)


@require_POST
@transaction.atomic
@login_required
def update_stock_item(request, item_id):
    item_to_process = get_object_or_404(StockItem, id=item_id)
    original_status = item_to_process.status

    form = StockItemForm(request.POST, instance=item_to_process)

    if not form.is_valid():
        return JsonResponse({'status': 'error', 'message': 'Dati non validi.', 'errors': form.errors.as_json()}, status=400)

    if item_to_process.work_order:
        work_order_notes = form.cleaned_data.get('work_order_notes')
        if work_order_notes is not None:
            item_to_process.work_order.notes = work_order_notes
            item_to_process.work_order.save()

    new_status = form.cleaned_data.get('status')

    if new_status != 'SOLD':
        form.save()
        return JsonResponse({'status': 'ok', 'message': 'Oggetto aggiornato con successo!'})

    # --- Logica di Vendita ---
    quantity_to_sell = form.cleaned_data.get('quantity_to_sell')

    if not quantity_to_sell or not (0 < quantity_to_sell <= item_to_process.quantity):
        return JsonResponse({'status': 'error', 'message': 'Quantità da vendere non valida.'}, status=400)

    production_cost_per_unit = item_to_process.material_cost / item_to_process.quantity if item_to_process.quantity > 0 else Decimal('0')
    labor_cost_per_unit = item_to_process.labor_cost / item_to_process.quantity if item_to_process.quantity > 0 else Decimal('0')
    
    # Update name if changed
    new_name = form.cleaned_data.get('name')
    if new_name:
        item_to_process.name = new_name

    if quantity_to_sell == item_to_process.quantity:
        item_to_process.status = 'SOLD'
        item_to_process.sold_at = form.cleaned_data.get('sold_at') or timezone.now().date()
        item_to_process.sale_price = form.cleaned_data.get('sale_price')
        item_to_process.payment_method = form.cleaned_data.get('payment_method')
        item_to_process.sold_to = form.cleaned_data.get('sold_to')
        item_to_process.notes = form.cleaned_data.get('notes')
        
        # Save all changes (including name)
        item_to_process.save()

        if item_to_process.payment_method and item_to_process.sale_price:
            net_revenue = item_to_process.get_net_revenue()
            item_to_process.payment_method.refresh_from_db()
            item_to_process.payment_method.balance += net_revenue
            item_to_process.payment_method.save()
    else:
        newly_sold_item = StockItem.objects.create(
            work_order=item_to_process.work_order,
            custom_id=item_to_process.custom_id,
            name=item_to_process.name, # This is already updated above
            quantity=quantity_to_sell,
            status='SOLD',
            material_cost=production_cost_per_unit * quantity_to_sell,
            labor_cost=labor_cost_per_unit * quantity_to_sell,
            suggested_price=item_to_process.suggested_price,
            sold_at=form.cleaned_data.get('sold_at') or timezone.now().date(),
            sale_price=form.cleaned_data.get('sale_price'),
            payment_method=form.cleaned_data.get('payment_method'),
            sold_to=form.cleaned_data.get('sold_to'),
            notes=form.cleaned_data.get('notes'),
        )
        item_to_process.quantity -= quantity_to_sell
        item_to_process.material_cost -= (production_cost_per_unit * quantity_to_sell)
        item_to_process.labor_cost -= (labor_cost_per_unit * quantity_to_sell)
        item_to_process.status = original_status
        # Note: item_to_process name was updated in memory, so if we save it here, the original remaining item ALSO gets the new name?
        # Usually when splitting, one might want to keep original name for remaining stack?
        # But if user edited the name in the "Sell" modal, they probably intended to name the SOLD item.
        # If I change item_to_process.name before split, both will get the name (since create uses it, and save uses it).
        # Scenario: "Widget" (qty 5). User sells 1, changes name to "Widget Sold". 
        # Result: "Widget Sold" (qty 1, sold) AND "Widget Sold" (qty 4, in stock).
        # This seems acceptable behavior if the user renames the "Item". 
        # If they wanted to only rename the sold part, that's more complex (split logic).
        # Given the UI "Dettagli Vendita", seeing "Oggetto: [input]" implies we are editing the item being sold.
        # Ideally only the sold item should get the name.
        
        # Let's Refine:
        # If partial sell, maybe we should ONLY apply name to the NEW item?
        # But the UI shows "Oggetto" which seems like the name of the row.
        # If I change it, I probably mean "This thing I am selling is actually X".
        # If I have 5 distinct X, and I sell one, and I call it Y, are the other 4 now Y?
        # If they are generic items, yes.
        # Let's stick to updating both for consistency, or standard behavior.
        # However, looking at the code I just wrote:
        # item_to_process.name = new_name
        # newly_sold_item = ... name=item_to_process.name
        # item_to_process.save()
        # Yes, both update. This is consistent.
        
        item_to_process.save()
        
        if newly_sold_item.payment_method and newly_sold_item.sale_price:
            net_revenue = newly_sold_item.get_net_revenue()
            newly_sold_item.payment_method.refresh_from_db()
            newly_sold_item.payment_method.balance += net_revenue
            newly_sold_item.payment_method.save()

    return JsonResponse({'status': 'ok', 'message': 'Oggetto venduto con successo!'})


@require_POST
@login_required
def delete_stock_item(request, item_id):
    item = get_object_or_404(StockItem, id=item_id)
    if item.status == 'SOLD':
        return JsonResponse({'status': 'error', 'message': 'Non puoi eliminare un oggetto già venduto da qui.'}, status=400)
    item.delete()
    return JsonResponse({'status': 'ok', 'message': 'Oggetto eliminato con successo.'})

@login_required
def export_stock_sales_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="export_magazzino_vendite_{timezone.now().strftime("%Y-%m-%d")}.csv"'
    response.write(u'\ufeff'.encode('utf8'))

    writer = csv.writer(response, delimiter=';')

    writer.writerow([
        'ID Oggetto', 'ID Progetto Origine', 'Categoria Progetto', 'Nome Oggetto', 'Stato', 'Quantita',
        'Costo Materiali (€)', 'Costo Manodopera (€)', 'Costo Totale Produzione (€)',
        'Prezzo Vendita Suggerito (Unità) (€)', 'Data Creazione', 'Data Vendita',
        'Prezzo Vendita Effettivo (Unità) (€)', 'Ricavo Totale (€)', 'Profitto (€)',
        'Venduto a', 'Metodo Pagamento', 'Note'
    ])

    items = StockItem.objects.all().select_related('work_order__category', 'payment_method').order_by('status', '-created_at')

    for item in items:
        total_revenue = (item.sale_price or 0) * item.quantity
        profit = total_revenue - (item.material_cost + item.labor_cost) if item.status == 'SOLD' else None

        writer.writerow([
            item.custom_id or item.id,
            item.work_order.custom_id if item.work_order else 'N/A',
            item.work_order.category.name if item.work_order and item.work_order.category else 'N/A',
            item.name,
            item.get_status_display(),
            item.quantity,
            f'{item.material_cost:.2f}'.replace('.', ','),
            f'{item.labor_cost:.2f}'.replace('.', ','),
            f'{item.total_cost:.2f}'.replace('.', ','),
            f'{item.suggested_price:.2f}'.replace('.', ','),
            item.created_at.strftime('%d/%m/%Y'),
            item.sold_at.strftime('%d/%m/%Y') if item.sold_at else '',
            f'{item.sale_price:.2f}'.replace('.', ',') if item.sale_price is not None else '',
            f'{total_revenue:.2f}'.replace('.', ',') if item.status == 'SOLD' else '',
            f'{profit:.2f}'.replace('.', ',') if profit is not None else '',
            item.sold_to,
            item.payment_method.name if item.payment_method else ('DA PAGARE' if item.status == 'SOLD' else ''),
            item.notes
        ])

    return response
