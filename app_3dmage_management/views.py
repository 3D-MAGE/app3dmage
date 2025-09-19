from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponse
from django.views.decorators.http import require_POST
import math
from django.db.models import Prefetch, Sum, Case, When, Value, IntegerField, F, Q, Count, Max, ExpressionWrapper, DecimalField, OuterRef, Subquery
from django.db.models.functions import Coalesce
from django.contrib.auth.decorators import login_required
from django.forms.models import model_to_dict
from django.utils import timezone
from django.db import transaction
from decimal import Decimal
from django.urls import reverse
import datetime
import json
import re
import csv


from .models import (
    Project, Printer, Plate, Filament, PrintFile, Spool, Category,
    StockItem, PaymentMethod, Expense, ExpenseCategory, FilamentUsage, ExpenseCategory, MaintenanceLog, GlobalSetting, Quote, Notification
)

from .forms import (
    ProjectForm, PrintFileForm, StockItemForm, CompleteProjectForm,
    PrintFileEditForm, FilamentForm, SpoolForm, ExpenseForm, TransferForm, CorrectBalanceForm,
    PrinterForm, PlateForm, CategoryForm, PaymentMethodForm, ExpenseCategoryForm, MaintenanceLogForm, GeneralSettingsForm, SaleEditForm, ManualStockItemForm, ManualIncomeForm, SpoolForm, SpoolEditForm
)

@login_required
def project_dashboard(request):
    # Filtri per Progetti Attivi
    search_query = request.GET.get('q', '')
    status_filter = request.GET.get('status', '')
    category_filter = request.GET.get('category', '')

    # Filtri per Progetti Completati
    completed_search_query = request.GET.get('q_completed', '')
    completed_year_filter = request.GET.get('year_completed', '')
    completed_category_filter = request.GET.get('category_completed', '')
    completed_filament_filter = request.GET.get('filament_completed', '')


    # Flag per mantenere aperte le sezioni dei filtri
    active_filters_applied = bool(search_query or status_filter or category_filter)
    completed_filters_applied = bool(completed_search_query or completed_year_filter or completed_category_filter or completed_filament_filter)

    # Anni disponibili per il filtro dei progetti completati
    completed_project_years = Project.objects.filter(
        status='DONE', completed_at__isnull=False
    ).dates('completed_at', 'year', order='DESC')

    all_projects = Project.objects.select_related('category').all()

    cost_annotation = Sum(
        ExpressionWrapper(
            F('print_files__filament_usages__grams_used') *
            F('print_files__filament_usages__spool__cost') /
            Case(
                When(print_files__filament_usages__spool__initial_weight_g=0, then=Value(1)),
                default=F('print_files__filament_usages__spool__initial_weight_g'),
                output_field=DecimalField()
            ),
            output_field=DecimalField()
        )
    )

    # --- Gestione Progetti Attivi ---
    sort_active = request.GET.get('sort_active', 'name')
    order_active = request.GET.get('order_active', 'asc')
    order_prefix_active = '-' if order_active == 'desc' else ''

    active_projects_query = all_projects.exclude(status='DONE').annotate(
        total_print_time_seconds=Sum('print_files__print_time_seconds', default=0),
        remaining_print_time_seconds=Sum(Case(When(print_files__status='TODO', then='print_files__print_time_seconds'), default=Value(0)), output_field=IntegerField()),
        annotated_material_cost=Coalesce(cost_annotation, Decimal('0.00'), output_field=DecimalField())
    )

    if search_query:
        # CORREZIONE: Migliorata la logica di ricerca per coerenza
        q_filter = Q(name__icontains=search_query) | Q(custom_id__icontains=search_query)
        if search_query.isdigit():
            q_filter |= Q(id=search_query)
        active_projects_query = active_projects_query.filter(q_filter)
    if status_filter:
        active_projects_query = active_projects_query.filter(status=status_filter)
    if category_filter:
        active_projects_query = active_projects_query.filter(category_id=category_filter)

    valid_sort_fields_active = ['name', 'priority', 'status', 'remaining_print_time_seconds', 'total_print_time_seconds', 'category__name']
    if sort_active not in valid_sort_fields_active:
        sort_active = 'name'
    active_projects = active_projects_query.order_by(f'{order_prefix_active}{sort_active}')

    # --- Gestione Progetti Completati ---
    sort_completed = request.GET.get('sort_completed', 'completed_at')
    order_completed = request.GET.get('order_completed', 'desc')
    order_prefix_completed = '-' if order_completed == 'desc' else ''

    completed_projects_query = all_projects.filter(status='DONE').prefetch_related(
        Prefetch(
            'print_files__filament_usages',
            queryset=FilamentUsage.objects.select_related('spool__filament'),
            to_attr='detailed_filament_usages'
        )
    ).annotate(
        total_print_time_seconds=Sum('print_files__print_time_seconds', default=0),
        annotated_material_cost=Coalesce(cost_annotation, Decimal('0.00'), output_field=DecimalField()),
        total_grams_used=Coalesce(Sum('print_files__filament_usages__grams_used'), Decimal('0.00'))
    )

    if completed_search_query:
        # CORREZIONE: Aggiunta la ricerca per ID numerico anche ai progetti completati
        q_filter_completed = Q(name__icontains=completed_search_query) | Q(custom_id__icontains=completed_search_query)
        if completed_search_query.isdigit():
            q_filter_completed |= Q(id=completed_search_query)
        completed_projects_query = completed_projects_query.filter(q_filter_completed)

    if completed_year_filter and completed_year_filter.isdigit():
        completed_projects_query = completed_projects_query.filter(completed_at__year=int(completed_year_filter))
    if completed_category_filter:
        completed_projects_query = completed_projects_query.filter(category_id=completed_category_filter)
    if completed_filament_filter:
        completed_projects_query = completed_projects_query.filter(print_files__filament_usages__spool__filament_id=completed_filament_filter).distinct()

    valid_sort_fields_completed = ['name', 'completed_at', 'total_print_time_seconds', 'annotated_material_cost', 'category__name', 'total_grams_used']
    if sort_completed not in valid_sort_fields_completed:
        sort_completed = 'completed_at'
    completed_projects = completed_projects_query.order_by(f'{order_prefix_completed}{sort_completed}')

    for project in completed_projects:
        usages = {}
        for pf in project.print_files.all():
            for usage in getattr(pf, 'detailed_filament_usages', []):
                filament = usage.spool.filament
                if filament.id not in usages:
                    usages[filament.id] = {
                        'name': str(filament),
                        'color_hex': filament.color_hex,
                    }
        project.filament_summary_details = list(usages.values())


    context = {
        'active_projects': active_projects,
        'completed_projects': completed_projects,
        'all_categories': Category.objects.all(),
        'all_filaments': Filament.objects.all().order_by('material', 'brand', 'color_name'),
        'all_statuses': Project.Status.choices,
        'project_form': ProjectForm(),
        'add_print_file_form': PrintFileForm(),
        'edit_print_file_form': PrintFileEditForm(),
        'page_title': 'Progetti',
        'current_view': 'table',
        'search_query': search_query,
        'status_filter': status_filter,
        'category_filter': category_filter,
        'active_filters_applied': active_filters_applied,
        'sort_active': sort_active,
        'order_active': order_active,
        'completed_search_query': completed_search_query,
        'completed_year_filter': completed_year_filter,
        'completed_category_filter': completed_category_filter,
        'completed_filament_filter': completed_filament_filter,
        'completed_filters_applied': completed_filters_applied,
        'completed_project_years': [d.year for d in completed_project_years],
        'sort_completed': sort_completed,
        'order_completed': order_completed,
    }
    return render(request, 'app_3dmage_management/dashboard.html', context)

@login_required
def project_kanban_board(request):
    kanban_columns = []
    statuses_to_show = [status for status in Project.Status.choices if status[0] != 'DONE']
    for status_id, status_name in statuses_to_show:
        projects_in_status = Project.objects.filter(status=status_id).prefetch_related('print_files')
        kanban_columns.append({'status_id': status_id, 'status_name': status_name, 'projects': projects_in_status})
    context = {'kanban_columns': kanban_columns, 'project_form': ProjectForm(), 'print_file_form': PrintFileForm(), 'page_title': 'Progetti', 'current_view': 'kanban'}
    return render(request, 'app_3dmage_management/kanban_board.html', context)

