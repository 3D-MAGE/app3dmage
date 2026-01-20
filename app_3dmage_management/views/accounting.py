from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Sum, F, Q
from django.forms.models import model_to_dict

from ..models import StockItem, Expense, ExpenseCategory, PaymentMethod
from ..forms import ExpenseForm, ManualIncomeForm, TransferForm, CorrectBalanceForm

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

    income_items = income_items_query.with_net_values().select_related('payment_method').order_by('-sold_at', '-id')
    expenses = expenses_query.order_by('-expense_date', '-id')

    total_income = income_items.aggregate(total=Sum('annotated_net_revenue'))['total'] or Decimal('0.00')
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
            income.save() # Salviamo per avere l'ID e i campi impostati
            income.payment_method.refresh_from_db()
            income.payment_method.balance += income.get_net_revenue()
            income.payment_method.save()
        else:
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

    # Gestione virgola nel backend se non gestita dal frontend o in fallback
    data = request.POST.copy()
    if 'new_balance' in data and ',' in str(data['new_balance']):
        data['new_balance'] = str(data['new_balance']).replace(',', '.')

    form = CorrectBalanceForm(data)
    if form.is_valid():
        payment_method.balance = form.cleaned_data['new_balance']
        payment_method.save()
        return JsonResponse({'status': 'ok'})

    # Restituisce JSON con errori per la gestione AJAX
    return JsonResponse({'status': 'error', 'errors': form.errors.as_json()}, status=400)

@login_required
def get_expense_details(request, expense_id):
    expense = get_object_or_404(Expense, id=expense_id)
    return JsonResponse(model_to_dict(expense)) 

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
