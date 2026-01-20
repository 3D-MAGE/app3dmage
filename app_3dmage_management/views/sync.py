from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET, require_POST
from ..models import WorkOrder, StockItem, GlobalSetting
from decimal import Decimal

@login_required
@require_GET
def check_updates(request):
    """
    Check if the global app state has changed.
    Expects a 'v' GET parameter (timestamp).
    Returns 204 (No Content) if no change, or 200 with new version if change.
    """
    client_version = request.GET.get('v')
    # Intelligent Polling Check
    try:
        setting = GlobalSetting.objects.get(key='app_last_updated')
        # Check if value is valid decimal/string
        if setting.value is None or str(setting.value) == '':
           raise ValueError("Empty value")
        server_version = str(setting.value)
    except Exception:
         # Corrupt data, reset it
         from django.utils import timezone
         ts = str(timezone.now().timestamp())
         new_val = Decimal(ts)
         # Avoid reading corrupt data
         GlobalSetting.objects.filter(key='app_last_updated').delete()
         GlobalSetting.objects.create(key='app_last_updated', value=new_val)
         server_version = str(new_val)

    if client_version == server_version:
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
