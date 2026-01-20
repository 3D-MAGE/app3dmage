from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required

from ..models import Notification

@login_required
def api_get_notifications(request):
    notifications = Notification.objects.filter(is_read=False)
    data = {
        'count': notifications.count(),
        'notifications': list(notifications.values('id', 'message', 'level', 'related_url'))[:5]
    }
    return JsonResponse(data)

@require_POST
@login_required
def api_mark_notifications_as_read(request):
    Notification.objects.filter(is_read=False).update(is_read=True)
    return JsonResponse({'status': 'ok'})

@require_POST
@login_required
def api_delete_notification(request, notification_id):
    notification = get_object_or_404(Notification, id=notification_id)
    notification.is_read = True
    notification.save()
    return JsonResponse({'status': 'ok'})
