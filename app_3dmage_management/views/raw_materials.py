import datetime
from decimal import Decimal
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.forms.models import model_to_dict
from django.db.models import Q

from ..models import RawMaterial, RawMaterialPurchase, Expense, ExpenseCategory, PaymentMethod
from ..forms import RawMaterialForm, RawMaterialPurchaseForm

@login_required
def raw_materials_dashboard(request):
    search_query = request.GET.get('q', '')
    raw_materials_query = RawMaterial.objects.all()

    if search_query:
        raw_materials_query = raw_materials_query.filter(name__icontains=search_query)

    # Separiamo materie prime disponibili da quelle esaurite
    materials = list(raw_materials_query)
    active_materials = []
    exhausted_materials = []

    for mat in materials:
        if mat.available_quantity > 0:
            active_materials.append(mat)
        else:
            exhausted_materials.append(mat)

    recent_purchases = RawMaterialPurchase.objects.select_related('raw_material', 'payment_method').all()[:20]

    context = {
        'active_materials': active_materials,
        'exhausted_materials': exhausted_materials,
        'raw_material_form': RawMaterialForm(),
        'purchase_form': RawMaterialPurchaseForm(),
        'recent_purchases': recent_purchases,
        'search_query': search_query,
        'page_title': 'Magazzino Materie Prime',
    }
    return render(request, 'app_3dmage_management/raw_materials.html', context)

@require_POST
@login_required
def add_raw_material(request):
    form = RawMaterialForm(request.POST)
    if form.is_valid():
        form.save()
        return JsonResponse({'status': 'ok'})
    return JsonResponse({'status': 'error', 'errors': form.errors.as_json()}, status=400)

@require_POST
@login_required
def edit_raw_material(request, material_id):
    material = get_object_or_404(RawMaterial, id=material_id)
    form = RawMaterialForm(request.POST, instance=material)
    if form.is_valid():
        form.save()
        return JsonResponse({'status': 'ok'})
    return JsonResponse({'status': 'error', 'errors': form.errors.as_json()}, status=400)

@require_POST
@login_required
@transaction.atomic
def add_raw_material_purchase(request):
    form = RawMaterialPurchaseForm(request.POST)
    if form.is_valid():
        purchase = form.save(commit=False)
        payment_method = form.cleaned_data['payment_method']
        cost = form.cleaned_data['cost']

        # Aggiornamento contabilità
        category, created = ExpenseCategory.objects.get_or_create(name='Materie Prime')
        expense = Expense.objects.create(
            description=f"Acquisto materia prima: {purchase.quantity}x {purchase.raw_material.name}",
            amount=cost,
            category=category,
            expense_date=purchase.purchase_date,
            payment_method=payment_method
        )

        purchase.expense = expense
        purchase.save()

        # Detrazione fondi
        payment_method.balance -= cost
        payment_method.save()

        return redirect('raw_materials_dashboard')
    
    # In caso di errore nel form, ridirigi con un messaggio o gestisci in altro modo
    return redirect('raw_materials_dashboard')

@require_POST
@login_required
@transaction.atomic
def delete_raw_material_purchase(request, purchase_id):
    purchase = get_object_or_404(RawMaterialPurchase, id=purchase_id)
    
    # Ripristina i fondi se c'è una spesa collegata e un metodo di pagamento
    if purchase.expense and purchase.expense.payment_method:
        purchase.expense.payment_method.balance += purchase.expense.amount
        purchase.expense.payment_method.save()
        purchase.expense.delete()
    elif purchase.payment_method:
        # Fallback se la spesa è stata eliminata manualmente ma il metodo di pagamento era ancora segnato
        purchase.payment_method.balance += purchase.cost
        purchase.payment_method.save()

    purchase.delete()
    return JsonResponse({'status': 'ok', 'message': 'Acquisto eliminato e contabilità stornata con successo.'})

@require_POST
@login_required
def delete_raw_material(request, material_id):
    material = get_object_or_404(RawMaterial, id=material_id)
    
    # Verifica se la materia prima è utilizzata
    if material.purchases.exists():
        return JsonResponse({
            'status': 'error',
            'message': 'Impossibile eliminare: esistono acquisti associati a questa materia prima. Rimuovi prima gli acquisti.'
        }, status=400)
        
    if material.project_usages.exists() or material.work_order_usages.exists():
        return JsonResponse({
            'status': 'error',
            'message': 'Impossibile eliminare: questa materia prima è usata in uno o più progetti o ordini di lavoro.'
        }, status=400)

    material.delete()
    return JsonResponse({'status': 'ok', 'message': 'Materia prima eliminata con successo.'})

@login_required
def get_raw_material_details(request, material_id):
    material = get_object_or_404(RawMaterial, id=material_id)
    data = model_to_dict(material)
    data['remaining_quantity'] = material.remaining_quantity
    data['available_quantity'] = material.available_quantity
    data['average_unit_cost'] = str(material.average_unit_cost)
    return JsonResponse(data)
