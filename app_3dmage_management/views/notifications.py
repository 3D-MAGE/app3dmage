from datetime import timedelta
from django.shortcuts import get_object_or_404, render, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Sum

from ..models import Notification, Note, Spool, RawMaterial, WorkOrder


def generate_smart_alerts():
    """
    Genera notifiche automatiche basate sullo stato del sistema:
    - Note/promemoria scaduti o in scadenza oggi
    - Bobine filamento sotto i 150g o esaurite
    - Materie prime con stock a zero o negativo
    - Ordini di lavoro in ritardo rispetto alla data di consegna
    Evita duplicati se una notifica identica è già presente non letta o creata nelle ultime 24 ore.
    """
    now = timezone.now()
    today = now.date()
    yesterday = now - timedelta(hours=24)

    recent_messages = set(
        Notification.objects.filter(
            created_at__gte=yesterday
        ).values_list('message', flat=True)
    )

    new_notifications = []

    # 1. Note scadute o in scadenza oggi
    active_due_notes = Note.objects.filter(
        is_completed=False,
        due_date__lte=today
    ).order_by('due_date')[:10]

    for note in active_due_notes:
        if note.due_date < today:
            msg = f"Promemoria scaduto: {note.title}"
            lvl = Notification.NotificationLevel.DANGER
        else:
            msg = f"Promemoria per oggi: {note.title}"
            lvl = Notification.NotificationLevel.WARNING

        if msg not in recent_messages:
            new_notifications.append(
                Notification(
                    message=msg,
                    level=lvl,
                    related_url='/notes/'
                )
            )
            recent_messages.add(msg)

    # 2. Ordini di lavoro in ritardo
    overdue_orders = WorkOrder.objects.filter(
        status__in=[WorkOrder.Status.TODO, WorkOrder.Status.PRINTING],
        delivery_date__isnull=False,
        delivery_date__lt=today
    ).order_by('delivery_date')[:5]

    for order in overdue_orders:
        name_info = f" ({order.name})" if order.name else ""
        msg = f"Ordine #{order.id}{name_info} in ritardo sulla consegna!"
        if msg not in recent_messages:
            new_notifications.append(
                Notification(
                    message=msg,
                    level=Notification.NotificationLevel.DANGER,
                    related_url=f"/project/{order.id}/"
                )
            )
            recent_messages.add(msg)

    # 3. Bobine con meno di 150g
    for spool in Spool.objects.filter(is_active=True).select_related('filament')[:30]:
        try:
            rem_g = round(float(spool.remaining_weight), 1)
            if rem_g <= 150:
                if rem_g <= 0:
                    msg = f"Bobina #{spool.id} ({spool.filament}) esaurita (0g)!"
                    lvl = Notification.NotificationLevel.DANGER
                else:
                    msg = f"Bobina #{spool.id} ({spool.filament}) quasi vuota ({rem_g}g rimanenti)"
                    lvl = Notification.NotificationLevel.WARNING

                if msg not in recent_messages:
                    new_notifications.append(
                        Notification(
                            message=msg,
                            level=lvl,
                            related_url='/filaments/'
                        )
                    )
                    recent_messages.add(msg)
        except Exception:
            continue


    # 4. Materie prime a stock esaurito o negativo
    try:
        low_materials = RawMaterial.objects.with_stock_info()
        for mat in low_materials:
            stock = getattr(mat, 'annotated_total_stock', 0) or 0
            if stock <= 0:
                msg = f"Materia prima esaurita: {mat.name} (scorta: {stock})"
                if msg not in recent_messages:
                    new_notifications.append(
                        Notification(
                            message=msg,
                            level=Notification.NotificationLevel.WARNING,
                            related_url='/inventory/raw-materials/'
                        )
                    )
                    recent_messages.add(msg)
    except Exception:
        pass

    if new_notifications:
        Notification.objects.bulk_create(new_notifications)


@login_required
def api_get_notifications(request):
    generate_smart_alerts()

    notifications = Notification.objects.filter(is_read=False).order_by('-created_at')
    count = notifications.count()
    items = list(notifications.values('id', 'message', 'level', 'related_url', 'created_at')[:8])

    # Formattazione data leggibile
    for item in items:
        if item.get('created_at'):
            item['time_ago'] = item['created_at'].strftime('%d/%m %H:%M')

    return JsonResponse({
        'count': count,
        'notifications': items
    })


@require_POST
@login_required
def api_mark_notifications_as_read(request):
    Notification.objects.filter(is_read=False).update(is_read=True)
    return JsonResponse({'status': 'ok'})


@require_POST
@login_required
def api_delete_notification(request, notification_id):
    notification = get_object_or_404(Notification, id=notification_id)
    notification.delete()
    return JsonResponse({'status': 'ok'})


@login_required
def notifications_dashboard(request):
    generate_smart_alerts()

    status_filter = request.GET.get('status', 'unread')  # unread, all, read
    notifications_qs = Notification.objects.all().order_by('-created_at')

    if status_filter == 'unread':
        notifications_qs = notifications_qs.filter(is_read=False)
    elif status_filter == 'read':
        notifications_qs = notifications_qs.filter(is_read=True)

    unread_count = Notification.objects.filter(is_read=False).count()
    total_count = Notification.objects.count()

    context = {
        'notifications': notifications_qs[:100],
        'status_filter': status_filter,
        'unread_count': unread_count,
        'total_count': total_count,
        'page_title': 'Centro Notifiche',
    }
    return render(request, 'app_3dmage_management/notifications.html', context)


@require_POST
@login_required
def clear_all_notifications(request):
    Notification.objects.all().delete()
    return redirect('notifications_dashboard')

