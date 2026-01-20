from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.forms.models import model_to_dict
from django.db.models import Sum, Count, Subquery, OuterRef, IntegerField, DecimalField, ExpressionWrapper, F, Value
from django.db.models.functions import Coalesce

from ..models import (
    Printer, Plate, Category, PaymentMethod, ExpenseCategory,
    MaintenanceLog, GlobalSetting, PrintFile, Filament, WorkOrder
)
from ..forms import (
    PrinterForm, PlateForm, CategoryForm, PaymentMethodForm,
    ExpenseCategoryForm, MaintenanceLogForm, GeneralSettingsForm
)

@login_required
def settings_dashboard(request):
    # Get the year from the request, default to empty string if not present
    year_filter = request.GET.get('year', '')

    # Retrieve global setting for electricity cost, with a default value
    electricity_cost_obj, _ = GlobalSetting.objects.get_or_create(
        key='electricity_cost_kwh',
        defaults={'value': Decimal('0.25')}
    )
    electricity_cost_kwh = electricity_cost_obj.value

    # Get available years for the filter dropdown from completed orders
    available_years_dates = WorkOrder.objects.filter(
        status='DONE',
        completed_at__isnull=False
    ).dates('completed_at', 'year', order='DESC')
    available_years = [d.year for d in available_years_dates]

    # --- BUG FIX: Use Subqueries for accurate aggregation ---

    # Subquery for calculating total print seconds, filtered by year if provided.
    relevant_seconds_subquery = PrintFile.objects.filter(
        printer=OuterRef('pk'),
        status='DONE'
    )
    if year_filter and year_filter.isdigit():
        relevant_seconds_subquery = relevant_seconds_subquery.filter(
            work_order__completed_at__year=int(year_filter)
        )
    # Define the annotation within the subquery
    relevant_seconds_subquery = relevant_seconds_subquery.values('printer').annotate(
        total=Sum('print_time_seconds')
    ).values('total')



    # Main query for printers, now using the robust subqueries for aggregations
    printers_query = Printer.objects.prefetch_related(
        'plates', 'maintenance_logs'
    ).annotate(
        # Standard counts
        plate_count=Count('plates', distinct=True),
        maintenance_count=Count('maintenance_logs', distinct=True),

        relevant_print_seconds=Coalesce(
            Subquery(relevant_seconds_subquery, output_field=IntegerField()), 0
        )
    ).order_by('name')

    # Process printers to format the time values for display
    printers = []
    for printer in printers_query:
        # Format the total/filtered print time
        relevant_seconds = printer.relevant_print_seconds
        h_relevant = relevant_seconds // 3600
        m_relevant = (relevant_seconds % 3600) // 60
        printer.relevant_print_time_formatted = f"{h_relevant} ore {m_relevant} min"

        # Calculate electricity cost in Python for precision
        relevant_hours = Decimal(relevant_seconds) / Decimal('3600.0')
        printer_kw = Decimal(printer.power_consumption) / Decimal('1000.0')
        printer.annotated_electricity_cost = relevant_hours * printer_kw * electricity_cost_kwh
        printers.append(printer)


    categories = Category.objects.annotate(project_count=Count('workorder')).order_by('name')
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
@login_required
def get_printer_details(request, pk):
    return JsonResponse(model_to_dict(get_object_or_404(Printer, pk=pk)))

@login_required
def get_plate_details(request, pk):
    return JsonResponse(model_to_dict(get_object_or_404(Plate, pk=pk)))

@login_required
def get_category_details(request, pk):
    return JsonResponse(model_to_dict(get_object_or_404(Category, pk=pk)))

@login_required
def get_payment_method_details(request, pk):
    return JsonResponse(model_to_dict(get_object_or_404(PaymentMethod, pk=pk)))

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
    # Filtra solo i filamenti con bobbine attive e ordina per materiale e codice colore
    filaments = Filament.objects.filter(spools__is_active=True).distinct().order_by('material', 'color_code')
    for f in filaments:
        total_weight = f.spools.aggregate(total=Sum('initial_weight_g'))['total'] or 0
        total_cost = f.spools.aggregate(total=Sum('cost'))['total'] or 0
        cost_per_gram = (total_cost / total_weight) if total_weight > 0 else 0
        filaments_data.append({
            'id': f.id,
            'name': str(f),
            'cost_per_gram': float(cost_per_gram),
            'color_hex': f.color_hex
        })

    return JsonResponse({
        'electricity_cost_kwh': float(cost_kwh),
        'filaments': filaments_data
    })
