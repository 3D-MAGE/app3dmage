from decimal import Decimal
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count
from django.utils import timezone
from collections import defaultdict

from ..models import Printer, PrintFile, FilamentUsage, GlobalSetting, Filament

@login_required
def statistics_dashboard(request):
    # Retrieve filters
    year_filter = request.GET.get('year', '')
    printer_filter = request.GET.get('printer', '')

    # Fetch available years from PrintFile creation dates
    available_years_dates = PrintFile.objects.dates('created_at', 'year', order='DESC')
    available_years = [d.year for d in available_years_dates]
    if not available_years:
        available_years = [timezone.now().year]

    # Fetch available printers
    printers = Printer.objects.all().order_by('name')

    # Base query for print files
    print_files = PrintFile.objects.all()

    # Apply filters
    if year_filter and year_filter.isdigit():
        print_files = print_files.filter(created_at__year=int(year_filter))
    if printer_filter and printer_filter.isdigit():
        print_files = print_files.filter(printer_id=int(printer_filter))

    # Basic metrics
    total_prints = print_files.count()
    successful_prints = print_files.filter(status='DONE').count()
    failed_prints = print_files.filter(status='FAILED').count()
    active_prints = print_files.filter(status__in=['TODO', 'PRINTING']).count()

    total_valid = successful_prints + failed_prints
    success_rate = (successful_prints / total_valid * 100) if total_valid > 0 else 0

    # Total print time (only completed prints)
    total_seconds = print_files.filter(status='DONE').aggregate(total=Sum('print_time_seconds'))['total'] or 0
    h = total_seconds // 3600
    m = (total_seconds % 3600) // 60
    total_time_formatted = f"{h} ore {m} min"

    # Pre-fetch global setting configs for electricity and wear tear
    cost_setting, _ = GlobalSetting.objects.get_or_create(
        key='electricity_cost_kwh',
        defaults={'value': Decimal('0.25')}
    )
    cost_kwh = cost_setting.value

    wear_setting, _ = GlobalSetting.objects.get_or_create(
        key='wear_tear_coefficient',
        defaults={'value': Decimal('0.10')}
    )
    wear_cost_per_hour = wear_setting.value

    # Fetch completed prints with prefetched spools and printers for precise calculations
    completed_prints = print_files.filter(status__in=['DONE', 'FAILED']).prefetch_related(
        'filament_usages__spool__filament', 'printer'
    )

    # Cost calculations
    total_material_cost = Decimal('0.00')
    total_electricity_cost = Decimal('0.00')
    total_wear_tear_cost = Decimal('0.00')
    total_grams = 0.0

    # Filament type distribution (PLA, PETG, ABS, TPU, ASA) in grams
    material_distribution = {choice[0]: 0.0 for choice in Filament.MATERIAL_CHOICES}
    
    # Monthly aggregations
    monthly_data = defaultdict(lambda: {'count': 0, 'cost': Decimal('0.00'), 'grams': 0.0})

    for pf in completed_prints:
        # Calculate components for this specific print file
        pf_material_cost = Decimal('0.00')
        pf_grams = 0.0

        for usage in pf.filament_usages.all():
            grams = float(usage.grams_used)
            pf_grams += grams
            total_grams += grams
            
            # Add to material type distribution
            mat = usage.spool.filament.material
            if mat in material_distribution:
                material_distribution[mat] += grams
            else:
                material_distribution[mat] = material_distribution.get(mat, 0.0) + grams

            if usage.spool and usage.spool.initial_weight_g > 0:
                pf_material_cost += Decimal(str(usage.grams_used)) * (usage.spool.cost / Decimal(usage.spool.initial_weight_g))

        pf_elec_cost = Decimal('0.00')
        if pf.print_time_seconds and pf.printer and pf.printer.power_consumption > 0:
            hours = Decimal(pf.print_time_seconds) / Decimal('3600.0')
            kwh_used = (Decimal(pf.printer.power_consumption) * hours) / Decimal('1000.0')
            pf_elec_cost = (kwh_used * cost_kwh)

        pf_wear_cost = Decimal('0.00')
        if pf.print_time_seconds:
            hours = Decimal(pf.print_time_seconds) / Decimal('3600.0')
            pf_wear_cost = (hours * wear_cost_per_hour)

        # Totals
        total_material_cost += pf_material_cost
        total_electricity_cost += pf_elec_cost
        total_wear_tear_cost += pf_wear_cost

        # Monthly aggregation
        # Format key as YYYY-MM
        month_key = pf.created_at.strftime('%Y-%m')
        monthly_data[month_key]['count'] += 1
        monthly_data[month_key]['cost'] += (pf_material_cost + pf_elec_cost + pf_wear_cost)
        monthly_data[month_key]['grams'] += pf_grams

    total_cost = total_material_cost + total_electricity_cost + total_wear_tear_cost
    total_kg = total_grams / 1000.0

    # Print files per printer (including incomplete prints)
    printer_counts = print_files.values('printer__name').annotate(count=Count('id')).order_by('-count')
    printer_labels = [p['printer__name'] or 'N/D' for p in printer_counts]
    printer_values = [p['count'] for p in printer_counts]

    # Sort monthly data chronologically
    sorted_months = sorted(monthly_data.keys())
    monthly_labels = []
    # Convert monthly labels from YYYY-MM to MM/YYYY
    for m in sorted_months:
        parts = m.split('-')
        monthly_labels.append(f"{parts[1]}/{parts[0]}")

    monthly_print_counts = [monthly_data[m]['count'] for m in sorted_months]
    monthly_costs = [float(monthly_data[m]['cost']) for m in sorted_months]
    monthly_kg = [monthly_data[m]['grams'] / 1000.0 for m in sorted_months]

    # Convert material distribution to Kg
    material_distribution_kg = {k: round(v / 1000.0, 3) for k, v in material_distribution.items()}

    context = {
        'page_title': 'Statistiche',
        'available_years': available_years,
        'selected_year': int(year_filter) if year_filter.isdigit() else None,
        'printers': printers,
        'selected_printer': int(printer_filter) if printer_filter.isdigit() else None,
        
        # KPI values
        'total_prints': total_prints,
        'successful_prints': successful_prints,
        'failed_prints': failed_prints,
        'active_prints': active_prints,
        'success_rate': round(success_rate, 1),
        'total_time_formatted': total_time_formatted,
        'total_kg': round(total_kg, 2),
        'total_cost': round(total_cost, 2),
        'total_material_cost': round(total_material_cost, 2),
        'total_electricity_cost': round(total_electricity_cost, 2),
        'total_wear_tear_cost': round(total_wear_tear_cost, 2),

        # Charts data
        'chart_status_data': [successful_prints, failed_prints, active_prints],
        'chart_material_labels': list(material_distribution_kg.keys()),
        'chart_material_values': list(material_distribution_kg.values()),
        'chart_printer_labels': printer_labels,
        'chart_printer_values': printer_values,
        'chart_monthly_labels': monthly_labels,
        'chart_monthly_print_counts': monthly_print_counts,
        'chart_monthly_costs': monthly_costs,
        'chart_monthly_kg': monthly_kg,
    }

    return render(request, 'app_3dmage_management/statistics.html', context)
