from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET, require_POST
from ..models import WorkOrder, StockItem, GlobalSetting, get_app_version
from decimal import Decimal

@login_required
@require_GET
def check_updates(request):
    """
    Check if the global app state has changed.
    Expects a 'v' GET parameter (timestamp/counter).
    Returns 204 (No Content) if no change, or 200 with new version if change.
    """
    client_version = request.GET.get('v')
    server_version = get_app_version()

    if client_version and client_version == server_version:
        return HttpResponse(status=204)
    
    return JsonResponse({'v': server_version})

@login_required
@require_POST
def lock_item(request, model_type, item_id):
    """Generic lock functionality for WorkOrders and StockItems."""
    model = WorkOrder if model_type == 'project' else StockItem
    item = get_object_or_404(model, id=item_id)
    
    # If already locked by someone else and not expired
    if item.is_locked(user=request.user):
        return JsonResponse({
            'status': 'locked', 
            'message': f'Oggetto bloccato da {item.locked_by.username}'
        }, status=403)
    
    # Set/Refresh lock
    item.locked_by = request.user
    item.locked_at = timezone.now()
    item.save()
    
    return JsonResponse({'status': 'ok'})

@login_required
@require_POST
def unlock_item(request, model_type, item_id):
    """Release a lock."""
    model = WorkOrder if model_type == 'project' else StockItem
    item = get_object_or_404(model, id=item_id)
    
    if item.locked_by == request.user:
        item.locked_by = None
        item.locked_at = None
        item.save()
        
    return JsonResponse({'status': 'ok'})
