from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.http import require_POST
import math
from django.db.models import Prefetch, Sum, Case, When, Value, IntegerField, F, Q, Count, Max, ExpressionWrapper, DecimalField, OuterRef, Subquery
from django.db.models.functions import Coalesce
from django.contrib.auth.decorators import login_required, permission_required
from django.forms.models import model_to_dict
from django.utils import timezone
from django.db import transaction
from decimal import Decimal
import datetime
import json


from .models import (
    Project, Printer, Plate, Filament, PrintFile, Spool, Category,
    StockItem, PaymentMethod, Expense, ExpenseCategory, FilamentUsage, ExpenseCategory, MaintenanceLog, GlobalSetting, Quote, Notification
)

from .forms import (
    ProjectForm, PrintFileForm, StockItemForm, CompleteProjectForm,
    PrintFileEditForm, FilamentForm, SpoolForm, ExpenseForm, TransferForm, CorrectBalanceForm,
    PrinterForm, PlateForm, CategoryForm, PaymentMethodForm, ExpenseCategoryForm, MaintenanceLogForm, ElectricityCostForm, SaleEditForm, ManualStockItemForm
)

def project_dashboard(request):
    # Filtri per Progetti Attivi
    search_query = request.GET.get('q', '')
    status_filter = request.GET.get('status', '')
    category_filter = request.GET.get('category', '')

    # Filtri per Progetti Completati
    completed_search_query = request.GET.get('q_completed', '')
    completed_year_filter = request.GET.get('year_completed', '')

    # Flag per mantenere aperte le sezioni dei filtri
    active_filters_applied = bool(search_query or status_filter or category_filter)
    completed_filters_applied = bool(completed_search_query or completed_year_filter)

    # Anni disponibili per il filtro dei progetti completati
    completed_project_years = Project.objects.filter(
        status='DONE', completed_at__isnull=False
    ).dates('completed_at', 'year', order='DESC')

    all_projects = Project.objects.select_related('category').all()

    # MIGLIORAMENTO PERFORMANCE: Definizione dell'annotazione per il costo del materiale
    # Questo calcolo viene fatto una sola volta a livello di DB invece che per ogni progetto
    cost_annotation = Sum(
        ExpressionWrapper(
            F('print_files__filament_usages__grams_used') *
            F('print_files__filament_usages__spool__cost') /
            # Evita la divisione per zero se il peso iniziale di una bobina è 0
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
        # MIGLIORAMENTO PERFORMANCE: Applica l'annotazione del costo
        annotated_material_cost=Coalesce(cost_annotation, Decimal('0.00'), output_field=DecimalField())
    )

    if search_query:
        q_filter = Q(name__icontains=search_query)
        if search_query.isdigit():
            q_filter |= Q(id=search_query) | Q(custom_id__icontains=search_query)
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
    completed_projects_query = all_projects.filter(status='DONE').annotate(
        total_print_time_seconds=Sum('print_files__print_time_seconds', default=0),
        # MIGLIORAMENTO PERFORMANCE: Applica l'annotazione del costo
        annotated_material_cost=Coalesce(cost_annotation, Decimal('0.00'), output_field=DecimalField())
    )

    if completed_search_query:
        completed_projects_query = completed_projects_query.filter(
            Q(name__icontains=completed_search_query) | Q(custom_id__icontains=completed_search_query)
        )
    if completed_year_filter and completed_year_filter.isdigit():
        completed_projects_query = completed_projects_query.filter(completed_at__year=int(completed_year_filter))

    completed_projects = completed_projects_query.order_by('-completed_at')

    context = {
        'active_projects': active_projects,
        'completed_projects': completed_projects,
        'all_categories': Category.objects.all(),
        'all_statuses': Project.Status.choices,
        'project_form': ProjectForm(),
        'add_print_file_form': PrintFileForm(),
        'edit_print_file_form': PrintFileEditForm(),
        'page_title': 'Progetti',
        'current_view': 'table',
        # Valori e flag per i filtri attivi
        'search_query': search_query,
        'status_filter': status_filter,
        'category_filter': category_filter,
        'active_filters_applied': active_filters_applied,
        'sort_active': sort_active,
        'order_active': order_active,
        # Valori e flag per i filtri completati
        'completed_search_query': completed_search_query,
        'completed_year_filter': completed_year_filter,
        'completed_filters_applied': completed_filters_applied,
        'completed_project_years': [d.year for d in completed_project_years],
    }
    return render(request, 'app_3dmage_management/dashboard.html', context)


def project_kanban_board(request):
    kanban_columns = []
    statuses_to_show = [status for status in Project.Status.choices if status[0] != 'DONE']
    for status_id, status_name in statuses_to_show:
        projects_in_status = Project.objects.filter(status=status_id).prefetch_related('print_files')
        kanban_columns.append({'status_id': status_id, 'status_name': status_name, 'projects': projects_in_status})
    context = {'kanban_columns': kanban_columns, 'project_form': ProjectForm(), 'print_file_form': PrintFileForm(), 'page_title': 'Progetti', 'current_view': 'kanban'}
    return render(request, 'app_3dmage_management/kanban_board.html', context)

def filament_dashboard(request):
    sort_by = request.GET.get('sort', 'material')
    order = request.GET.get('order', 'asc')
    order_prefix = '-' if order == 'desc' else ''

    # Subquery to get the total initial weight of all spools for a given filament.
    total_initial_weight_subquery = Spool.objects.filter(
        filament=OuterRef('pk')
    ).values('filament').annotate(
        s=Sum('initial_weight_g')
    ).values('s')

    # Subquery to get the total used weight from all usages for a given filament.
    total_used_weight_subquery = FilamentUsage.objects.filter(
        spool__filament=OuterRef('pk'),
        print_file__status__in=['DONE', 'FAILED']
    ).values('spool__filament').annotate(
        s=Sum('grams_used')
    ).values('s')

    # Annotate the Filament queryset with the results of the subqueries.
    filaments_query = Filament.objects.annotate(
        annotated_total_initial_weight=Coalesce(Subquery(total_initial_weight_subquery, output_field=IntegerField()), 0),
        annotated_total_used_weight=Coalesce(Subquery(total_used_weight_subquery, output_field=DecimalField()), Decimal('0.00'))
    ).annotate(
        annotated_remaining_weight=ExpressionWrapper(
            F('annotated_total_initial_weight') - F('annotated_total_used_weight'),
            output_field=DecimalField()
        )
    )

    valid_sort_fields = ['material', 'brand', 'color_name']
    if sort_by not in valid_sort_fields:
        sort_by = 'material'

    order_fields = (f'{order_prefix}{sort_by}',)
    filaments = filaments_query.order_by(*order_fields)

    LOW_STOCK_THRESHOLD = 150
    # NOTA: Per le notifiche, usiamo il valore appena annotato per coerenza e performance
    for f in filaments:
        if f.annotated_remaining_weight < LOW_STOCK_THRESHOLD:
            Notification.objects.get_or_create(
                message=f"Scorta quasi esaurita per {f}!",
                level=Notification.NotificationLevel.WARNING,
                is_read=False,
                defaults={'related_url': "/filaments/"}
            )

    context = {
        'filaments': filaments,
        'filament_form': FilamentForm(),
        'spool_form': SpoolForm(),
        'page_title': 'Filamenti',
        'sort_by': sort_by,
        'order': order
    }
    return render(request, 'app_3dmage_management/filaments.html', context)

def inventory_dashboard(request):
    search_query = request.GET.get('q', '')
    status_filter = request.GET.get('status', '')
    sort_by = request.GET.get('sort', 'created_at')
    order = request.GET.get('order', 'desc')

    filters_applied = bool(search_query or status_filter)
    order_prefix = '-' if order == 'desc' else ''

    stock_items_query = StockItem.objects.exclude(status='SOLD').select_related('project').all()

    if search_query:
        stock_items_query = stock_items_query.filter(
            Q(name__icontains=search_query) |
            Q(custom_id__icontains=search_query)
        )
    if status_filter:
        stock_items_query = stock_items_query.filter(status=status_filter)

    valid_sort_fields = ['custom_id', 'quantity', 'name', 'status', 'suggested_price']
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


def get_stock_item_details(request, item_id):
    item = get_object_or_404(StockItem.objects.select_related('project'), id=item_id)
    data = model_to_dict(item)
    data['project_name'] = item.project.name if item.project else None
    data['project_id'] = item.project.custom_id if item.project else None
    return JsonResponse(data)


@require_POST
@transaction.atomic
def update_stock_item(request, item_id):
    item_to_process = get_object_or_404(StockItem, id=item_id)
    original_status = item_to_process.status

    form = StockItemForm(request.POST, instance=item_to_process)

    if not form.is_valid():
        return JsonResponse({'status': 'error', 'message': 'Dati non validi.', 'errors': form.errors.as_json()}, status=400)

    new_status = form.cleaned_data.get('status')

    if new_status != 'SOLD':
        form.save()
        return JsonResponse({'status': 'ok', 'message': 'Oggetto aggiornato con successo!'})

    quantity_to_sell = form.cleaned_data.get('quantity_to_sell')

    if not quantity_to_sell or not (0 < quantity_to_sell <= item_to_process.quantity):
        return JsonResponse({'status': 'error', 'message': 'Quantità da vendere non valida.'}, status=400)

    cost_per_unit = item_to_process.material_cost / item_to_process.quantity if item_to_process.quantity > 0 else Decimal('0')

    if quantity_to_sell == item_to_process.quantity:
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
        newly_sold_item = StockItem.objects.create(
            project=item_to_process.project,
            custom_id=item_to_process.custom_id,
            name=item_to_process.name,
            quantity=quantity_to_sell,
            status='SOLD',
            material_cost=cost_per_unit * quantity_to_sell,
            suggested_price=item_to_process.suggested_price,
            sold_at=form.cleaned_data.get('sold_at') or timezone.now().date(),
            sale_price=form.cleaned_data.get('sale_price'),
            payment_method=form.cleaned_data.get('payment_method'),
            sold_to=form.cleaned_data.get('sold_to'),
            notes=form.cleaned_data.get('notes'),
        )
        item_to_process.quantity -= quantity_to_sell
        item_to_process.material_cost -= (cost_per_unit * quantity_to_sell)
        item_to_process.status = original_status
        item_to_process.save()

        if newly_sold_item.payment_method and newly_sold_item.sale_price:
            total_sale_price = newly_sold_item.sale_price * newly_sold_item.quantity
            newly_sold_item.payment_method.balance += total_sale_price
            newly_sold_item.payment_method.save()

    return JsonResponse({'status': 'ok', 'message': 'Oggetto venduto con successo!'})

@require_POST
def delete_stock_item(request, item_id):
    item = get_object_or_404(StockItem, id=item_id)
    if item.status == 'SOLD':
        return JsonResponse({'status': 'error', 'message': 'Non puoi eliminare un oggetto già venduto da qui.'}, status=400)
    item.delete()
    return JsonResponse({'status': 'ok', 'message': 'Oggetto eliminato con successo.'})

def sales_dashboard(request):
    search_query = request.GET.get('q', '')
    year_filter = request.GET.get('year', '')
    sold_to_filter = request.GET.get('sold_to', '')
    payment_method_filter = request.GET.get('payment_method', '')
    notes_filter = request.GET.get('notes', '')

    sort_by = request.GET.get('sort', 'sold_at')
    order = request.GET.get('order', 'desc')

    filters_applied = bool(search_query or year_filter or sold_to_filter or payment_method_filter or notes_filter)
    order_prefix = '-' if order == 'desc' else ''

    sold_items_query = StockItem.objects.filter(status='SOLD').annotate(
        total_sale_price=F('sale_price') * F('quantity'),
        profit= (F('sale_price') * F('quantity')) - F('material_cost')
    ).select_related('project', 'payment_method')

    filter_summary_parts = []
    if search_query:
        sold_items_query = sold_items_query.filter(name__icontains=search_query)
        filter_summary_parts.append(f'Nome: "{search_query}"')
    if year_filter:
        sold_items_query = sold_items_query.filter(sold_at__year=year_filter)
        filter_summary_parts.append(f'Anno: {year_filter}')
    if sold_to_filter:
        sold_items_query = sold_items_query.filter(sold_to__icontains=sold_to_filter)
        filter_summary_parts.append(f'Venduto a: "{sold_to_filter}"')
    if payment_method_filter:
        sold_items_query = sold_items_query.filter(payment_method_id=payment_method_filter)
        try:
            method_name = PaymentMethod.objects.get(id=payment_method_filter).name
            filter_summary_parts.append(f'Metodo: {method_name}')
        except PaymentMethod.DoesNotExist:
            pass
    if notes_filter:
        sold_items_query = sold_items_query.filter(notes__icontains=notes_filter)
        filter_summary_parts.append(f'Note: "{notes_filter}"')

    filter_summary = ", ".join(filter_summary_parts)

    valid_sort_fields = ['sold_at', 'name', 'total_sale_price', 'material_cost', 'profit', 'sold_to']
    if sort_by not in valid_sort_fields:
        sort_by = 'sold_at'

    sold_items = sold_items_query.order_by(f'{order_prefix}{sort_by}')

    total_sales = sold_items_query.aggregate(total=Coalesce(Sum('total_sale_price'), Decimal('0.00')))['total']
    total_profit = sold_items_query.aggregate(total=Coalesce(Sum('profit'), Decimal('0.00')))['total']

    available_years = StockItem.objects.filter(sold_at__isnull=False).dates('sold_at', 'year', order='DESC')
    all_payment_methods = PaymentMethod.objects.all()

    context = {
        'sold_items': sold_items,
        'page_title': 'Vendite',
        'available_years': [d.year for d in available_years],
        'all_payment_methods': all_payment_methods,
        'search_query': search_query,
        'year_filter': year_filter,
        'sold_to_filter': sold_to_filter,
        'payment_method_filter': payment_method_filter,
        'notes_filter': notes_filter,
        'filters_applied': filters_applied,
        'filter_summary': filter_summary,
        'sale_edit_form': SaleEditForm(),
        'sort_by': sort_by,
        'order': order,
        'total_sales': total_sales,
        'total_profit': total_profit,
    }
    return render(request, 'app_3dmage_management/sales.html', context)

def get_sale_details(request, item_id):
    sale = get_object_or_404(StockItem.objects.select_related('project'), id=item_id, status='SOLD')
    data = {
        'id': sale.id,
        'name': sale.name,
        'project_custom_id': sale.project.custom_id if sale.project else None,
        'sold_at': sale.sold_at.strftime('%Y-%m-%d') if sale.sold_at else '',
        'sale_price': sale.sale_price,
        'payment_method': sale.payment_method.id if sale.payment_method else None,
        'sold_to': sale.sold_to,
        'notes': sale.notes,
    }
    return JsonResponse(data)

@require_POST
@transaction.atomic
def edit_sale(request, item_id):
    sale = get_object_or_404(StockItem, id=item_id, status='SOLD')
    old_price = sale.sale_price or Decimal('0.00')
    old_payment_method = sale.payment_method

    form = SaleEditForm(request.POST, instance=sale)
    if form.is_valid():
        if old_payment_method:
            old_payment_method.balance -= old_price
            old_payment_method.save()

        updated_sale = form.save()

        new_payment_method = updated_sale.payment_method
        new_price = updated_sale.sale_price or Decimal('0.00')
        if new_payment_method:
            new_payment_method.balance += new_price
            new_payment_method.save()

        return JsonResponse({'status': 'ok'})
    return JsonResponse({'status': 'error', 'errors': form.errors.as_json()}, status=400)


@require_POST
@transaction.atomic
def reverse_sale(request, stock_item_id):
    sale_to_reverse = get_object_or_404(StockItem, id=stock_item_id, status='SOLD')

    if sale_to_reverse.payment_method and sale_to_reverse.sale_price:
        sale_to_reverse.payment_method.balance -= sale_to_reverse.sale_price
        sale_to_reverse.payment_method.save()

    existing_stock = StockItem.objects.filter(
        project=sale_to_reverse.project,
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
        sale_to_reverse.save()

    return JsonResponse({'status': 'ok'})

def print_queue_board(request):
    # Query di base per ottenere i file attivi, pre-caricando i dati necessari in modo efficiente
    active_print_files_qs = PrintFile.objects.filter(
        status__in=['TODO', 'PRINTING']
    ).select_related(
        'project', 'printer', 'plate'
    ).prefetch_related(
        'filament_usages__spool__filament'
    ).order_by('queue_position')

    # Annotiamo il tempo totale direttamente sulla query delle stampanti
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
        # Separiamo il file in stampa da quelli in coda
        printing_file = next((f for f in printer.queued_files if f.status == 'PRINTING'), None)
        todo_files = [f for f in printer.queued_files if f.status == 'TODO']

        # Formattiamo il tempo totale
        total_seconds = printer.total_queued_seconds or 0
        printer.total_queued_time_formatted = str(datetime.timedelta(seconds=total_seconds))

        # Aggiungiamo attributi personalizzati all'oggetto printer prima di passarlo al template
        printer.printing_file = printing_file
        printer.todo_files = todo_files
        printers_list.append(printer)

    context = {
        'printers': printers_list,
        'page_title': 'Coda di Stampa'
    }
    return render(request, 'app_3dmage_management/print_queue.html', context)

# --- Vista Dettaglio Progetto ---
def project_detail(request, project_id):
    # Query ottimizzata per pre-caricare tutto il necessario
    queryset = Project.objects.prefetch_related(
        Prefetch('print_files', queryset=PrintFile.objects.select_related('printer', 'plate')
                 .prefetch_related('filament_usages__spool__filament').order_by('created_at'))
    )
    project = get_object_or_404(queryset, id=project_id)

    referer = request.GET.get('from', 'kanban')

    # Gestione del form per aggiungere un nuovo file di stampa
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

    # Prepara tutti gli altri form necessari per il contesto
    context = {
        'project': project,
        'completion_form': CompleteProjectForm(initial={'stock_item_name': project.name, 'stock_item_quantity': project.quantity}),
        'edit_project_form': ProjectForm(instance=project),
        'add_print_file_form': print_file_form,
        'edit_print_file_form': PrintFileEditForm(),
        'can_be_completed': not project.print_files.filter(status__in=['TODO', 'PRINTING']).exists() and project.print_files.exists(),
        'page_title': 'Progetti',
        'referer': referer
    }
    return render(request, 'app_3dmage_management/project_detail.html', context)

# --- Viste di Azione e AJAX ---
@require_POST
def add_project(request):
    form = ProjectForm(request.POST)
    if form.is_valid():
        form.save()
    return redirect(request.META.get('HTTP_REFERER', 'project_dashboard'))

@require_POST
def edit_project(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    form = ProjectForm(request.POST, instance=project)
    if form.is_valid():
        form.save()
        return JsonResponse({'status': 'ok'})
    return JsonResponse({'status': 'error', 'errors': form.errors.as_json()}, status=400)

@require_POST
@transaction.atomic
def complete_project(request, project_id):
    project = get_object_or_404(Project.objects.prefetch_related('print_files__filament_usages__spool'), id=project_id)
    form = CompleteProjectForm(request.POST)

    if form.is_valid():
        # --- LOGICA DI GENERAZIONE ID ---
        current_year = timezone.now().year
        last_item_id = Project.objects.filter(
            completed_at__year=current_year,
            custom_id__isnull=False
        ).aggregate(max_id=Max('custom_id'))['max_id']

        if last_item_id:
            last_sequential = int(last_item_id[2:])
            new_sequential = last_sequential + 1
        else:
            new_sequential = 1

        new_custom_id = f"{current_year % 100:02d}{new_sequential:03d}"
        # --------------------------------

        project.status = Project.Status.DONE
        project.completed_at = timezone.now()
        project.custom_id = new_custom_id
        project.save()

        # Cerca se esiste già uno StockItem per questo progetto (caso raro, ma sicuro)
        stock_item, created = StockItem.objects.get_or_create(
            project=project,
            defaults={
                'custom_id': new_custom_id,
                'name': form.cleaned_data['stock_item_name'],
                'quantity': form.cleaned_data['stock_item_quantity'],
                'material_cost': project.total_material_cost
            }
        )
        # Se non è stato creato, significa che esisteva già, quindi lo aggiorniamo
        if not created:
            stock_item.custom_id = new_custom_id
            stock_item.name = form.cleaned_data['stock_item_name']
            stock_item.quantity = form.cleaned_data['stock_item_quantity']
            stock_item.material_cost = project.total_material_cost
            stock_item.save()

        return redirect('inventory_dashboard')

    return redirect('project_detail', project_id=project.id)

@require_POST
def delete_project(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    project.delete()
    return redirect('project_dashboard')

@require_POST
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
                filament_data_json=request.POST.get('filament_data', '[]'),
                print_file=print_file
            )

            # Logica per l'automatismo
            project = print_file.project
            produced_per_print = print_file.produced_quantity

            # Calcola gli oggetti totali già prodotti *prima* di questo file
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
def clone_print_file(request):
    try:
        data = json.loads(request.body)
        original_file_id = data.get('file_id')
        count = int(data.get('count', 0))

        if not original_file_id or count <= 0:
            return JsonResponse({'status': 'error', 'message': 'Dati per la clonazione non validi.'}, status=400)

        original_file = PrintFile.objects.select_related('project').prefetch_related('filament_usages__spool').get(id=original_file_id)

        for i in range(count):
            new_file = PrintFile.objects.create(
                project=original_file.project,
                name=f"{original_file.name.replace(' (Copia)', '')} (Copia {i+1})",
                printer=original_file.printer,
                plate=original_file.plate,
                print_time_seconds=original_file.print_time_seconds,
                status=PrintFile.Status.TODO,
                produced_quantity=original_file.produced_quantity,
                actual_quantity=0,
                queue_position=0
            )
            # Copia anche gli utilizzi di filamento
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
                filament_data_json=request.POST.get('filament_data', '[]'),
                print_file=print_file,
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
def requeue_print_file(request, file_id):
    try:
        original_file = get_object_or_404(PrintFile, id=file_id)

        # NUOVA FUNZIONALITA: Leggi i dati dal corpo della richiesta JSON
        data = json.loads(request.body)
        planned_filaments = data.get('filaments', [])

        # Crea una copia del file con stato 'Da Stampare'
        new_file = PrintFile.objects.create(
            project=original_file.project,
            name=f"{original_file.name.replace(' (Da ristampare)', '')} (Da ristampare)",
            printer=original_file.printer,
            plate=original_file.plate,
            print_time_seconds=original_file.print_time_seconds,
            status=PrintFile.Status.TODO,
            queue_position=0
        )

        # Se il frontend ha inviato i dati del filamento, usali.
        if planned_filaments:
            for usage_data in planned_filaments:
                spool_id = usage_data.get('spool_id')
                grams = usage_data.get('grams')
                if spool_id and grams:
                    spool = get_object_or_404(Spool, id=spool_id)
                    FilamentUsage.objects.create(
                        print_file=new_file,
                        spool=spool,
                        grams_used=grams # Usa il valore originale completo
                    )
        # Altrimenti, come fallback, usa la vecchia logica (meno precisa)
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

def get_print_file_details(request, file_id):
    print_file = get_object_or_404(PrintFile, id=file_id)
    # MODIFICA: Aggiunti i campi per la quantità per popolare correttamente il modale di modifica
    data = model_to_dict(print_file, fields=['name', 'printer', 'plate', 'status', 'produced_quantity', 'actual_quantity'])
    # Restituisci direttamente i secondi totali
    data['print_time_seconds'] = print_file.print_time_seconds
    data['filaments_used'] = list(print_file.filament_usages.select_related('spool__filament').values('spool__filament_id', 'spool_id', 'grams_used'))
    return JsonResponse(data)

def api_get_all_projects(request):
    projects = Project.objects.filter(status__in=['QUOTE', 'TODO', 'POST']).order_by('name')
    data = [{'id': p.id, 'name': p.name} for p in projects]
    return JsonResponse(data, safe=False)


@require_POST
def delete_print_file(request, file_id):
    try:
        print_file = get_object_or_404(PrintFile, id=file_id)
        print_file.delete()
        return JsonResponse({'status': 'ok', 'message': 'File eliminato con successo.'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@require_POST
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

def load_plates(request):
    printer_id = request.GET.get('printer_id')
    try:
        plates = Plate.objects.filter(printer_id=printer_id).values('id', 'name')
        return JsonResponse(list(plates), safe=False)
    except (ValueError, TypeError):
        return JsonResponse([], safe=False)

@require_POST
def reprint_project(request, project_id):
    original_project = get_object_or_404(Project.objects.prefetch_related('print_files__filament_usages__spool'), id=project_id)

    # Crea il nuovo progetto
    new_project = Project.objects.create(
        name=f"{original_project.name} (Ristampa)",
        category=original_project.category,
        priority=original_project.priority,
        quantity=original_project.quantity,
        notes=original_project.notes,
        status=Project.Status.TODO # Imposta lo stato a "Da Stampare"
    )

    # Copia tutti i file di stampa e i loro usi di filamento
    for old_file in original_project.print_files.exclude(status='FAILED'):
        new_file = PrintFile.objects.create(
            project=new_project,
            name=old_file.name,
            printer=old_file.printer,
            plate=old_file.plate,
            print_time_seconds=old_file.print_time_seconds,
            status=PrintFile.Status.TODO
        )
        # Copia ogni record di utilizzo del filamento
        for usage in old_file.filament_usages.all():
            FilamentUsage.objects.create(
                print_file=new_file,
                spool=usage.spool,
                grams_used=usage.grams_used
            )

    return redirect('project_dashboard')

@require_POST
def update_project_inline(request, project_id):
    try:
        data = json.loads(request.body)
        field = data.get('field')
        value = data.get('value')

        project = get_object_or_404(Project, id=project_id)

        # Convalida il campo per sicurezza (rimosso 'notes')
        if field not in ['status', 'priority']:
            return JsonResponse({'status': 'error', 'message': 'Campo non valido.'}, status=400)

        setattr(project, field, value)
        project.save()

        # Risposta di successo generica
        return JsonResponse({'status': 'ok', 'message': f'Campo {field} aggiornato.'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@require_POST
@transaction.atomic
def add_spool(request):
    form = SpoolForm(request.POST)
    if form.is_valid():
        filament = form.cleaned_data['filament']
        purchase_date = form.cleaned_data['purchase_date']

        existing_spools = Spool.objects.filter(filament=filament, purchase_date=purchase_date).count()
        new_identifier = chr(ord('A') + existing_spools)

        spool = form.save(commit=False)
        spool.identifier = new_identifier
        spool.save()

        payment_method = form.cleaned_data['payment_method']
        cost = form.cleaned_data['cost']
        material_category, created = ExpenseCategory.objects.get_or_create(name='Bobine')

        Expense.objects.create(
            description=f"Acquisto bobina: {spool.filament} ({spool})",
            amount=cost, category=material_category,
            expense_date=spool.purchase_date, payment_method=payment_method
        )

        payment_method.balance -= cost
        payment_method.save()

    return redirect('filament_dashboard')

@require_POST
def delete_spool(request, spool_id):
    spool = get_object_or_404(Spool, id=spool_id)
    if spool.usages.exists():
        return JsonResponse({
            'status': 'error',
            'message': 'Impossibile eliminare: questa bobina è stata usata in una o più stampe.'
        }, status=400)

    # Storna il costo della bobina dal metodo di pagamento prima di eliminarla
    # Cerca la spesa associata all'acquisto di questa bobina
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

def get_filament_details(request, filament_id):
    filament = get_object_or_404(Filament, id=filament_id)
    return JsonResponse(model_to_dict(filament))

@require_POST
def add_filament(request):
    form = FilamentForm(request.POST)
    if form.is_valid():
        form.save()
    return redirect('filament_dashboard')

@require_POST
def edit_filament(request, filament_id):
    instance = get_object_or_404(Filament, id=filament_id)
    form = FilamentForm(request.POST, instance=instance)
    if form.is_valid():
        form.save()
        return JsonResponse({'status': 'ok'})
    return JsonResponse({'status': 'error', 'errors': form.errors.as_json()}, status=400)

@require_POST
def delete_filament(request, filament_id):
    filament = get_object_or_404(Filament, id=filament_id)
    # Controlla se ci sono bobine associate
    if filament.spools.exists():
        return JsonResponse({'status': 'error', 'message': 'Non puoi eliminare un filamento con bobine associate.'}, status=400)
    filament.delete()
    return JsonResponse({'status': 'ok'})

# Nuova vista AJAX per recuperare le bobine di un filamento
def get_spools_for_filament(request):
    filament_id = request.GET.get('filament_id')
    spools = Spool.objects.filter(filament_id=filament_id)

    # Calcoliamo il peso rimanente per ogni bobina
    spools_data = []
    for spool in spools:
        # Questa è una logica semplificata. Per performance ottimali
        # su grandi dataset, questo calcolo andrebbe ottimizzato.
        used_on_spool = spool.usages.filter(print_file__status__in=['DONE', 'FAILED']).aggregate(total=Sum('grams_used'))['total'] or 0
        remaining = spool.initial_weight_g - used_on_spool
        if remaining > 0: # Mostra solo le bobine con filamento rimanente
            spools_data.append({
                'id': spool.id,
                'purchase_date': spool.purchase_date.strftime('%d/%m/%Y'),
                'remaining': remaining
            })
    return JsonResponse(spools_data, safe=False)

def _handle_filament_data(print_file, filament_data_json, wasted_grams_str=None):
    """Funzione helper per gestire i dati dei filamenti."""
    print_file.filament_usages.all().delete()
    filament_data = json.loads(filament_data_json)

    wasted_grams = None
    if wasted_grams_str:
        try:
            # Assicura che il valore sia un numero valido e non negativo
            val = Decimal(wasted_grams_str)
            wasted_grams = val if val >= 0 else None
        except:
            wasted_grams = None

    if wasted_grams is not None and filament_data:
        total_planned_grams = sum(Decimal(usage.get('grams', 0)) for usage in filament_data if usage.get('grams'))

        if total_planned_grams > 0:
            # Limita i grammi sprecati a non superare quelli pianificati
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

def api_get_all_filaments(request):
    filaments = Filament.objects.all().order_by('material', 'brand', 'color_name')
    # MODIFICA: Aggiungiamo 'color_hex' ai dati restituiti dalla API
    data = [{'id': f.id, 'name': str(f), 'color_hex': f.color_hex} for f in filaments]
    return JsonResponse(data, safe=False)

def api_get_filament_spools(request, filament_id):
    spools = Spool.objects.filter(filament_id=filament_id).order_by('identifier')
    spools_data = []

    for spool in spools:
        # Assicura che il valore di fallback sia un Decimale
        used_on_spool = spool.usages.filter(
            print_file__status__in=['DONE', 'FAILED']
        ).aggregate(total=Sum('grams_used'))['total'] or Decimal('0')

        # --- MODIFICA CRUCIALE ---
        # Convertiamo il peso iniziale (intero) in Decimale prima della sottrazione
        # per evitare un TypeError che blocca l'intera richiesta.
        remaining = Decimal(spool.initial_weight_g) - used_on_spool

        # Mostra solo bobine con ancora filamento
        if remaining > Decimal('0.01'):
            spools_data.append({
                'id': spool.id,
                'text': str(spool),
                'remaining': remaining,
                'cost': f"{spool.cost}€",
                'purchase_link': spool.purchase_link
            })

    return JsonResponse(spools_data, safe=False)

@login_required
@permission_required('app_3dmage_management.view_expense', raise_exception=True)
def accounting_dashboard(request):
    selected_year = request.GET.get('year', 'all')

    income_years = StockItem.objects.filter(sold_at__isnull=False).dates('sold_at', 'year', order='DESC')
    expense_years = Expense.objects.dates('expense_date', 'year', order='DESC')
    available_years = sorted(list(set([d.year for d in income_years] + [d.year for d in expense_years])), reverse=True)

    income_items = StockItem.objects.filter(status='SOLD').order_by('-sold_at')
    expenses = Expense.objects.all().order_by('-expense_date')

    if selected_year and selected_year != 'all':
        selected_year_int = int(selected_year)
        income_items = income_items.filter(sold_at__year=selected_year_int)
        expenses = expenses.filter(expense_date__year=selected_year_int)

    # Conversione sicura a Decimal
    def safe_decimal(value):
        return value if isinstance(value, Decimal) else Decimal(value or 0)

    total_income = safe_decimal(income_items.aggregate(total=Sum('sale_price'))['total'])
    total_expenses = safe_decimal(expenses.aggregate(total=Sum('amount'))['total'])
    total_cash = safe_decimal(PaymentMethod.objects.aggregate(total=Sum('balance'))['total'])

    profit = total_income - total_expenses

    context = {
        'income_items': income_items,
        'total_income': total_income,
        'expenses': expenses,
        'total_expenses': total_expenses,
        'payment_methods': PaymentMethod.objects.all(),
        'profit': profit,
        'total_cash': total_cash,
        'expense_form': ExpenseForm(),
        'transfer_form': TransferForm(),
        'correct_balance_form': CorrectBalanceForm(),
        'available_years': available_years,
        'selected_year': selected_year,
        'page_title': 'Contabilità'
    }

    return render(request, 'app_3dmage_management/accounting.html', context)

@require_POST
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
def correct_balance(request, method_id):
    payment_method = get_object_or_404(PaymentMethod, id=method_id)
    form = CorrectBalanceForm(request.POST)
    if form.is_valid():
        payment_method.balance = form.cleaned_data['new_balance']
        payment_method.save()
    return redirect('accounting_dashboard')

def get_expense_details(request, expense_id):
    expense = get_object_or_404(Expense, id=expense_id)
    data = model_to_dict(expense)
    # Formatta la data per il campo input[type=date]
    if data.get('expense_date'):
        data['expense_date'] = data['expense_date'].strftime('%Y-%m-%d')
    return JsonResponse(data)

@require_POST
def edit_expense(request, expense_id):
    expense = get_object_or_404(Expense, id=expense_id)
    old_amount = expense.amount
    old_payment_method = expense.payment_method

    form = ExpenseForm(request.POST, instance=expense)
    if form.is_valid():
        # Storna la vecchia transazione se il metodo di pagamento esisteva
        if old_payment_method and old_amount:
            old_payment_method.balance += old_amount
            old_payment_method.save()

        updated_expense = form.save()

        # Applica la nuova transazione
        if updated_expense.payment_method and updated_expense.amount:
            updated_expense.payment_method.balance -= updated_expense.amount
            updated_expense.payment_method.save()

        return JsonResponse({'status': 'ok'})
    return JsonResponse({'status': 'error', 'errors': form.errors.as_json()}, status=400)

@require_POST
def delete_expense(request, expense_id):
    expense = get_object_or_404(Expense, id=expense_id)
    # Rimborsa il metodo di pagamento prima di eliminare
    if expense.payment_method and expense.amount:
        expense.payment_method.balance += expense.amount
        expense.payment_method.save()
    expense.delete()
    return JsonResponse({'status': 'ok'})

@require_POST
def reverse_sale(request, stock_item_id):
    sale_to_reverse = get_object_or_404(StockItem, id=stock_item_id, status='SOLD')

    # Rimborsa il metodo di pagamento
    if sale_to_reverse.payment_method and sale_to_reverse.sale_price:
        sale_to_reverse.payment_method.balance -= sale_to_reverse.sale_price
        sale_to_reverse.payment_method.save()

    # Cerca un oggetto identico già in magazzino per accorparlo
    existing_stock = StockItem.objects.filter(
        project=sale_to_reverse.project,
        status='IN_STOCK'
    ).first()

    if existing_stock:
        existing_stock.quantity += sale_to_reverse.quantity
        existing_stock.material_cost += sale_to_reverse.material_cost
        existing_stock.save()
        sale_to_reverse.delete()
    else:
        # Altrimenti, trasforma l'oggetto venduto in un oggetto in magazzino
        sale_to_reverse.status = 'IN_STOCK'
        sale_to_reverse.sale_price = None
        sale_to_reverse.sold_at = None
        sale_to_reverse.payment_method = None
        sale_to_reverse.sold_to = ''
        sale_to_reverse.save()

    return JsonResponse({'status': 'ok'})

def settings_dashboard(request):
    # Carica i dati delle stampanti con i relativi log
    printers = Printer.objects.prefetch_related('plates', 'maintenance_logs').annotate(
        plate_count=Count('plates'),
        maintenance_count=Count('maintenance_logs')
    ).order_by('name')
    categories = Category.objects.annotate(project_count=Count('project')).order_by('name')
    payment_methods = PaymentMethod.objects.annotate(expense_count=Count('expense'), sale_count=Count('stockitem')).order_by('name')
    expense_categories = ExpenseCategory.objects.annotate(expense_count=Count('expense')).order_by('name')

    try:
        electricity_cost_obj = GlobalSetting.objects.get(key='electricity_cost_kwh')
        initial_cost = electricity_cost_obj.value
    except GlobalSetting.DoesNotExist:
        initial_cost = 0.25 # Valore di fallback

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
        'electricity_form': ElectricityCostForm(initial={'cost': initial_cost}),
        'page_title': 'Impostazioni'
    }
    return render(request, 'app_3dmage_management/settings.html', context)

@require_POST
def update_electricity_cost(request):
    form = ElectricityCostForm(request.POST)
    if form.is_valid():
        cost = form.cleaned_data['cost']
        setting, created = GlobalSetting.objects.update_or_create(
            key='electricity_cost_kwh',
            defaults={'value': cost}
        )
    return redirect('settings_dashboard')


# --- Viste per AGGIUNGERE ---
@require_POST
def add_printer(request):
    form = PrinterForm(request.POST)
    if form.is_valid(): form.save()
    return redirect('settings_dashboard')

@require_POST
def add_plate(request):
    form = PlateForm(request.POST)
    if form.is_valid(): form.save()
    return redirect('settings_dashboard')

@require_POST
def add_category(request):
    form = CategoryForm(request.POST)
    if form.is_valid(): form.save()
    return redirect('settings_dashboard')

@require_POST
def add_payment_method(request):
    form = PaymentMethodForm(request.POST)
    if form.is_valid(): form.save()
    return redirect('settings_dashboard')

@require_POST
def add_expense_category(request):
    form = ExpenseCategoryForm(request.POST)
    if form.is_valid(): form.save()
    return redirect('settings_dashboard')

# --- Viste per PRENDERE DETTAGLI (AJAX) ---
def get_printer_details(request, pk):
    return JsonResponse(model_to_dict(get_object_or_404(Printer, pk=pk)))

def get_plate_details(request, pk):
    return JsonResponse(model_to_dict(get_object_or_404(Plate, pk=pk)))

def get_category_details(request, pk):
    return JsonResponse(model_to_dict(get_object_or_404(Category, pk=pk)))

def get_payment_method_details(request, pk):
    return JsonResponse(model_to_dict(get_object_or_404(PaymentMethod, pk=pk)))

def get_expense_category_details(request, pk):
    return JsonResponse(model_to_dict(get_object_or_404(ExpenseCategory, pk=pk)))

# --- Viste per MODIFICARE ---
@require_POST
def edit_printer(request, pk):
    instance = get_object_or_404(Printer, pk=pk)
    form = PrinterForm(request.POST, instance=instance)
    if form.is_valid():
        form.save()
        return JsonResponse({'status': 'ok'})
    return JsonResponse({'status': 'error', 'errors': form.errors.as_json()}, status=400)

@require_POST
def edit_plate(request, pk):
    instance = get_object_or_404(Plate, pk=pk)
    form = PlateForm(request.POST, instance=instance)
    if form.is_valid():
        form.save()
        return JsonResponse({'status': 'ok'})
    return JsonResponse({'status': 'error', 'errors': form.errors.as_json()}, status=400)

@require_POST
def edit_category(request, pk):
    instance = get_object_or_404(Category, pk=pk)
    form = CategoryForm(request.POST, instance=instance)
    if form.is_valid():
        form.save()
        return JsonResponse({'status': 'ok'})
    return JsonResponse({'status': 'error', 'errors': form.errors.as_json()}, status=400)

@require_POST
def edit_payment_method(request, pk):
    instance = get_object_or_404(PaymentMethod, pk=pk)
    form = PaymentMethodForm(request.POST, instance=instance)
    if form.is_valid():
        form.save()
        return JsonResponse({'status': 'ok'})
    return JsonResponse({'status': 'error', 'errors': form.errors.as_json()}, status=400)

@require_POST
def edit_expense_category(request, pk):
    instance = get_object_or_404(ExpenseCategory, pk=pk)
    form = ExpenseCategoryForm(request.POST, instance=instance)
    if form.is_valid():
        form.save()
        return JsonResponse({'status': 'ok'})
    return JsonResponse({'status': 'error', 'errors': form.errors.as_json()}, status=400)

# --- Viste per ELIMINARE ---
@require_POST
def delete_printer(request, pk):
    instance = get_object_or_404(Printer, pk=pk)
    if instance.print_files.exists():
        return JsonResponse({'status': 'error', 'message': 'Impossibile eliminare: stampante usata in uno o più file di stampa.'}, status=400)
    if instance.plates.exists():
        return JsonResponse({'status': 'error', 'message': 'Impossibile eliminare: prima elimina i piatti associati.'}, status=400)
    instance.delete()
    return JsonResponse({'status': 'ok'})

@require_POST
def delete_plate(request, pk):
    instance = get_object_or_404(Plate, pk=pk)
    if instance.printfile_set.exists():
        return JsonResponse({'status': 'error', 'message': 'Impossibile eliminare: piatto usato in uno o più file di stampa.'}, status=400)
    instance.delete()
    return JsonResponse({'status': 'ok'})

@require_POST
def delete_category(request, pk):
    instance = get_object_or_404(Category, pk=pk)
    if instance.project_set.exists():
        return JsonResponse({'status': 'error', 'message': 'Impossibile eliminare: categoria usata in uno o più progetti.'}, status=400)
    instance.delete()
    return JsonResponse({'status': 'ok'})

@require_POST
def delete_payment_method(request, pk):
    instance = get_object_or_404(PaymentMethod, pk=pk)
    if instance.expense_set.exists() or instance.stockitem_set.exists():
        return JsonResponse({'status': 'error', 'message': 'Metodo in uso in spese o vendite, impossibile eliminare.'}, status=400)
    instance.delete()
    return JsonResponse({'status': 'ok'})

@require_POST
def delete_expense_category(request, pk):
    instance = get_object_or_404(ExpenseCategory, pk=pk)
    if instance.expense_set.exists():
        return JsonResponse({'status': 'error', 'message': 'Categoria in uso in una o più spese, impossibile eliminare.'}, status=400)
    instance.delete()
    return JsonResponse({'status': 'ok'})

@require_POST
def add_maintenance_log(request):
    form = MaintenanceLogForm(request.POST)
    if form.is_valid():
        form.save()

def api_get_costs(request):
    """Fornisce i costi base per il calcolatore."""
    try:
        cost_obj = GlobalSetting.objects.get(key='electricity_cost_kwh')
        cost_kwh = cost_obj.value
    except GlobalSetting.DoesNotExist:
        cost_kwh = 0.25

    filaments_data = []
    for f in Filament.objects.all():
        # Calcolo del costo medio per grammo
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

def quote_calculator(request):
    saved_quotes = Quote.objects.all()
    # Aggiungiamo una versione JSON-string dei dettagli per ogni preventivo
    for quote in saved_quotes:
        quote.details_json = json.dumps(quote.details)

    context = {
        'page_title': 'Preventivi',
        'saved_quotes': saved_quotes
    }
    return render(request, 'app_3dmage_management/quotes.html', context)

@require_POST
def save_quote(request):
    data = json.loads(request.body)
    Quote.objects.create(
        name=data.get('name'),
        total_cost=data.get('total_cost'),
        details=data.get('details')
    )
    return JsonResponse({'status': 'ok'})

@require_POST
def delete_quote(request, quote_id):
    quote = get_object_or_404(Quote, id=quote_id)
    quote.delete()
    return JsonResponse({'status': 'ok'})

def get_quote_details(request, quote_id):
    quote = get_object_or_404(Quote, id=quote_id)
    return JsonResponse({'details': quote.details})

def api_get_notifications(request):
    notifications = Notification.objects.filter(is_read=False)
    data = {
        'count': notifications.count(),
        'notifications': list(notifications.values('id', 'message', 'level', 'related_url'))[:5] # Mostra solo le 5 più recenti
    }
    return JsonResponse(data)

@require_POST
def api_mark_notifications_as_read(request):
    Notification.objects.filter(is_read=False).update(is_read=True)
    return JsonResponse({'status': 'ok'})

@require_POST
def api_delete_notification(request, notification_id):
    notification = get_object_or_404(Notification, id=notification_id)
    # Per ora, contrassegniamo come letta invece di eliminarla, per mantenere lo storico
    notification.is_read = True
    notification.save()
    return JsonResponse({'status': 'ok'})

@require_POST
@transaction.atomic
def set_print_file_status(request, file_id):
    """
    Imposta lo stato di un file di stampa. Usato per il drag-and-drop
    nella Coda di Stampa per avviare o fermare una stampa.
    """
    try:
        data = json.loads(request.body)
        new_status = data.get('new_status')

        if new_status not in ['PRINTING', 'TODO']:
            return JsonResponse({'status': 'error', 'message': 'Stato non valido.'}, status=400)

        file_to_update = get_object_or_404(PrintFile, id=file_id)

        # Se si sta impostando un file come 'IN STAMPA'
        if new_status == 'PRINTING':
            # Trova qualsiasi altro file che è già in stampa sulla stessa stampante
            # e rimettilo in coda.
            if file_to_update.printer:
                PrintFile.objects.filter(
                    printer=file_to_update.printer,
                    status='PRINTING'
                ).exclude(id=file_id).update(status='TODO')

        # Aggiorna lo stato del file spostato
        file_to_update.status = new_status
        file_to_update.save()

        return JsonResponse({'status': 'ok', 'message': 'Stato aggiornato con successo.'})

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