@login_required
def filament_dashboard(request):
    sort_by = request.GET.get('sort', 'material')
    order = request.GET.get('order', 'asc')
    order_prefix = '-' if order == 'desc' else ''

    # Sottoquery per contare le bobine attive per ciascun filamento
    active_spool_count_subquery = Spool.objects.filter(
        filament=OuterRef('pk'),
        is_active=True
    ).values('filament').annotate(c=Count('id')).values('c')

    # Annotiamo il conteggio su TUTTI i filamenti
    all_filaments = Filament.objects.annotate(
        annotated_active_spool_count=Coalesce(Subquery(active_spool_count_subquery, output_field=IntegerField()), 0)
    )

    # Filtriamo i filamenti che hanno almeno una bobina attiva
    active_filaments_query = all_filaments.filter(annotated_active_spool_count__gt=0)

    # Sottoquery per il peso iniziale delle bobine attive
    active_initial_weight_subquery = Spool.objects.filter(
        filament=OuterRef('pk'), is_active=True
    ).values('filament').annotate(s=Sum('initial_weight_g')).values('s')

    # Sottoquery per il peso usato dalle bobine attive
    active_used_weight_subquery = FilamentUsage.objects.filter(
        spool__filament=OuterRef('pk'), spool__is_active=True, print_file__status__in=['DONE', 'FAILED']
    ).values('spool__filament').annotate(s=Sum('grams_used')).values('s')

    # Sottoquery per la correzione manuale del peso
    active_adjustment_subquery = Spool.objects.filter(
        filament=OuterRef('pk'), is_active=True
    ).values('filament').annotate(s=Sum('weight_adjustment')).values('s')

    # Annotazioni aggiornate per calcolare il peso rimanente
    active_filaments_query = active_filaments_query.annotate(
        annotated_total_initial_weight=Coalesce(Subquery(active_initial_weight_subquery, output_field=DecimalField()), Decimal('0.00')),
        annotated_total_used_weight=Coalesce(Subquery(active_used_weight_subquery, output_field=DecimalField()), Decimal('0.00')),
        annotated_total_adjustment=Coalesce(Subquery(active_adjustment_subquery, output_field=DecimalField()), Decimal('0.00'))
    ).annotate(
        annotated_remaining_weight=ExpressionWrapper(
            F('annotated_total_initial_weight') + F('annotated_total_adjustment') - F('annotated_total_used_weight'),
            output_field=DecimalField()
        )
    )

    # NUOVA FUNZIONALITÀ: Aggiunto `annotated_active_spool_count` ai campi validi per l'ordinamento
    valid_sort_fields = ['material', 'brand', 'color_name', 'annotated_remaining_weight', 'annotated_total_used_weight', 'annotated_active_spool_count']
    if sort_by not in valid_sort_fields:
        sort_by = 'material'

    if sort_by == 'material':
        order_fields = (f'{order_prefix}material', f'{order_prefix}color_code', f'{order_prefix}brand')
    else:
        order_fields = (f'{order_prefix}{sort_by}',)

    active_filaments = active_filaments_query.order_by(*order_fields)

    # Filamenti esauriti (quelli con 0 bobine attive ma che hanno avuto bobine in passato)
    exhausted_filaments_query = all_filaments.filter(annotated_active_spool_count=0, spools__isnull=False).distinct()

    total_used_weight_subquery = FilamentUsage.objects.filter(
        spool__filament=OuterRef('pk'), print_file__status__in=['DONE', 'FAILED']
    ).values('spool__filament').annotate(s=Sum('grams_used')).values('s')

    exhausted_filaments = exhausted_filaments_query.annotate(
        total_grams_ever_used=Coalesce(Subquery(total_used_weight_subquery, output_field=DecimalField()), Decimal('0.00'))
    ).order_by('material', 'brand', 'color_code')

    context = {
        'active_filaments': active_filaments,
        'exhausted_filaments': exhausted_filaments,
        'filament_form': FilamentForm(),
        'spool_form': SpoolForm(),
        'spool_edit_form': SpoolEditForm(),
        'page_title': 'Filamenti',
        'sort_by': sort_by,
        'order': order
    }
    return render(request, 'app_3dmage_management/filaments.html', context)

@login_required
def inventory_dashboard(request):
    search_query = request.GET.get('q', '')
    status_filter = request.GET.get('status', '')
    sort_by = request.GET.get('sort', 'created_at')
    order = request.GET.get('order', 'desc')

    filters_applied = bool(search_query or status_filter)
    order_prefix = '-' if order == 'desc' else ''

    stock_items_query = StockItem.objects.exclude(status='SOLD').select_related('project').annotate(
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
    }
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
        item.project = None
        item.status = 'IN_STOCK'
        item.save()
        return JsonResponse({'status': 'ok'})
    return JsonResponse({'status': 'error', 'errors': form.errors.as_json()}, status=400)

