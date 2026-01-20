from decimal import Decimal
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import F, Sum
from django.db.models.functions import Coalesce

from ..models import StockItem, PaymentMethod
from ..forms import SaleEditForm

@login_required
def sales_dashboard(request):
    search_query = request.GET.get('q', '')
    sold_to_filter = request.GET.get('sold_to', '')
    payment_method_filter = request.GET.get('payment_method', '')
    notes_filter = request.GET.get('notes', '')
    start_date = request.GET.get('start_date', '')
    end_date = request.GET.get('end_date', '')

    sort_by = request.GET.get('sort', 'sold_at')
    order = request.GET.get('order', 'desc')
    order_prefix = '-' if order == 'desc' else ''

    sold_items_query = StockItem.objects.filter(status='SOLD').with_net_values().select_related('work_order', 'payment_method')

    filter_summary_parts = []
    if search_query:
        sold_items_query = sold_items_query.filter(name__icontains=search_query)
        filter_summary_parts.append(f'Nome: "{search_query}"')
    if sold_to_filter:
        sold_items_query = sold_items_query.filter(sold_to__icontains=sold_to_filter)
        filter_summary_parts.append(f'Venduto a: "{sold_to_filter}"')
    if payment_method_filter:
        if payment_method_filter == 'UNPAID':
            sold_items_query = sold_items_query.filter(payment_method__isnull=True)
            filter_summary_parts.append('Stato: DA PAGARE')
        else:
            sold_items_query = sold_items_query.filter(payment_method_id=payment_method_filter)
            try:
                method_name = PaymentMethod.objects.get(id=payment_method_filter).name
                filter_summary_parts.append(f'Metodo: {method_name}')
            except PaymentMethod.DoesNotExist:
                pass
    if notes_filter:
        sold_items_query = sold_items_query.filter(notes__icontains=notes_filter)
        filter_summary_parts.append(f'Note: "{notes_filter}"')
    if start_date:
        sold_items_query = sold_items_query.filter(sold_at__gte=start_date)
        filter_summary_parts.append(f'Da: {start_date}')
    if end_date:
        sold_items_query = sold_items_query.filter(sold_at__lte=end_date)
        filter_summary_parts.append(f'A: {end_date}')

    filter_summary = ", ".join(filter_summary_parts)
    filters_applied = bool(filter_summary_parts)
    
    valid_sort_fields = ['sold_at', 'name', 'annotated_net_revenue', 'annotated_production_cost', 'annotated_net_profit', 'sold_to']
    if sort_by not in valid_sort_fields:
        sort_by = 'sold_at'
    
    # We apply order_by here
    sold_items = sold_items_query.order_by(f'{order_prefix}{sort_by}')

    total_sales = sold_items_query.aggregate(total=Coalesce(Sum('annotated_net_revenue'), Decimal('0.00')))['total']
    total_profit = sold_items_query.aggregate(total=Coalesce(Sum('annotated_net_profit'), Decimal('0.00')))['total']

    context = {
        'sold_items': sold_items,
        'page_title': 'Vendite',
        'all_payment_methods': PaymentMethod.objects.all(),
        'sale_edit_form': SaleEditForm(),
        'search_query': search_query,
        'start_date': start_date,
        'end_date': end_date,
        'sold_to_filter': sold_to_filter,
        'payment_method_filter': payment_method_filter,
        'notes_filter': notes_filter,
        'sort_by': sort_by,
        'order': order,
        'total_sales': total_sales,
        'total_profit': total_profit,
        'filters_applied': bool(search_query or sold_to_filter or payment_method_filter or notes_filter or start_date or end_date),
    }
    return render(request, 'app_3dmage_management/sales.html', context)

@login_required
def get_sale_details(request, item_id):
    sale = get_object_or_404(StockItem.objects.select_related('work_order'), id=item_id, status='SOLD')
    data = {
        'id': sale.id,
        'item_custom_id': sale.custom_id,
        'project_id': sale.work_order.id if sale.work_order else None,
        'name': sale.name,
        'sold_at': sale.sold_at.strftime('%Y-%m-%d') if sale.sold_at else '',
        'sale_price': sale.sale_price,
        'payment_method': sale.payment_method.id if sale.payment_method else None,
        'sold_to': sale.sold_to,
        'notes': sale.notes,
        'total_cost': sale.material_cost + sale.labor_cost,
    }
    return JsonResponse(data)

@require_POST
@transaction.atomic
@login_required
def edit_sale(request, item_id):
    # Fetch the ORIGINAL sale instance
    sale = get_object_or_404(StockItem, id=item_id, status='SOLD')
    
    # CAPTURE OLD VALUES before the form modifies the instance!
    old_payment_method = sale.payment_method
    old_net_revenue = sale.get_net_revenue()

    form = SaleEditForm(request.POST, instance=sale)
    if form.is_valid():
        # 1. STORNA L'IMPORTO DAL VECCHIO METODO (Se esisteva)
        if old_payment_method:
            old_payment_method.refresh_from_db() # Cruciale per evitare dati vecchi
            old_payment_method.balance -= old_net_revenue
            old_payment_method.save()

        # 2. SALVA LE MODIFICHE ALLA VENDITA
        updated_sale = form.save()

        # 3. AGGIUNGI IL NUOVO IMPORTO AL NUOVO METODO (Se presente)
        if updated_sale.payment_method:
            new_method = updated_sale.payment_method
            new_method.refresh_from_db()
            net_amount = updated_sale.get_net_revenue()
            new_method.balance += net_amount
            new_method.save()

        return JsonResponse({'status': 'ok'})
    return JsonResponse({'status': 'error', 'errors': form.errors.as_json()}, status=400)


@require_POST
@transaction.atomic
@login_required
def reverse_sale(request, stock_item_id):
    sale_to_reverse = get_object_or_404(StockItem, id=stock_item_id, status='SOLD')

    if sale_to_reverse.payment_method:
        sale_to_reverse.payment_method.refresh_from_db()
        # Quando storniamo, dobbiamo togliere esattamente quanto abbiamo aggiunto (net revenue)
        net_to_reverse = sale_to_reverse.get_net_revenue()
        sale_to_reverse.payment_method.balance -= net_to_reverse
        sale_to_reverse.payment_method.save()

    existing_stock = StockItem.objects.filter(
        work_order=sale_to_reverse.work_order,
        custom_id=sale_to_reverse.custom_id,
        status='IN_STOCK'
    ).first()

    if existing_stock:
        existing_stock.quantity += sale_to_reverse.quantity
        existing_stock.material_cost += sale_to_reverse.material_cost
        existing_stock.save()
        sale_to_reverse.delete()
    else:
        sale_to_reverse.status = 'IN_STOCK'
        sale_to_reverse.sale_price = None
        sale_to_reverse.sold_at = None
        sale_to_reverse.payment_method = None
        sale_to_reverse.sold_to = ''
        sale_to_reverse.notes = ''
        sale_to_reverse.save()

    return redirect('inventory_dashboard')
