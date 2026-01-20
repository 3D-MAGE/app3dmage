import json
import datetime
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Sum, Q, Prefetch

from ..models import PrintFile, Printer, Plate, Spool, FilamentUsage

@login_required
def print_queue_board(request):
    from ..models import GlobalSetting
    from ..models import GlobalSetting
    # Intelligent Polling Check
    try:
        setting = GlobalSetting.objects.get(key='app_last_updated')
        if setting.value is None or str(setting.value) == '':
            raise ValueError("Empty value")
        current_server_version = str(setting.value)
    except Exception:
         # Corrupt data, reset it
         from django.utils import timezone
         from decimal import Decimal
         ts = str(timezone.now().timestamp())
         new_val = Decimal(ts)
         # Avoid reading corrupt data
         GlobalSetting.objects.filter(key='app_last_updated').delete()
         GlobalSetting.objects.create(key='app_last_updated', value=new_val)
         current_server_version = str(new_val)

    if request.headers.get('HX-Request'):
        client_version = request.GET.get('v')
        if client_version == current_server_version:
            return HttpResponse(status=204)

    active_print_files_qs = PrintFile.objects.filter(
        status__in=['TODO', 'PRINTING'],
        work_order__status__in=['TODO', 'PRINTING']
    ).select_related(
        'work_order', 'printer', 'plate'
    ).prefetch_related(
        'filament_usages__spool__filament'
    ).order_by('queue_position')

    printers_qs = Printer.objects.prefetch_related(
        Prefetch('print_files', queryset=active_print_files_qs, to_attr='queued_files')
    ).annotate(
        total_queued_seconds=Sum(
            'print_files__print_time_seconds',
            filter=Q(
                print_files__status__in=['TODO', 'PRINTING'],
                print_files__work_order__status__in=['TODO', 'PRINTING']
            )
        )
    ).order_by('name')

    printers_list = []
    for printer in printers_qs:
        printing_file = next((f for f in printer.queued_files if f.status == 'PRINTING'), None)
        todo_files = [f for f in printer.queued_files if f.status == 'TODO']
        total_seconds = printer.total_queued_seconds or 0
        printer.total_queued_time_formatted = str(datetime.timedelta(seconds=total_seconds))
        printer.printing_file = printing_file
        printer.todo_files = todo_files
        printers_list.append(printer)

    context = {
        'printers': printers_list,
        'page_title': 'Coda di Stampa',
        'server_version': current_server_version,
    }

    if request.headers.get('HX-Request'):
        return render(request, 'app_3dmage_management/partials/print_queue_content.html', context)

    return render(request, 'app_3dmage_management/print_queue.html', context)

@require_POST
@login_required
def update_print_queue(request):
    try:
        data = json.loads(request.body)
        printer_id, ordered_file_ids = data.get('printer_id'), data.get('file_ids', [])
        PrintFile.objects.filter(id__in=ordered_file_ids).update(printer_id=printer_id)
        for index, file_id in enumerate(ordered_file_ids):
            PrintFile.objects.filter(id=file_id).update(queue_position=index)
        return JsonResponse({'status': 'ok', 'message': 'Coda di stampa aggiornata.'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@login_required
def load_plates(request):
    printer_id = request.GET.get('printer_id')
    try:
        plates = Plate.objects.filter(printer_id=printer_id).values('id', 'name')
        return JsonResponse(list(plates), safe=False)
    except (ValueError, TypeError):
        return JsonResponse([], safe=False)

@require_POST
@transaction.atomic
@login_required
def set_print_file_status(request, file_id):
    try:
        data = json.loads(request.body)
        new_status = data.get('new_status')

        if new_status not in [choice[0] for choice in PrintFile.Status.choices]:
            return JsonResponse({'status': 'error', 'message': 'Stato non valido.'}, status=400)

        file_to_update = get_object_or_404(PrintFile, id=file_id)

        if new_status == 'PRINTING':
            if file_to_update.printer:
                PrintFile.objects.filter(
                    printer=file_to_update.printer,
                    status='PRINTING'
                ).exclude(id=file_id).update(status='TODO')
        
        # Automatizzazione quantità
        if new_status == 'DONE':
            file_to_update.actual_quantity = file_to_update.produced_quantity
        elif new_status == 'FAILED':
            file_to_update.actual_quantity = 0

        file_to_update.status = new_status
        file_to_update.save()

        # Sincronizza lo stato dell'ordine associato
        file_to_update.work_order.sync_status()

        return JsonResponse({
            'status': 'ok', 
            'message': 'Stato aggiornato con successo.',
            'new_progress': file_to_update.work_order.progress,
            'new_progress_percentage': file_to_update.work_order.progress_percentage
        })

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