@login_required
def get_stock_item_details(request, item_id):
    item = get_object_or_404(StockItem.objects.select_related('project'), id=item_id)
    data = model_to_dict(item)
    data['project_name'] = item.project.name if item.project else None
    # CORREZIONE BUG 1: Invia l'ID primario del progetto, non il custom_id che viene sovrascritto.
    data['project_id'] = item.project.id if item.project else None
    data['project_notes'] = item.project.notes if item.project else ''

    if item.quantity > 0:
        data['production_cost_per_unit'] = str(item.material_cost / item.quantity)
        data['labor_cost_per_unit'] = str(item.labor_cost / item.quantity)
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

    if item_to_process.project:
        project_notes = form.cleaned_data.get('project_notes')
        if project_notes is not None:
            item_to_process.project.notes = project_notes
            item_to_process.project.save()

    new_status = form.cleaned_data.get('status')

    if new_status != 'SOLD':
        form.save()
        return JsonResponse({'status': 'ok', 'message': 'Oggetto aggiornato con successo!'})

    # --- Logica di Vendita ---
    quantity_to_sell = form.cleaned_data.get('quantity_to_sell')

    if not quantity_to_sell or not (0 < quantity_to_sell <= item_to_process.quantity):
        return JsonResponse({'status': 'error', 'message': 'Quantità da vendere non valida.'}, status=400)

    # Calcola i costi unitari per una ripartizione corretta
    production_cost_per_unit = item_to_process.material_cost / item_to_process.quantity if item_to_process.quantity > 0 else Decimal('0')
    labor_cost_per_unit = item_to_process.labor_cost / item_to_process.quantity if item_to_process.quantity > 0 else Decimal('0')

    if quantity_to_sell == item_to_process.quantity:
        # Caso 1: Vendi l'intero lotto
        item_to_process.status = 'SOLD'
        item_to_process.sold_at = form.cleaned_data.get('sold_at') or timezone.now().date()
        item_to_process.sale_price = form.cleaned_data.get('sale_price')
        item_to_process.payment_method = form.cleaned_data.get('payment_method')
        item_to_process.sold_to = form.cleaned_data.get('sold_to')
        item_to_process.notes = form.cleaned_data.get('notes')
        item_to_process.save()

        if item_to_process.payment_method and item_to_process.sale_price:
            total_sale_price = item_to_process.sale_price * item_to_process.quantity
            item_to_process.payment_method.balance += total_sale_price
            item_to_process.payment_method.save()
    else:
        # Caso 2: Vendi una parte del lotto (split)
        newly_sold_item = StockItem.objects.create(
            project=item_to_process.project,
            custom_id=item_to_process.custom_id,
            name=item_to_process.name,
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
        # Aggiorna il lotto rimanente in magazzino
        item_to_process.quantity -= quantity_to_sell
        item_to_process.material_cost -= (production_cost_per_unit * quantity_to_sell)
        item_to_process.labor_cost -= (labor_cost_per_unit * quantity_to_sell)
        item_to_process.status = original_status
        item_to_process.save()

        if newly_sold_item.payment_method and newly_sold_item.sale_price:
            total_sale_price = newly_sold_item.sale_price * newly_sold_item.quantity
            newly_sold_item.payment_method.balance += total_sale_price
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

    sold_items_query = StockItem.objects.filter(status='SOLD').annotate(
        annotated_total_cost=F('material_cost') + F('labor_cost'),
        total_sale_price=F('sale_price') * F('quantity'),
        profit= (F('sale_price') * F('quantity')) - (F('material_cost') + F('labor_cost'))
    ).select_related('project', 'payment_method')


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

    valid_sort_fields = ['sold_at', 'name', 'total_sale_price', 'material_cost', 'profit', 'sold_to']
    if sort_by not in valid_sort_fields:
        sort_by = 'sold_at'
    sold_items = sold_items_query.order_by(f'{order_prefix}{sort_by}')

    total_sales = sold_items_query.aggregate(total=Coalesce(Sum('total_sale_price'), Decimal('0.00')))['total']
    total_profit = sold_items_query.aggregate(total=Coalesce(Sum('profit'), Decimal('0.00')))['total']

    context = {
        'sold_items': sold_items_query.order_by(f'{order_prefix}{sort_by}'),
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
def export_stock_sales_csv(request):
    """
    Esporta tutti i dati dal modello StockItem (magazzino e vendite) in un file CSV.
    """
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="export_magazzino_vendite_{timezone.now().strftime("%Y-%m-%d")}.csv"'
    response.write(u'\ufeff'.encode('utf8')) # BOM per Excel

    writer = csv.writer(response, delimiter=';')

    # Scrive l'intestazione del file CSV
    writer.writerow([
        'ID Oggetto', 'ID Progetto Origine', 'Categoria Progetto', 'Nome Oggetto', 'Stato', 'Quantita',
        'Costo Materiali (€)', 'Costo Manodopera (€)', 'Costo Totale Produzione (€)',
        'Prezzo Vendita Suggerito (Unità) (€)', 'Data Creazione', 'Data Vendita',
        'Prezzo Vendita Effettivo (Unità) (€)', 'Ricavo Totale (€)', 'Profitto (€)',
        'Venduto a', 'Metodo Pagamento', 'Note'
    ])

    # Recupera tutti gli oggetti, ordinandoli per stato e data
    items = StockItem.objects.all().select_related('project__category', 'payment_method').order_by('status', '-created_at')

    for item in items:
        total_revenue = (item.sale_price or 0) * item.quantity
        profit = total_revenue - (item.material_cost + item.labor_cost) if item.status == 'SOLD' else None

        writer.writerow([
            item.custom_id or item.id,
            item.project.custom_id if item.project else 'N/A',
            item.project.category.name if item.project and item.project.category else 'N/A',
            item.name,
            item.get_status_display(),
            item.quantity,
            f'{item.material_cost:.2f}'.replace('.', ','),
            f'{item.labor_cost:.2f}'.replace('.', ','),
            f'{item.total_cost:.2f}'.replace('.', ','),
            f'{item.suggested_price:.2f}'.replace('.', ','),
            item.created_at.strftime('%Y-%m-%d'),
            item.sold_at.strftime('%Y-%m-%d') if item.sold_at else '',
            f'{item.sale_price:.2f}'.replace('.', ',') if item.sale_price is not None else '',
            f'{total_revenue:.2f}'.replace('.', ',') if item.status == 'SOLD' else '',
            f'{profit:.2f}'.replace('.', ',') if profit is not None else '',
            item.sold_to,
            item.payment_method.name if item.payment_method else ('DA PAGARE' if item.status == 'SOLD' else ''),
            item.notes
        ])

    return response

@login_required
def get_sale_details(request, item_id):
    sale = get_object_or_404(StockItem.objects.select_related('project'), id=item_id, status='SOLD')
    # CORREZIONE BUG 2 e 3: Invia i dati corretti al frontend
    data = {
        'id': sale.id, # Manteniamo l'ID primario per l'URL del form
        'item_custom_id': sale.custom_id, # ID da mostrare per l'oggetto
        'project_id': sale.project.id if sale.project else None, # ID da mostrare per il progetto
        'name': sale.name,
        'sold_at': sale.sold_at.strftime('%Y-%m-%d') if sale.sold_at else '',
        'sale_price': sale.sale_price,
        'payment_method': sale.payment_method.id if sale.payment_method else None,
        'sold_to': sale.sold_to,
        'notes': sale.notes,
        'total_cost': sale.material_cost + sale.labor_cost, # Invia il costo totale
    }
    return JsonResponse(data)

@require_POST
@transaction.atomic
@login_required
def edit_sale(request, item_id):
    sale = get_object_or_404(StockItem, id=item_id, status='SOLD')
    old_total_price = (sale.sale_price or Decimal('0.00')) * sale.quantity
    old_payment_method = sale.payment_method

    form = SaleEditForm(request.POST, instance=sale)
    if form.is_valid():
        if old_payment_method:
            old_payment_method.balance -= old_total_price
            old_payment_method.save()

        updated_sale = form.save()

        new_payment_method = updated_sale.payment_method
        new_total_price = (updated_sale.sale_price or Decimal('0.00')) * updated_sale.quantity

        if new_payment_method:
            new_payment_method.balance += new_total_price
            new_payment_method.save()

        return JsonResponse({'status': 'ok'})
    return JsonResponse({'status': 'error', 'errors': form.errors.as_json()}, status=400)


@require_POST
@transaction.atomic
@login_required
def reverse_sale(request, stock_item_id):
    sale_to_reverse = get_object_or_404(StockItem, id=stock_item_id, status='SOLD')

    total_sale_price = (sale_to_reverse.sale_price or Decimal('0.00')) * sale_to_reverse.quantity
    if sale_to_reverse.payment_method:
        sale_to_reverse.payment_method.balance -= total_sale_price
        sale_to_reverse.payment_method.save()

    existing_stock = StockItem.objects.filter(
        project=sale_to_reverse.project,
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

@login_required
def print_queue_board(request):
    active_print_files_qs = PrintFile.objects.filter(
        status__in=['TODO', 'PRINTING']
    ).select_related(
        'project', 'printer', 'plate'
    ).prefetch_related(
        'filament_usages__spool__filament'
    ).order_by('queue_position')

    printers_qs = Printer.objects.prefetch_related(
        Prefetch('print_files', queryset=active_print_files_qs, to_attr='queued_files')
    ).annotate(
        total_queued_seconds=Sum(
            'print_files__print_time_seconds',
            filter=Q(print_files__status__in=['TODO', 'PRINTING'])
        )
    ).order_by('name')

    printers_list = []
    for printer in printers_qs:
        printing_file = next((f for f in printer.queued_files if f.status == 'PRINTING'), None)
        todo_files = [f for f in printer.queued_files if f.status == 'TODO']
        total_seconds = printer.total_queued_seconds or 0
        printer.total_queued_time_formatted = str(datetime.timedelta(seconds=total_seconds))
        printer.printing_file = printing_file
        printer.todo_files = todo_files
        printers_list.append(printer)

    context = {
        'printers': printers_list,
        'page_title': 'Coda di Stampa'
    }
    return render(request, 'app_3dmage_management/print_queue.html', context)

@login_required
def project_detail(request, project_id):
    queryset = Project.objects.prefetch_related(
        Prefetch('print_files', queryset=PrintFile.objects.select_related('printer', 'plate')
                 .prefetch_related('filament_usages__spool__filament').order_by('created_at'))
    )
    project = get_object_or_404(queryset, id=project_id)

    total_project_cost = sum(file.total_cost for file in project.print_files.all())

    referer = request.GET.get('from', 'kanban')

    if request.method == 'POST' and 'add_print_file_form' in request.POST:
        print_file_form = PrintFileForm(request.POST)
        if print_file_form.is_valid():
            new_print_file = print_file_form.save(commit=False)
            new_print_file.project = project
            minutes = print_file_form.cleaned_data['print_time_minutes']
            new_print_file.print_time_seconds = minutes * 60
            new_print_file.save()
            return redirect('project_detail', project_id=project.id)
    else:
        print_file_form = PrintFileForm(initial={'project': project})

    context = {
        'project': project,
        'total_project_cost': total_project_cost,
        'completion_form': CompleteProjectForm(initial={'stock_item_name': project.name, 'stock_item_quantity': project.quantity}),
        'edit_project_form': ProjectForm(instance=project),
        'add_print_file_form': print_file_form,
        'edit_print_file_form': PrintFileEditForm(),
        'can_be_completed': not project.print_files.filter(status__in=['TODO', 'PRINTING']).exists() and project.print_files.exists(),
        'page_title': 'Progetti',
        'referer': referer
    }
    return render(request, 'app_3dmage_management/project_detail.html', context)

@require_POST
@login_required
def add_project(request):
    form = ProjectForm(request.POST)
    if form.is_valid():
        form.save()
    return redirect(request.META.get('HTTP_REFERER', 'project_dashboard'))

@require_POST
@login_required
def edit_project(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    form = ProjectForm(request.POST, instance=project)
    if form.is_valid():
        form.save()
        return JsonResponse({'status': 'ok'})
    return JsonResponse({'status': 'error', 'errors': form.errors.as_json()}, status=400)

@require_POST
@transaction.atomic
@login_required
def complete_project(request, project_id):
    project = get_object_or_404(Project.objects.prefetch_related('print_files'), id=project_id)
    form = CompleteProjectForm(request.POST)

    if form.is_valid():
        current_year_str = timezone.now().strftime('%y')
        last_project_this_year = Project.objects.filter(custom_id__startswith=current_year_str, custom_id__regex=r'^\d{5}$').order_by('-custom_id').first()
        new_sequential = 1
        if last_project_this_year:
            try:
                last_sequential = int(last_project_this_year.custom_id[2:])
                new_sequential = last_sequential + 1
            except (ValueError, IndexError):
                pass
        new_custom_id = f"{current_year_str}{new_sequential:03d}"

        project.status = Project.Status.DONE
        project.completed_at = timezone.now()
        project.custom_id = new_custom_id
        project.save()

        # Dati dal form
        stock_item_quantity = form.cleaned_data['stock_item_quantity']
        labor_cost_for_batch = form.cleaned_data.get('labor_cost') or Decimal('0.00')

        # Dati dal progetto
        # Il costo di produzione è il costo totale del progetto (materiali + elettricità + usura)
        production_cost_for_batch = project.full_total_cost

        # Calcolo del prezzo suggerito per singolo oggetto
        total_cost_for_batch = production_cost_for_batch + labor_cost_for_batch

        # Prevenzione divisione per zero
        cost_per_item = total_cost_for_batch / stock_item_quantity if stock_item_quantity > 0 else Decimal('0.00')

        suggested_price_per_item = cost_per_item * Decimal('1.5')

        # Creazione/Aggiornamento dell'oggetto a magazzino
        stock_item, created = StockItem.objects.update_or_create(
            project=project,
            defaults={
                'custom_id': new_custom_id,
                'name': form.cleaned_data['stock_item_name'],
                'quantity': stock_item_quantity,
                # Salva i costi totali per l'intero lotto
                'material_cost': production_cost_for_batch.quantize(Decimal('0.01')),
                'labor_cost': labor_cost_for_batch.quantize(Decimal('0.01')),
                'status': StockItem.Status.IN_STOCK,
                'suggested_price': suggested_price_per_item.quantize(Decimal('0.01'))
            }
        )

        return redirect('inventory_dashboard')

    return redirect('project_detail', project_id=project.id)

@require_POST
@login_required
def delete_project(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    project.delete()
    return redirect('project_dashboard')

@require_POST
@login_required
@transaction.atomic
def add_print_file(request):
    try:
        filament_data = json.loads(request.POST.get('filament_data', '[]'))
        if not filament_data:
            return JsonResponse({'status': 'error', 'message': 'È richiesto almeno un filamento.'}, status=400)

        try:
            days = int(request.POST.get('print_time_days', 0) or 0)
            hours = int(request.POST.get('print_time_hours', 0) or 0)
            minutes = int(request.POST.get('print_time_minutes', 0) or 0)
            total_seconds = (days * 86400) + (hours * 3600) + (minutes * 60)
        except (ValueError, TypeError):
            return JsonResponse({'status': 'error', 'message': 'Il tempo di stampa deve essere un numero valido.'}, status=400)

        if total_seconds < 60:
            return JsonResponse({'status': 'error', 'message': 'Il tempo di stampa deve essere di almeno 1 minuto.'}, status=400)

        form = PrintFileForm(request.POST)
        if form.is_valid():
            print_file = form.save(commit=False)
            print_file.print_time_seconds = total_seconds

            if print_file.actual_quantity is None:
                print_file.actual_quantity = 0

            print_file.save()

            _handle_filament_data(
                request,
                print_file=print_file,
                filament_data_json=request.POST.get('filament_data', '[]')
            )

            project = print_file.project
            produced_per_print = print_file.produced_quantity

            objects_already_produced = project.print_files.exclude(id=print_file.id).aggregate(total=Sum('produced_quantity'))['total'] or 0

            if produced_per_print > 0:
                remaining_to_produce = project.quantity - objects_already_produced - produced_per_print

                if remaining_to_produce > 0:
                    copies_to_suggest = remaining_to_produce // produced_per_print
                    final_remainder = remaining_to_produce % produced_per_print

                    if copies_to_suggest > 0 or final_remainder > 0:
                         return JsonResponse({
                            'status': 'ok_suggestion',
                            'message': 'File aggiunto!',
                            'suggestion': {
                                'count': copies_to_suggest,
                                'remainder': final_remainder,
                                'file_id': print_file.id
                            }
                        })

            return JsonResponse({'status': 'ok', 'message': 'File aggiunto con successo!'})
        else:
            return JsonResponse({'status': 'error', 'errors': form.errors.as_json()}, status=400)

    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Dati filamento non validi.'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'Errore imprevisto: {str(e)}'}, status=500)

@require_POST
@transaction.atomic
@login_required
def clone_print_file(request):
    try:
        data = json.loads(request.body)
        original_file_id = data.get('file_id')
        count = int(data.get('count', 0))

        if not original_file_id or count <= 0:
            return JsonResponse({'status': 'error', 'message': 'Dati per la clonazione non validi.'}, status=400)

        original_file = PrintFile.objects.select_related('project').get(id=original_file_id)

        base_name = re.sub(r'\s\(\d+\)$', '', original_file.name).strip()
        for suffix in [" (Copia)", " (Da ristampare)"]:
             if base_name.endswith(suffix):
                base_name = base_name[:-len(suffix)]

        existing_files = PrintFile.objects.filter(
            project=original_file.project,
            name__startswith=base_name
        )
        max_num = 0
        if existing_files.filter(name=base_name).exists():
            max_num = 1
        for file in existing_files:
            match = re.search(r'\((\d+)\)$', file.name)
            if match:
                num = int(match.group(1))
                if num > max_num:
                    max_num = num

        start_num = max_num + 1

        for i in range(count):
            new_name = f"{base_name} ({start_num + i})"
            new_file = PrintFile.objects.create(
                project=original_file.project,
                name=new_name,
                printer=original_file.printer,
                plate=original_file.plate,
                print_time_seconds=original_file.print_time_seconds,
                status=PrintFile.Status.TODO,
                produced_quantity=original_file.produced_quantity,
                actual_quantity=0,
                queue_position=0
            )
            for usage in original_file.filament_usages.all():
                FilamentUsage.objects.create(
                    print_file=new_file,
                    spool=usage.spool,
                    grams_used=usage.grams_used
                )

        return JsonResponse({'status': 'ok', 'message': f'{count} copie create con successo.'})
    except PrintFile.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'File originale non trovato.'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'Errore durante la clonazione: {str(e)}'}, status=500)


@require_POST
@login_required
def edit_print_file(request, file_id):
    instance = get_object_or_404(PrintFile, id=file_id)

    try:
        filament_data = json.loads(request.POST.get('filament_data', '[]'))
        if not filament_data:
            return JsonResponse({'status': 'error', 'message': 'È richiesto almeno un filamento.'}, status=400)

        try:
            days = int(request.POST.get('print_time_days', 0) or 0)
            hours = int(request.POST.get('print_time_hours', 0) or 0)
            minutes = int(request.POST.get('print_time_minutes', 0) or 0)
            total_seconds = (days * 86400) + (hours * 3600) + (minutes * 60)
        except (ValueError, TypeError):
            return JsonResponse({'status': 'error', 'message': 'Il tempo di stampa deve essere un numero valido.'}, status=400)

        if total_seconds < 60:
            return JsonResponse({'status': 'error', 'message': 'Il tempo di stampa deve essere di almeno 1 minuto.'}, status=400)

        form = PrintFileEditForm(request.POST, instance=instance)
        if form.is_valid():
            new_status = form.cleaned_data.get('status')

            if new_status == 'DONE' and instance.project.status != 'TODO':
                 return JsonResponse({
                    'status': 'error',
                    'message': 'Impossibile segnare come "Stampato" se il progetto non è in stato "Pronto da Stampare".'
                }, status=400)

            print_file = form.save(commit=False)
            print_file.print_time_seconds = total_seconds

            if print_file.actual_quantity is None:
                print_file.actual_quantity = 0

            print_file.save()

            wasted_grams_str = request.POST.get('wasted_grams') if new_status == 'FAILED' else None

            _handle_filament_data(
                request,
                print_file=print_file,
                filament_data_json=request.POST.get('filament_data', '[]'),
                wasted_grams_str=wasted_grams_str
            )

            return JsonResponse({'status': 'ok', 'message': 'Modifiche salvate!', 'new_print_status': print_file.status})
        else:
            return JsonResponse({'status': 'error', 'errors': form.errors.as_json()}, status=400)

    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Dati filamento non validi.'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'Errore imprevisto: {str(e)}'}, status=500)

@require_POST
@transaction.atomic
@login_required
def requeue_print_file(request, file_id):
    try:
        original_file = get_object_or_404(PrintFile, id=file_id)

        data = json.loads(request.body)
        planned_filaments = data.get('filaments', [])

        new_file = PrintFile.objects.create(
            project=original_file.project,
            name=f"{original_file.name.replace(' (Da ristampare)', '')} (Da ristampare)",
            printer=original_file.printer,
            plate=original_file.plate,
            print_time_seconds=original_file.print_time_seconds,
            status=PrintFile.Status.TODO,
            queue_position=0
        )

        if planned_filaments:
            for usage_data in planned_filaments:
                spool_id = usage_data.get('spool_id')
                grams = usage_data.get('grams')
                if spool_id and grams:
                    spool = get_object_or_404(Spool, id=spool_id)
                    FilamentUsage.objects.create(
                        print_file=new_file,
                        spool=spool,
                        grams_used=grams
                    )
        else:
            for usage in original_file.filament_usages.all():
                FilamentUsage.objects.create(
                    print_file=new_file,
                    spool=usage.spool,
                    grams_used=usage.grams_used
                )

        return JsonResponse({'status': 'ok', 'message': 'File rimesso in coda con successo.'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
def get_print_file_details(request, file_id):
    print_file = get_object_or_404(PrintFile, id=file_id)
    data = model_to_dict(print_file, fields=['name', 'printer', 'plate', 'status', 'produced_quantity', 'actual_quantity'])
    data['print_time_seconds'] = print_file.print_time_seconds
    data['filaments_used'] = list(print_file.filament_usages.select_related('spool__filament').values('spool__filament_id', 'spool_id', 'grams_used'))
    return JsonResponse(data)

@login_required
def api_get_all_projects(request):
    projects = Project.objects.filter(status__in=['QUOTE', 'TODO', 'POST']).order_by('name')
    data = [{'id': p.id, 'name': p.name} for p in projects]
    return JsonResponse(data, safe=False)


@require_POST
@login_required
def delete_print_file(request, file_id):
    try:
        print_file = get_object_or_404(PrintFile, id=file_id)
        print_file.delete()
        return JsonResponse({'status': 'ok', 'message': 'File eliminato con successo.'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@require_POST
@login_required
def update_project_status(request):
    try:
        data = json.loads(request.body)
        project_id, new_status = data.get('project_id'), data.get('new_status')
        if not project_id or not new_status:
            return HttpResponseBadRequest("Dati mancanti.")
        project = Project.objects.get(id=project_id)
        project.status = new_status
        project.save()
        return JsonResponse({'status': 'ok', 'message': f'Progetto {project.name} aggiornato'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@require_POST
@login_required
def update_print_queue(request):
    try:
        data = json.loads(request.body)
        printer_id, ordered_file_ids = data.get('printer_id'), data.get('file_ids', [])
        PrintFile.objects.filter(id__in=ordered_file_ids).update(printer_id=printer_id)
        for index, file_id in enumerate(ordered_file_ids):
            PrintFile.objects.filter(id=file_id).update(queue_position=index)
        return JsonResponse({'status': 'ok', 'message': 'Coda di stampa aggiornata.'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@login_required
def load_plates(request):
    printer_id = request.GET.get('printer_id')
    try:
        plates = Plate.objects.filter(printer_id=printer_id).values('id', 'name')
        return JsonResponse(list(plates), safe=False)
    except (ValueError, TypeError):
        return JsonResponse([], safe=False)

@require_POST
@login_required
def reprint_project(request, project_id):
    original_project = get_object_or_404(Project.objects.prefetch_related('print_files__filament_usages__spool'), id=project_id)

    new_project = Project.objects.create(
        name=f"{original_project.name} (Ristampa)",
        category=original_project.category,
        priority=original_project.priority,
        quantity=original_project.quantity,
        notes=original_project.notes,
        status=Project.Status.TODO
    )

    for old_file in original_project.print_files.exclude(status='FAILED'):
        new_file = PrintFile.objects.create(
            project=new_project,
            name=old_file.name,
            printer=old_file.printer,
            plate=old_file.plate,
            print_time_seconds=old_file.print_time_seconds,
            status=PrintFile.Status.TODO
        )
        for usage in old_file.filament_usages.all():
            FilamentUsage.objects.create(
                print_file=new_file,
                spool=usage.spool,
                grams_used=usage.grams_used
            )

    return redirect('project_dashboard')

@require_POST
@login_required
def update_project_inline(request, project_id):
    try:
        data = json.loads(request.body)
        field = data.get('field')
        value = data.get('value')

        project = get_object_or_404(Project, id=project_id)

        if field not in ['status', 'priority']:
            return JsonResponse({'status': 'error', 'message': 'Campo non valido.'}, status=400)

        setattr(project, field, value)
        project.save()

        return JsonResponse({'status': 'ok', 'message': f'Campo {field} aggiornato.'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@require_POST
@transaction.atomic
@login_required
def add_spool(request):
    form = SpoolForm(request.POST)
    if form.is_valid():
        filament = form.cleaned_data['filament']
        purchase_date = form.cleaned_data['purchase_date']

        existing_spools_count = Spool.objects.filter(
            filament=filament,
            purchase_date__year=purchase_date.year,
            purchase_date__month=purchase_date.month
        ).count()

        new_identifier = ""
        if existing_spools_count > 0:
            new_identifier = chr(ord('A') + existing_spools_count)

        spool = form.save(commit=False)
        spool.identifier = new_identifier
        spool.save()

        payment_method = form.cleaned_data['payment_method']
        cost = form.cleaned_data['cost']
        material_category, created = ExpenseCategory.objects.get_or_create(name='Bobine')

        expense_description = f"Bobina {spool.filament} {spool}"

        Expense.objects.create(
            description=expense_description,
            amount=cost, category=material_category,
            expense_date=spool.purchase_date, payment_method=payment_method
        )

        payment_method.balance -= cost
        payment_method.save()

    return redirect('filament_dashboard')

@require_POST
@login_required
def delete_spool(request, spool_id):
    spool = get_object_or_404(Spool, id=spool_id)
    if spool.usages.exists():
        return JsonResponse({
            'status': 'error',
            'message': 'Impossibile eliminare: questa bobina è stata usata in una o più stampe.'
        }, status=400)

    related_expense = Expense.objects.filter(
        description=f"Acquisto bobina: {spool.filament}",
        amount=spool.cost,
        expense_date=spool.purchase_date
    ).first()

    if related_expense and related_expense.payment_method:
        related_expense.payment_method.balance += related_expense.amount
        related_expense.payment_method.save()
        related_expense.delete()

    spool.delete()
    return JsonResponse({'status': 'ok', 'message': 'Bobina eliminata con successo.'})

@login_required
def get_filament_details(request, filament_id):
    filament = get_object_or_404(Filament, id=filament_id)
    return JsonResponse(model_to_dict(filament))

@require_POST
@login_required
def add_filament(request):
    form = FilamentForm(request.POST)
    if form.is_valid():
        form.save()
        # BUG 1 FIX: Risponde con JSON per la gestione AJAX, invece di un redirect
        return JsonResponse({'status': 'ok'})
    return JsonResponse({'status': 'error', 'errors': form.errors.as_json()}, status=400)

@require_POST
@login_required
def edit_filament(request, filament_id):
    instance = get_object_or_404(Filament, id=filament_id)
    form = FilamentForm(request.POST, instance=instance)
    if form.is_valid():
        form.save()
        return JsonResponse({'status': 'ok'})
    return JsonResponse({'status': 'error', 'errors': form.errors.as_json()}, status=400)

@require_POST
@login_required
def delete_filament(request, filament_id):
    filament = get_object_or_404(Filament, id=filament_id)
    if filament.spools.exists():
        return JsonResponse({'status': 'error', 'message': 'Non puoi eliminare un filamento con bobine associate.'}, status=400)
    filament.delete()
    return JsonResponse({'status': 'ok'})

@login_required
def get_spools_for_filament(request):
    filament_id = request.GET.get('filament_id')
    spools = Spool.objects.filter(filament_id=filament_id, is_active=True)

    spools_data = []
    for spool in spools:
        used_on_spool = spool.usages.filter(print_file__status__in=['DONE', 'FAILED']).aggregate(total=Sum('grams_used'))['total'] or 0
        remaining = spool.initial_weight_g - used_on_spool
        if remaining > 0:
            spools_data.append({
                'id': spool.id,
                'purchase_date': spool.purchase_date.strftime('%d/%m/%Y'),
                'remaining': remaining
            })
    return JsonResponse(spools_data, safe=False)

def _handle_filament_data(request, print_file, filament_data_json, wasted_grams_str=None):
    """Funzione helper per gestire i dati dei filamenti."""
    print_file.filament_usages.all().delete()
    filament_data = json.loads(filament_data_json)

    wasted_grams = None
    if wasted_grams_str:
        try:
            val = Decimal(wasted_grams_str)
            wasted_grams = val if val >= 0 else None
        except:
            wasted_grams = None

    if wasted_grams is not None and filament_data:
        total_planned_grams = sum(Decimal(usage.get('grams', 0)) for usage in filament_data if usage.get('grams'))

        if total_planned_grams > 0:
            actual_wasted_grams = min(wasted_grams, total_planned_grams)
            ratio = actual_wasted_grams / total_planned_grams
            for usage in filament_data:
                spool_id = usage.get('spool_id')
                planned_grams = Decimal(usage.get('grams', 0))
                if spool_id and planned_grams > 0:
                    spool = get_object_or_404(Spool, id=spool_id)
                    actual_grams_used = planned_grams * ratio
                    FilamentUsage.objects.create(print_file=print_file, spool=spool, grams_used=actual_grams_used)
    else:
        for usage in filament_data:
            spool_id = usage.get('spool_id')
            grams = usage.get('grams')
            if spool_id and grams and Decimal(grams) > 0:
                spool = get_object_or_404(Spool, id=spool_id)
                FilamentUsage.objects.create(print_file=print_file, spool=spool, grams_used=grams)

@login_required
def api_get_all_filaments(request):
    # BUG 1 FIX: Questa API ora fornisce sempre l'elenco più aggiornato dei filamenti,
    # che verrà richiamata dopo l'aggiunta di un nuovo tipo.
    # Ho rimosso il filtro sulle bobine attive per popolare correttamente il dropdown
    # anche con filamenti a cui non è ancora stata associata una bobina.
    filaments = Filament.objects.all().order_by('material', 'brand', 'color_name')
    data = [{'id': f.id, 'name': str(f), 'color_hex': f.color_hex} for f in filaments]
    return JsonResponse(data, safe=False)

@login_required
def api_get_filament_spools(request, filament_id):
    spools = Spool.objects.filter(filament_id=filament_id).order_by('identifier')
    active_spools_data = []
    inactive_spools_data = []

    for spool in spools:
        used_on_spool = spool.usages.filter(
            print_file__status__in=['DONE', 'FAILED']
        ).aggregate(total=Sum('grams_used'))['total'] or Decimal('0')

        remaining = (Decimal(spool.initial_weight_g) + spool.weight_adjustment) - used_on_spool

        spool_data = {
            'id': spool.id,
            'text': str(spool),
            'remaining': remaining,
            'cost': f"{spool.cost}€",
            'purchase_link': spool.purchase_link,
            'is_active': spool.is_active
        }

        if spool.is_active:
             active_spools_data.append(spool_data)
        else:
             inactive_spools_data.append(spool_data)


    return JsonResponse({
        'active_spools': active_spools_data,
        'inactive_spools': inactive_spools_data
    })

@require_POST
@login_required
def toggle_spool_status(request, spool_id):
    spool = get_object_or_404(Spool, id=spool_id)
    spool.is_active = not spool.is_active
    spool.save()
    return JsonResponse({'status': 'ok', 'is_active': spool.is_active})

@login_required
def get_spool_details(request, spool_id):
    spool = get_object_or_404(Spool, id=spool_id)
    data = model_to_dict(spool, fields=['id', 'cost', 'purchase_link', 'is_active', 'weight_adjustment'])
    return JsonResponse(data)

@require_POST
@login_required
def edit_spool(request, spool_id):
    spool = get_object_or_404(Spool, id=spool_id)
    form = SpoolEditForm(request.POST, instance=spool)
    if form.is_valid():
        correction = form.cleaned_data.get('correction') or 0

        spool.cost = form.cleaned_data.get('cost')
        spool.purchase_link = form.cleaned_data.get('purchase_link')
        spool.is_active = form.cleaned_data.get('is_active')
        spool.weight_adjustment += correction
        spool.save()

        return JsonResponse({'status': 'ok'})
    return JsonResponse({'status': 'error', 'errors': form.errors.as_json()}, status=400)

@login_required
def accounting_dashboard(request):
    search_query = request.GET.get('q', '')
    year_filter = request.GET.get('year', '')
    payment_method_filter = request.GET.get('payment_method', '')
    category_filter = request.GET.get('category', '')

    income_items_query = StockItem.objects.filter(status='SOLD', payment_method__isnull=False)
    if search_query:
        income_items_query = income_items_query.filter(
            Q(name__icontains=search_query) | Q(notes__icontains=search_query)
        )

    expenses_query = Expense.objects.select_related('category', 'payment_method')
    if search_query:
        expenses_query = expenses_query.filter(
            Q(description__icontains=search_query) | Q(notes__icontains=search_query)
        )

    if year_filter:
        income_items_query = income_items_query.filter(sold_at__year=year_filter)
        expenses_query = expenses_query.filter(expense_date__year=year_filter)
    if payment_method_filter:
        income_items_query = income_items_query.filter(payment_method_id=payment_method_filter)
        expenses_query = expenses_query.filter(payment_method_id=payment_method_filter)

    if category_filter:
        expenses_query = expenses_query.filter(category_id=category_filter)

    income_items = income_items_query.select_related('payment_method').order_by('-sold_at', '-id')
    expenses = expenses_query.order_by('-expense_date', '-id')

    total_income = income_items.annotate(total_price=F('quantity') * F('sale_price')).aggregate(total=Sum('total_price'))['total'] or Decimal('0.00')
    total_expenses = expenses.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    profit = total_income - total_expenses
    total_cash = PaymentMethod.objects.aggregate(total=Sum('balance'))['total'] or Decimal('0.00')

    income_years = StockItem.objects.filter(sold_at__isnull=False, payment_method__isnull=False).dates('sold_at', 'year', order='DESC')
    expense_years = Expense.objects.dates('expense_date', 'year', order='DESC')
    available_years = sorted(list(set([d.year for d in income_years] + [d.year for d in expense_years])), reverse=True)

    context = {
        'income_items': income_items, 'total_income': total_income, 'expenses': expenses,
        'total_expenses': total_expenses, 'payment_methods': PaymentMethod.objects.all(),
        'all_payment_methods': PaymentMethod.objects.all(),
        'all_expense_categories': ExpenseCategory.objects.all(),
        'profit': profit,
        'total_cash': total_cash, 'expense_form': ExpenseForm(),
        'manual_income_form': ManualIncomeForm(),
        'transfer_form': TransferForm(), 'correct_balance_form': CorrectBalanceForm(),
        'available_years': available_years, 'search_query': search_query,
        'year_filter': year_filter, 'payment_method_filter': payment_method_filter,
        'category_filter': category_filter,
        'page_title': 'Contabilità'
    }
    return render(request, 'app_3dmage_management/accounting.html', context)


@require_POST
@transaction.atomic
@login_required
def add_manual_income(request):
    form = ManualIncomeForm(request.POST)
    if form.is_valid():
        income = form.save(commit=False)
        income.status = 'SOLD'
        income.quantity = 1
        income.material_cost = 0
        if income.payment_method and income.sale_price:
            income.payment_method.balance += income.sale_price
            income.payment_method.save()
        income.save()
    return redirect('accounting_dashboard')

@require_POST
@login_required
def add_expense(request):
    form = ExpenseForm(request.POST)
    if form.is_valid():
        expense = form.save(commit=False)
        if expense.payment_method and expense.amount:
            expense.payment_method.balance -= expense.amount
            expense.payment_method.save()
        expense.save()
    return redirect('accounting_dashboard')

@require_POST
@login_required
def transfer_funds(request):
    form = TransferForm(request.POST)
    if form.is_valid():
        amount = form.cleaned_data['amount']
        source = form.cleaned_data['source']
        destination = form.cleaned_data['destination']

        source.balance -= amount
        destination.balance += amount
        source.save()
        destination.save()
    return redirect('accounting_dashboard')

@require_POST
@login_required
def correct_balance(request, method_id):
    payment_method = get_object_or_404(PaymentMethod, id=method_id)
    form = CorrectBalanceForm(request.POST)
    if form.is_valid():
        payment_method.balance = form.cleaned_data['new_balance']
        payment_method.save()
    return redirect('accounting_dashboard')

@login_required
def get_expense_details(request, expense_id):
    expense = get_object_or_404(Expense, id=expense_id)
    data = model_to_dict(expense)
    if data.get('expense_date'):
        data['expense_date'] = data['expense_date'].strftime('%Y-%m-%d')
    return JsonResponse(data)

@require_POST
@login_required
def edit_expense(request, expense_id):
    expense = get_object_or_404(Expense, id=expense_id)
    old_amount = expense.amount
    old_payment_method = expense.payment_method

    form = ExpenseForm(request.POST, instance=expense)
    if form.is_valid():
        if old_payment_method and old_amount:
            old_payment_method.balance += old_amount
            old_payment_method.save()

        updated_expense = form.save()

        if updated_expense.payment_method and updated_expense.amount:
            updated_expense.payment_method.balance -= updated_expense.amount
            updated_expense.payment_method.save()

        return JsonResponse({'status': 'ok'})
    return JsonResponse({'status': 'error', 'errors': form.errors.as_json()}, status=400)

@require_POST
@login_required
def delete_expense(request, expense_id):
    expense = get_object_or_404(Expense, id=expense_id)
    if expense.payment_method and expense.amount:
        expense.payment_method.balance += expense.amount
        expense.payment_method.save()
    expense.delete()
    return JsonResponse({'status': 'ok'})

@login_required
def settings_dashboard(request):
    year_filter = request.GET.get('year', '')
    electricity_cost_obj, _ = GlobalSetting.objects.get_or_create(
        key='electricity_cost_kwh',
        defaults={'value': Decimal('0.25')}
    )
    electricity_cost_kwh = electricity_cost_obj.value

    available_years_dates = Project.objects.filter(
        status='DONE',
        completed_at__isnull=False
    ).dates('completed_at', 'year', order='DESC')
    available_years = [d.year for d in available_years_dates]

    # BUG FIX 2 & 3: Il filtro ora si applica a un'unica annotazione per tempo e costi.
    # Se non è selezionato un anno, il filtro include tutti i file completati.
    time_cost_filter = Q(print_files__status='DONE')
    if year_filter and year_filter.isdigit():
        time_cost_filter &= Q(print_files__project__completed_at__year=int(year_filter))

    printers_query = Printer.objects.prefetch_related('plates', 'maintenance_logs').annotate(
        plate_count=Count('plates', distinct=True),
        maintenance_count=Count('maintenance_logs', distinct=True),

        # BUG FIX 2 & 3: Questa annotazione ora calcola i secondi di stampa per il periodo rilevante (filtrato o totale).
        relevant_print_seconds=Coalesce(Sum(
            'print_files__print_time_seconds',
            filter=time_cost_filter,
            distinct=True
        ), 0),

        seconds_since_maintenance=Coalesce(Sum(
            'print_files__print_time_seconds',
            filter=Q(print_files__status='DONE', print_files__project__completed_at__gte=F('last_maintenance_reset')),
            distinct=True
        ), 0)
    ).annotate(
        # BUG FIX 2 & 3: Il costo viene calcolato sulla base dei secondi già aggregati, rendendo il calcolo più affidabile.
        annotated_electricity_cost=ExpressionWrapper(
            (F('relevant_print_seconds') / Decimal(3600.0)) *
            (F('power_consumption') / Decimal(1000.0)) *
            electricity_cost_kwh,
            output_field=DecimalField()
        )
    ).order_by('name')

    printers = []
    for printer in printers_query:
        # BUG FIX 2 & 3: Si formatta il tempo rilevante (filtrato o totale) da mostrare nel template.
        relevant_seconds = printer.relevant_print_seconds
        h_relevant = relevant_seconds // 3600
        m_relevant = (relevant_seconds % 3600) // 60
        printer.relevant_print_time_formatted = f"{h_relevant} ore {m_relevant} min"

        partial_seconds = printer.seconds_since_maintenance
        h_partial = partial_seconds // 3600
        m_partial = (partial_seconds % 3600) // 60
        printer.partial_print_time_formatted = f"{h_partial} ore {m_partial} min"

        printers.append(printer)

    categories = Category.objects.annotate(project_count=Count('project')).order_by('name')
    payment_methods = PaymentMethod.objects.annotate(expense_count=Count('expense'), sale_count=Count('stockitem')).order_by('name')
    expense_categories = ExpenseCategory.objects.annotate(expense_count=Count('expense')).order_by('name')

    wear_tear_obj, _ = GlobalSetting.objects.get_or_create(
        key='wear_tear_coefficient',
        defaults={'value': Decimal('0.10')}
    )
    initial_data = {
        'electricity_cost': electricity_cost_obj.value,
        'wear_tear_coefficient': wear_tear_obj.value
    }

    context = {
        'printers': printers,
        'categories': categories,
        'payment_methods': payment_methods,
        'expense_categories': expense_categories,
        'printer_form': PrinterForm(),
        'plate_form': PlateForm(),
        'category_form': CategoryForm(),
        'payment_method_form': PaymentMethodForm(),
        'expense_category_form': ExpenseCategoryForm(),
        'maintenance_form': MaintenanceLogForm(),
        'general_settings_form': GeneralSettingsForm(initial=initial_data),
        'page_title': 'Impostazioni',
        'available_years': available_years,
        'selected_year': int(year_filter) if year_filter.isdigit() else None,
    }
    return render(request, 'app_3dmage_management/settings.html', context)

@require_POST
@login_required
def reset_maintenance_counter(request, printer_id):
    printer = get_object_or_404(Printer, id=printer_id)
    printer.last_maintenance_reset = timezone.now()
    printer.save()
    return JsonResponse({'status': 'ok', 'message': f'Contatore per {printer.name} azzerato.'})

@require_POST
@login_required
def update_general_settings(request):
    form = GeneralSettingsForm(request.POST)
    if form.is_valid():
        GlobalSetting.objects.update_or_create(
            key='electricity_cost_kwh',
            defaults={'value': form.cleaned_data['electricity_cost']}
        )
        GlobalSetting.objects.update_or_create(
            key='wear_tear_coefficient',
            defaults={'value': form.cleaned_data['wear_tear_coefficient']}
        )
    return redirect('settings_dashboard')


# --- Viste per AGGIUNGERE ---
@require_POST
@login_required
def add_printer(request):
    form = PrinterForm(request.POST)
    if form.is_valid(): form.save()
    return redirect('settings_dashboard')

@require_POST
@login_required
def add_plate(request):
    form = PlateForm(request.POST)
    if form.is_valid(): form.save()
    return redirect('settings_dashboard')

@require_POST
@login_required
def add_category(request):
    form = CategoryForm(request.POST)
    if form.is_valid(): form.save()
    return redirect('settings_dashboard')

@require_POST
@login_required
def add_payment_method(request):
    form = PaymentMethodForm(request.POST)
    if form.is_valid(): form.save()
    return redirect('settings_dashboard')

@require_POST
@login_required
def add_expense_category(request):
    form = ExpenseCategoryForm(request.POST)
    if form.is_valid(): form.save()
    return redirect('settings_dashboard')

# --- Viste per PRENDERE DETTAGLI (AJAX) ---
@require_POST
@login_required
def get_printer_details(request, pk):
    return JsonResponse(model_to_dict(get_object_or_404(Printer, pk=pk)))

@require_POST
@login_required
def get_plate_details(request, pk):
    return JsonResponse(model_to_dict(get_object_or_404(Plate, pk=pk)))

@require_POST
@login_required
def get_category_details(request, pk):
    return JsonResponse(model_to_dict(get_object_or_404(Category, pk=pk)))

@require_POST
@login_required
def get_payment_method_details(request, pk):
    return JsonResponse(model_to_dict(get_object_or_404(PaymentMethod, pk=pk)))

@require_POST
@login_required
def get_expense_category_details(request, pk):
    return JsonResponse(model_to_dict(get_object_or_404(ExpenseCategory, pk=pk)))

# --- Viste per MODIFICARE ---
@require_POST
@login_required
def edit_printer(request, pk):
    instance = get_object_or_404(Printer, pk=pk)
    form = PrinterForm(request.POST, instance=instance)
    if form.is_valid():
        form.save()
        return JsonResponse({'status': 'ok'})
    return JsonResponse({'status': 'error', 'errors': form.errors.as_json()}, status=400)

@require_POST
@login_required
def edit_plate(request, pk):
    instance = get_object_or_404(Plate, pk=pk)
    form = PlateForm(request.POST, instance=instance)
    if form.is_valid():
        form.save()
        return JsonResponse({'status': 'ok'})
    return JsonResponse({'status': 'error', 'errors': form.errors.as_json()}, status=400)

@require_POST
@login_required
def edit_category(request, pk):
    instance = get_object_or_404(Category, pk=pk)
    form = CategoryForm(request.POST, instance=instance)
    if form.is_valid():
        form.save()
        return JsonResponse({'status': 'ok'})
    return JsonResponse({'status': 'error', 'errors': form.errors.as_json()}, status=400)

@require_POST
@login_required
def edit_payment_method(request, pk):
    instance = get_object_or_404(PaymentMethod, pk=pk)
    form = PaymentMethodForm(request.POST, instance=instance)
    if form.is_valid():
        form.save()
        return JsonResponse({'status': 'ok'})
    return JsonResponse({'status': 'error', 'errors': form.errors.as_json()}, status=400)

@require_POST
@login_required
def edit_expense_category(request, pk):
    instance = get_object_or_404(ExpenseCategory, pk=pk)
    form = ExpenseCategoryForm(request.POST, instance=instance)
    if form.is_valid():
        form.save()
        return JsonResponse({'status': 'ok'})
    return JsonResponse({'status': 'error', 'errors': form.errors.as_json()}, status=400)

# --- Viste per ELIMINARE ---
@require_POST
@login_required
def delete_printer(request, pk):
    instance = get_object_or_404(Printer, pk=pk)
    if instance.print_files.exists():
        return JsonResponse({'status': 'error', 'message': 'Impossibile eliminare: stampante usata in uno o più file di stampa.'}, status=400)
    if instance.plates.exists():
        return JsonResponse({'status': 'error', 'message': 'Impossibile eliminare: prima elimina i piatti associati.'}, status=400)
    instance.delete()
    return JsonResponse({'status': 'ok'})

@require_POST
@login_required
def delete_plate(request, pk):
    instance = get_object_or_404(Plate, pk=pk)
    if instance.printfile_set.exists():
        return JsonResponse({'status': 'error', 'message': 'Impossibile eliminare: piatto usato in uno o più file di stampa.'}, status=400)
    instance.delete()
    return JsonResponse({'status': 'ok'})

@require_POST
@login_required
def delete_category(request, pk):
    instance = get_object_or_404(Category, pk=pk)
    if instance.project_set.exists():
        return JsonResponse({'status': 'error', 'message': 'Impossibile eliminare: categoria usata in uno o più progetti.'}, status=400)
    instance.delete()
    return JsonResponse({'status': 'ok'})

@require_POST
@login_required
def delete_payment_method(request, pk):
    instance = get_object_or_404(PaymentMethod, pk=pk)
    if instance.expense_set.exists() or instance.stockitem_set.exists():
        return JsonResponse({'status': 'error', 'message': 'Metodo in uso in spese o vendite, impossibile eliminare.'}, status=400)
    instance.delete()
    return JsonResponse({'status': 'ok'})

@require_POST
@login_required
def delete_expense_category(request, pk):
    instance = get_object_or_404(ExpenseCategory, pk=pk)
    if instance.expense_set.exists():
        return JsonResponse({'status': 'error', 'message': 'Categoria in uso in una o più spese, impossibile eliminare.'}, status=400)
    instance.delete()
    return JsonResponse({'status': 'ok'})



@require_POST
@login_required
def add_maintenance_log(request):
    form = MaintenanceLogForm(request.POST)
    if form.is_valid():
        form.save()
    return redirect('settings_dashboard')


@login_required
def api_get_costs(request):
    try:
        cost_obj = GlobalSetting.objects.get(key='electricity_cost_kwh')
        cost_kwh = cost_obj.value
    except GlobalSetting.DoesNotExist:
        cost_kwh = 0.25

    filaments_data = []
    for f in Filament.objects.all():
        total_weight = f.spools.aggregate(total=Sum('initial_weight_g'))['total'] or 0
        total_cost = f.spools.aggregate(total=Sum('cost'))['total'] or 0
        cost_per_gram = (total_cost / total_weight) if total_weight > 0 else 0
        filaments_data.append({
            'id': f.id,
            'name': str(f),
            'cost_per_gram': float(cost_per_gram)
        })

    return JsonResponse({
        'electricity_cost_kwh': float(cost_kwh),
        'filaments': filaments_data
    })

@login_required
def quote_calculator(request):
    saved_quotes = Quote.objects.all()
    for quote in saved_quotes:
        quote.details_json = json.dumps(quote.details)

    context = {
        'page_title': 'Preventivi',
        'saved_quotes': saved_quotes
    }
    return render(request, 'app_3dmage_management/quotes.html', context)

@require_POST
@login_required
def save_quote(request):
    data = json.loads(request.body)
    Quote.objects.create(
        name=data.get('name'),
        total_cost=data.get('total_cost'),
        details=data.get('details')
    )
    return JsonResponse({'status': 'ok'})

@require_POST
@login_required
def delete_quote(request, quote_id):
    quote = get_object_or_404(Quote, id=quote_id)
    quote.delete()
    return JsonResponse({'status': 'ok'})

@login_required
def get_quote_details(request, quote_id):
    quote = get_object_or_404(Quote, id=quote_id)
    return JsonResponse({'details': quote.details})

@login_required
def api_get_notifications(request):
    notifications = Notification.objects.filter(is_read=False)
    data = {
        'count': notifications.count(),
        'notifications': list(notifications.values('id', 'message', 'level', 'related_url'))[:5]
    }
    return JsonResponse(data)

@require_POST
@login_required
def api_mark_notifications_as_read(request):
    Notification.objects.filter(is_read=False).update(is_read=True)
    return JsonResponse({'status': 'ok'})

@require_POST
@login_required
def api_delete_notification(request, notification_id):
    notification = get_object_or_404(Notification, id=notification_id)
    notification.is_read = True
    notification.save()
    return JsonResponse({'status': 'ok'})

@require_POST
@transaction.atomic
@login_required
def set_print_file_status(request, file_id):
    try:
        data = json.loads(request.body)
        new_status = data.get('new_status')

        if new_status not in ['PRINTING', 'TODO']:
            return JsonResponse({'status': 'error', 'message': 'Stato non valido.'}, status=400)

        file_to_update = get_object_or_404(PrintFile, id=file_id)

        if new_status == 'PRINTING':
            if file_to_update.printer:
                PrintFile.objects.filter(
                    printer=file_to_update.printer,
                    status='PRINTING'
                ).exclude(id=file_id).update(status='TODO')

        file_to_update.status = new_status
        file_to_update.save()

        return JsonResponse({'status': 'ok', 'message': 'Stato aggiornato con successo.'})

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
@require_POST
@transaction.atomic
@login_required
def create_project_from_quote(request):
    """
    Crea un nuovo progetto e un file di stampa associato
    partendo dai dati di un preventivo.
    """
    try:
        data = json.loads(request.body)

        if not data.get('name') or not data.get('materials'):
            return JsonResponse({'status': 'error', 'message': 'Nome del progetto e materiali sono obbligatori.'}, status=400)

        total_seconds = (int(data.get('hours', 0)) * 3600) + (int(data.get('minutes', 0)) * 60)
        if total_seconds <= 0:
            return JsonResponse({'status': 'error', 'message': 'Il tempo di stampa deve essere maggiore di zero.'}, status=400)

        new_project = Project.objects.create(
            name=data['name'],
            notes=f"Creato da preventivo in data {timezone.now().strftime('%d/%m/%Y')}",
            status=Project.Status.QUOTE
        )

        print_file = PrintFile.objects.create(
            project=new_project,
            name=f"{data['name']} (file unico)",
            print_time_seconds=total_seconds,
            status=PrintFile.Status.TODO
        )

        for material in data['materials']:
            filament_id = material.get('filament_id')
            grams = material.get('grams')
            if filament_id and grams:
                first_available_spool = Spool.objects.filter(filament_id=filament_id).first()

                if first_available_spool:
                    FilamentUsage.objects.create(
                        print_file=print_file,
                        spool=first_available_spool,
                        grams_used=Decimal(grams)
                    )
                else:
                    filament = get_object_or_404(Filament, id=filament_id)
                    return JsonResponse({
                        'status': 'error',
                        'message': f"Nessuna bobina disponibile per il filamento '{filament}'. Aggiungine una prima di creare il progetto."
                    }, status=400)

        return JsonResponse({
            'status': 'ok',
            'message': 'Progetto creato con successo!',
            'project_url': reverse('project_detail', args=[new_project.id])
        })

    except (json.JSONDecodeError, KeyError, TypeError) as e:
        return JsonResponse({'status': 'error', 'message': f'Dati non validi: {str(e)}'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'Errore del server: {str(e)}'}, status=500)
