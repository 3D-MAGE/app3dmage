import json
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required

from ..models import Quote

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
