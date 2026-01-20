import json
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Sum, Count, F, OuterRef, Subquery, IntegerField, DecimalField, ExpressionWrapper
from django.db.models.functions import Coalesce
from django.forms.models import model_to_dict

from ..models import Filament, Spool, FilamentUsage, Expense, ExpenseCategory
from ..forms import FilamentForm, SpoolForm, SpoolEditForm

@login_required
def filament_dashboard(request):
    sort_by = request.GET.get('sort', 'material')
    order = request.GET.get('order', 'asc')
    order_prefix = '-' if order == 'desc' else ''

    active_spool_count_subquery = Spool.objects.filter(
        filament=OuterRef('pk'),
        is_active=True
    ).values('filament').annotate(c=Count('id')).values('c')

    all_filaments = Filament.objects.annotate(
        annotated_active_spool_count=Coalesce(Subquery(active_spool_count_subquery, output_field=IntegerField()), 0)
    )

    active_filaments_query = all_filaments.filter(annotated_active_spool_count__gt=0)

    active_initial_weight_subquery = Spool.objects.filter(
        filament=OuterRef('pk'), is_active=True
    ).values('filament').annotate(s=Sum('initial_weight_g')).values('s')

    active_used_weight_subquery = FilamentUsage.objects.filter(
        spool__filament=OuterRef('pk'), spool__is_active=True, print_file__status__in=['DONE', 'FAILED']
    ).values('spool__filament').annotate(s=Sum('grams_used')).values('s')

    active_adjustment_subquery = Spool.objects.filter(
        filament=OuterRef('pk'), is_active=True
    ).values('filament').annotate(s=Sum('weight_adjustment')).values('s')

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

    valid_sort_fields = ['material', 'brand', 'color_name', 'annotated_remaining_weight', 'annotated_total_used_weight', 'annotated_active_spool_count']
    if sort_by not in valid_sort_fields:
        sort_by = 'material'

    if sort_by == 'material':
        order_fields = (f'{order_prefix}material', f'{order_prefix}color_code', f'{order_prefix}brand')
    else:
        order_fields = (f'{order_prefix}{sort_by}',)

    active_filaments = active_filaments_query.order_by(*order_fields)

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
    # Mostra solo i filamenti che hanno almeno una bobina attiva (is_active=True)
    # Ordina per materiale e poi per codice colore (ignorando la marca come richiesto)
    filaments = Filament.objects.filter(spools__is_active=True).distinct().order_by('material', 'color_code')
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
