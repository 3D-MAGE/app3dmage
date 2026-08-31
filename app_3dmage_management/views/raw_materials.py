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
        'payment_methods': PaymentMethod.objects.all(),
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
@transaction.atomic
def edit_raw_material(request, material_id):
    material = get_object_or_404(RawMaterial, id=material_id)
    form = RawMaterialForm(request.POST, instance=material)
    if not form.is_valid():
        return JsonResponse({'status': 'error', 'errors': form.errors.as_json()}, status=400)
    
    updated_material = form.save()

    # Gestione modifica rapida di giacenza e costo dallo stock
    quantity_raw = request.POST.get('quantity')
    cost_raw = request.POST.get('cost')
    payment_method_id = request.POST.get('payment_method')

    if quantity_raw is not None and quantity_raw != '':
        try:
            quantity = int(quantity_raw)
            if quantity < 0:
                return JsonResponse({'status': 'error', 'message': 'La quantità non può essere negativa.'}, status=400)
        except ValueError:
            return JsonResponse({'status': 'error', 'message': 'Quantità non valida.'}, status=400)

        try:
            cost = Decimal(str(cost_raw).replace(',', '.')) if cost_raw and str(cost_raw).strip() != '' else Decimal('0.00')
            if cost < 0:
                return JsonResponse({'status': 'error', 'message': 'Il costo non può essere negativo.'}, status=400)
        except Exception:
            return JsonResponse({'status': 'error', 'message': 'Costo non valido.'}, status=400)

        purchases_qs = updated_material.purchases.all()
        purchases_count = purchases_qs.count()

        if purchases_count == 1:
            purchase = purchases_qs.first()
            old_cost = purchase.cost
            old_pm = purchase.payment_method
            old_expense = purchase.expense

            purchase.quantity = quantity
            purchase.cost = cost

            if payment_method_id is not None:
                new_pm = PaymentMethod.objects.filter(id=payment_method_id).first() if payment_method_id else None
            else:
                new_pm = old_pm

            purchase.payment_method = new_pm

            # Riallineamento contabilità
            if old_expense and old_pm:
                old_pm_db = PaymentMethod.objects.select_for_update().get(id=old_pm.id)
                old_pm_db.balance += old_cost
                old_pm_db.save()

            if new_pm and cost > 0:
                category, _ = ExpenseCategory.objects.get_or_create(name='Materie Prime')
                if old_expense:
                    old_expense.amount = cost
                    old_expense.payment_method = new_pm
                    old_expense.description = f"Acquisto materia prima: {quantity}x {updated_material.name}"
                    old_expense.save()
                    purchase.expense = old_expense
                else:
                    expense = Expense.objects.create(
                        description=f"Acquisto materia prima: {quantity}x {updated_material.name}",
                        amount=cost,
                        category=category,
                        expense_date=purchase.purchase_date,
                        payment_method=new_pm
                    )
                    purchase.expense = expense

                new_pm_db = PaymentMethod.objects.select_for_update().get(id=new_pm.id)
                new_pm_db.balance -= cost
                new_pm_db.save()
            else:
                if old_expense:
                    old_expense.delete()
                purchase.expense = None
                purchase.payment_method = None

            purchase.save()

        elif purchases_count == 0 and quantity > 0:
            new_pm = PaymentMethod.objects.filter(id=payment_method_id).first() if payment_method_id else None
            purchase = RawMaterialPurchase(
                raw_material=updated_material,
                quantity=quantity,
                cost=cost,
                purchase_date=datetime.date.today(),
                payment_method=new_pm
            )
            if new_pm and cost > 0:
                category, _ = ExpenseCategory.objects.get_or_create(name='Materie Prime')
                expense = Expense.objects.create(
                    description=f"Acquisto materia prima: {quantity}x {updated_material.name}",
                    amount=cost,
                    category=category,
                    expense_date=purchase.purchase_date,
                    payment_method=new_pm
                )
                purchase.expense = expense
                new_pm_db = PaymentMethod.objects.select_for_update().get(id=new_pm.id)
                new_pm_db.balance -= cost
                new_pm_db.save()
            purchase.save()

    return JsonResponse({'status': 'ok'})

@require_POST
@login_required
@transaction.atomic
def add_raw_material_purchase(request):
    form = RawMaterialPurchaseForm(request.POST)
    if form.is_valid():
        purchase = form.save(commit=False)
        payment_method = form.cleaned_data.get('payment_method')
        cost = form.cleaned_data.get('cost') or Decimal('0.00')
        purchase.cost = cost

        # Aggiornamento contabilità solo se è specificato un metodo di pagamento ed il costo è > 0
        if payment_method and cost > 0:
            category, created = ExpenseCategory.objects.get_or_create(name='Materie Prime')
            expense = Expense.objects.create(
                description=f"Acquisto materia prima: {purchase.quantity}x {purchase.raw_material.name}",
                amount=cost,
                category=category,
                expense_date=purchase.purchase_date,
                payment_method=payment_method
            )
            purchase.expense = expense
            payment_method.balance -= cost
            payment_method.save()
        else:
            purchase.payment_method = None
            purchase.expense = None

        purchase.save()
        return redirect('raw_materials_dashboard')
    
    return redirect('raw_materials_dashboard')

@login_required
def get_raw_material_purchase_details(request, purchase_id):
    purchase = get_object_or_404(RawMaterialPurchase.objects.select_related('raw_material', 'payment_method'), id=purchase_id)
    data = {
        'id': purchase.id,
        'raw_material_id': purchase.raw_material.id,
        'raw_material_name': purchase.raw_material.name,
        'quantity': purchase.quantity,
        'cost': str(purchase.cost),
        'purchase_date': purchase.purchase_date.strftime('%Y-%m-%d'),
        'purchase_link': purchase.purchase_link or '',
        'payment_method_id': purchase.payment_method_id or '',
        'payment_method_name': purchase.payment_method.name if purchase.payment_method else 'Già in casa / Nessuno',
    }
    return JsonResponse(data)

@require_POST
@login_required
@transaction.atomic
def edit_raw_material_purchase(request, purchase_id):
    purchase = get_object_or_404(RawMaterialPurchase.objects.select_related('expense', 'payment_method', 'raw_material'), id=purchase_id)
    old_cost = purchase.cost
    old_pm = purchase.payment_method
    old_expense = purchase.expense

    form = RawMaterialPurchaseForm(request.POST, instance=purchase)
    
    if not form.is_valid():
        return JsonResponse({'status': 'error', 'errors': form.errors.as_json()}, status=400)

    # Ripristina fondi vecchi
    if old_expense and old_expense.payment_method:
        old_pm_db = PaymentMethod.objects.select_for_update().get(id=old_expense.payment_method.id)
        old_pm_db.balance += old_expense.amount
        old_pm_db.save()
    elif old_pm and old_cost > 0:
        old_pm_db = PaymentMethod.objects.select_for_update().get(id=old_pm.id)
        old_pm_db.balance += old_cost
        old_pm_db.save()

    updated_purchase = form.save(commit=False)
    new_cost = form.cleaned_data.get('cost') or Decimal('0.00')
    new_pm = form.cleaned_data.get('payment_method')
    updated_purchase.cost = new_cost

    if new_pm and new_cost > 0:
        category, _ = ExpenseCategory.objects.get_or_create(name='Materie Prime')
        if old_expense:
            old_expense.amount = new_cost
            old_expense.expense_date = updated_purchase.purchase_date
            old_expense.description = f"Acquisto materia prima: {updated_purchase.quantity}x {updated_purchase.raw_material.name}"
            old_expense.payment_method = new_pm
            old_expense.save()
            updated_purchase.expense = old_expense
        else:
            expense = Expense.objects.create(
                description=f"Acquisto materia prima: {updated_purchase.quantity}x {updated_purchase.raw_material.name}",
                amount=new_cost,
                category=category,
                expense_date=updated_purchase.purchase_date,
                payment_method=new_pm
            )
            updated_purchase.expense = expense

        new_pm_db = PaymentMethod.objects.select_for_update().get(id=new_pm.id)
        new_pm_db.balance -= new_cost
        new_pm_db.save()
        updated_purchase.payment_method = new_pm
    else:
        if old_expense:
            old_expense.delete()
        updated_purchase.expense = None
        updated_purchase.payment_method = None

    updated_purchase.save()
    return JsonResponse({'status': 'ok', 'message': 'Acquisto modificato con successo.'})

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
    data['total_purchased'] = material.total_purchased
    data['remaining_quantity'] = material.remaining_quantity
    data['available_quantity'] = material.available_quantity
    data['average_unit_cost'] = str(material.average_unit_cost)

    purchases = []
    for p in material.purchases.select_related('payment_method').order_by('-purchase_date', '-id'):
        unit_c = (p.cost / Decimal(p.quantity)).quantize(Decimal('0.01')) if p.quantity else Decimal('0.00')
        purchases.append({
            'id': p.id,
            'quantity': p.quantity,
            'cost': str(p.cost),
            'unit_cost': str(unit_c),
            'purchase_date': p.purchase_date.strftime('%d/%m/%Y'),
            'purchase_date_iso': p.purchase_date.strftime('%Y-%m-%d'),
            'purchase_link': p.purchase_link or '',
            'payment_method_id': p.payment_method_id or '',
            'payment_method_name': p.payment_method.name if p.payment_method else 'Già in casa / Nessuno',
        })
    data['purchases'] = purchases
    data['purchases_count'] = len(purchases)
    if len(purchases) == 1:
        data['single_purchase'] = purchases[0]
    return JsonResponse(data)
