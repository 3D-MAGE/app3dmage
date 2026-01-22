import json
import re
import math
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db import transaction
from django.db.models import Sum, Prefetch
from django.forms.models import model_to_dict
from django.urls import reverse

from django.contrib import messages
from ..models import Project, MasterPrintFile, WorkOrder, PrintFile, StockItem, FilamentUsage, Spool, Filament, MasterFilamentUsage, Printer, Category, ProjectPart
from ..forms import WorkOrderForm, PrintFileForm, PrintFileEditForm, CompleteWorkOrderForm, MasterProjectForm, MasterPrintFileForm
from .filaments import _handle_filament_data # Importing helper function


@login_required
def project_detail(request, project_id):
    queryset = WorkOrder.objects.prefetch_related(
        Prefetch('print_files', queryset=PrintFile.objects.select_related('printer', 'plate')
                 .prefetch_related('filament_usages__spool__filament').order_by('project_part__name', 'created_at'))
    )
    work_order = get_object_or_404(queryset, id=project_id)

    total_project_cost = sum(file.total_cost for file in work_order.print_files.all())

    # Calcolo della quantità suggerita per il magazzino: 
    # Oggetti stampati effettivi (actual_quantity) meno oggetti già versati (produced_quantity)
    pending_quantity = work_order.total_objects_printed - work_order.produced_quantity
    if pending_quantity < 0: pending_quantity = 0

    referer = request.GET.get('from', 'kanban')

    if request.method == 'POST' and 'add_print_file_form' in request.POST:
        print_file_form = PrintFileForm(request.POST, work_order=work_order)
        if print_file_form.is_valid():
            new_print_file = print_file_form.save(commit=False)
            new_print_file.work_order = work_order
            minutes = print_file_form.cleaned_data['print_time_minutes']
            new_print_file.print_time_seconds = minutes * 60
            new_print_file.save()
            return redirect('project_detail', project_id=work_order.id)
    else:
        print_file_form = PrintFileForm(initial={'work_order': work_order}, work_order=work_order)

    context = {
        'project': work_order,
        'total_project_cost': total_project_cost,
        'completion_form': CompleteWorkOrderForm(initial={
            'stock_item_name': work_order.name, 
            'stock_item_quantity': pending_quantity if pending_quantity > 0 else work_order.quantity
        }),
        'edit_project_form': WorkOrderForm(instance=work_order),
        'add_print_file_form': print_file_form,
        'edit_print_file_form': PrintFileEditForm(work_order=work_order),
        'can_be_completed': not work_order.print_files.filter(status__in=['TODO', 'PRINTING']).exists() and work_order.print_files.exists(),
        'page_title': 'Ordine di Lavoro',
        'referer': referer
    }
    return render(request, 'app_3dmage_management/work_order_detail.html', context)

@require_POST
@login_required
def add_project(request):
    form = WorkOrderForm(request.POST)
    if form.is_valid():
        form.save()
    return redirect(request.META.get('HTTP_REFERER', 'project_dashboard'))

@require_POST
@login_required
def edit_project(request, project_id):
    work_order = get_object_or_404(WorkOrder, id=project_id)
    form = WorkOrderForm(request.POST, instance=work_order)
    if form.is_valid():
        form.save()
        return JsonResponse({'status': 'ok'})
    return JsonResponse({'status': 'error', 'errors': form.errors.as_json()}, status=400)

@require_POST
@login_required
def edit_work_order_notes(request, project_id):
    work_order = get_object_or_404(WorkOrder, id=project_id)
    notes = request.POST.get('notes')
    work_order.notes = notes
    work_order.save()
    return redirect('project_detail', project_id=work_order.id)

@require_POST
@login_required
@transaction.atomic
def sync_work_order_to_master(request, project_id):
    """
    Sincronizza le modifiche dell'Ordine di Lavoro corrente verso il Progetto Master di origine.
    Aggiorna: Annotazioni, Categoria e i Template dei File di Stampa.
    """
    work_order = get_object_or_404(WorkOrder.objects.prefetch_related('print_files__filament_usages'), id=project_id)
    master_project = work_order.project

    if not master_project:
        return JsonResponse({'status': 'error', 'message': 'Questo ordine non è collegato a un Progetto Master.'}, status=400)

    # 1. Aggiorna dati base del Master
    master_project.notes = work_order.notes
    master_project.category = work_order.category
    # Non aggiorniamo il nome per evitare di perdere il riferimento se l'utente ha rinominato l'ordine
    master_project.save() # Questo triggera updated_at

    # 2. Sincronizza File di Stampa
    # Per semplicità e pulizia, ricreiamo i template basandoci sulla configurazione attuale dell'ordine.
    # Questo assicura che se sono stati aggiunti o rimossi file nell'ordine, il master si allinei.
    
    # Rimuoviamo i vecchi MasterPrintFile
    master_project.master_print_files.all().delete()

    for wo_file in work_order.print_files.all():
        # Recuperiamo le parti se disponibili dal file originale
        # Ora usiamo la parte specifica del file di stampa se presente
        original_parts = [wo_file.project_part] if wo_file.project_part else []
        
        # Se non ha una parte specifica, proviamo a recuperare tutte quelle del template master
        if not original_parts and wo_file.master_print_file:
            original_parts = list(wo_file.master_print_file.project_parts.all())

        # Creiamo il nuovo MasterPrintFile
        master_file = MasterPrintFile.objects.create(
            project=master_project,
            name=wo_file.name,
            estimated_time_seconds=wo_file.print_time_seconds,
            printer=wo_file.printer,
            plate=wo_file.plate,
            produced_quantity=wo_file.produced_quantity
        )
        
        if original_parts:
            master_file.project_parts.set(original_parts)

        # Copiamo i filamenti usati
        for usage in wo_file.filament_usages.all():
            if usage.spool and usage.spool.filament:
                MasterFilamentUsage.objects.create(
                    master_print_file=master_file,
                    filament=usage.spool.filament,
                    grams_used=usage.grams_used
                )

    return JsonResponse({
        'status': 'ok', 
        'message': f'Progetto Master "{master_project.name}" aggiornato correttamente.'
    })

@require_POST
@require_POST
@login_required
@transaction.atomic
def complete_project(request, project_id):
    work_order = get_object_or_404(WorkOrder.objects.select_for_update().prefetch_related('print_files'), id=project_id)
    
    # Leggiamo i dati degli output inviati (JSON)
    outputs_data_str = request.POST.get('outputs_data', '[]')
    try:
        outputs_data = json.loads(outputs_data_str)
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Dati output non validi.'}, status=400)

    labor_cost_total = Decimal(request.POST.get('labor_cost', '0.00') or '0.00')
    
    if not outputs_data:
        # Fallback per compatibilità col vecchio form se non c'è JSON
        stock_item_quantity = int(request.POST.get('stock_item_quantity', 0))
        if stock_item_quantity > 0:
            outputs_data = [{
                'name': request.POST.get('stock_item_name', work_order.name),
                'quantity': stock_item_quantity,
                'is_default': True
            }]

    if not outputs_data:
        return redirect('project_detail', project_id=work_order.id)

    # NUOVO: Generiamo il custom_id se non esiste
    if not work_order.custom_id:
        current_year_str = timezone.now().strftime('%y')
        last_wo_this_year = WorkOrder.objects.filter(custom_id__startswith=current_year_str, custom_id__regex=r'^\d{5}$').order_by('-custom_id').first()
        new_sequential = 1
        if last_wo_this_year:
            try:
                last_sequential = int(last_wo_this_year.custom_id[2:])
                new_sequential = last_sequential + 1
            except (ValueError, IndexError):
                pass
        work_order.custom_id = f"{current_year_str}{new_sequential:03d}"

    total_added_quantity = sum(item['quantity'] for item in outputs_data)
    
    # Pro-rata dei costi in base alla quantità totale aggiunta rispetto alla quantità di progetto
    # Pezzi totali previsti
    total_expected_pieces = work_order.quantity
    
    cost_per_piece = work_order.full_total_cost / total_expected_pieces if total_expected_pieces > 0 else Decimal('0.00')
    labor_per_piece = labor_cost_total / total_added_quantity if total_added_quantity > 0 else Decimal('0.00')

    for item in outputs_data:
        qty = int(item['quantity'])
        if qty <= 0: continue
        
        name = item['name']
        mat_cost = (cost_per_piece * qty).quantize(Decimal('0.01'))
        lab_cost = (labor_per_piece * qty).quantize(Decimal('0.01'))
        
        # Cerchiamo se esiste già un StockItem "POST_PROD" per questo output
        # Il nome è il nostro "id" per ora, come concordato.
        stock_item = StockItem.objects.filter(work_order=work_order, name=name, status=StockItem.Status.POST_PROD).first()
        
        if stock_item:
            stock_item.quantity += qty
            stock_item.material_cost += mat_cost
            stock_item.labor_cost += lab_cost
        else:
            stock_item = StockItem.objects.create(
                work_order=work_order,
                custom_id=work_order.custom_id,
                name=name,
                quantity=qty,
                material_cost=mat_cost,
                labor_cost=lab_cost,
                status=StockItem.Status.POST_PROD
            )
        
        # Ricalcolo prezzo suggerito: usa quello del Master se presente, altrimenti calcola margina 1.5x
        if work_order.project and work_order.project.suggested_selling_price:
            stock_item.suggested_price = work_order.project.suggested_selling_price
        else:
            total_prod_cost = stock_item.material_cost + stock_item.labor_cost
            unit_cost = total_prod_cost / stock_item.quantity if stock_item.quantity > 0 else Decimal('0.00')
            stock_item.suggested_price = (unit_cost * Decimal('1.5')).quantize(Decimal('0.01'))
        
        stock_item.save()

    # Aggiorniamo la quantità prodotta dell'ordine in "unità master"
    # Se abbiamo prodotto 3 pezzi del Master X che ne prevede 3 per unità, abbiamo fatto 1 unità master.
    total_pieces_per_master = work_order.project.outputs.aggregate(Sum('quantity'))['quantity__sum'] or 1
    if total_pieces_per_master > 0:
        master_units_completed = Decimal(total_added_quantity) / Decimal(total_pieces_per_master)
    else:
        master_units_completed = Decimal(total_added_quantity)
    
    # Usiamo Decimal per precisione, poi arrotondiamo per l'intero prodotto (ma forse meglio int(total_produced) / total_pieces_per_master)
    # Lo user ha detto "producibilità parziale", quindi l'ordine è DONE solo se ALL pezzi (tutti gli output) sono a magazzino.
    
    # Lo user ha detto "producibilità parziale", quindi l'ordine è DONE solo se ALL pezzi (tutti gli output) sono a magazzino.
    work_order.produced_quantity = StockItem.objects.filter(work_order=work_order).aggregate(Sum('quantity'))['quantity__sum'] or 0
    
    if work_order.produced_quantity >= work_order.quantity:
        work_order.status = WorkOrder.Status.DONE
        work_order.completed_at = timezone.now()
    else:
        # Se era PRINTED (finito di stampare) ma abbiamo fatto solo un versamento parziale, 
        # non lo mettiamo DONE, resta in uno stato che permetta altri versamenti.
        # Se tutti i file sono DONE, sync_status lo metterebbe in PRINTED.
        work_order.sync_status() 
    
    work_order.save()
    return redirect('inventory_dashboard')

@require_POST
@login_required
def delete_project(request, project_id):
    work_order = get_object_or_404(WorkOrder, id=project_id)
    work_order.delete()
    return redirect('project_dashboard')

@require_POST
@login_required
@transaction.atomic
def add_print_file(request):
    try:
        filament_data = json.loads(request.POST.get('filament_data', '[]'))
        if not filament_data:
            return JsonResponse({'status': 'error', 'message': 'È richiesto almeno un filamento.'}, status=400)

        try:
            days = int(request.POST.get('print_time_days', 0) or 0)
            hours = int(request.POST.get('print_time_hours', 0) or 0)
            minutes = int(request.POST.get('print_time_minutes', 0) or 0)
            total_seconds = (days * 86400) + (hours * 3600) + (minutes * 60)
        except (ValueError, TypeError):
            return JsonResponse({'status': 'error', 'message': 'Il tempo di stampa deve essere un numero valido.'}, status=400)

        if total_seconds < 60:
            return JsonResponse({'status': 'error', 'message': 'Il tempo di stampa deve essere di almeno 1 minuto.'}, status=400)

        # Get work order for form validation (to filter parts)
        work_order_id = request.POST.get('work_order')
        work_order = get_object_or_404(WorkOrder, id=work_order_id)
        form = PrintFileForm(request.POST, work_order=work_order)
        if form.is_valid():
            print_file = form.save(commit=False)
            print_file.print_time_seconds = total_seconds

            if print_file.actual_quantity is None:
                print_file.actual_quantity = 0

            print_file.save()

            _handle_filament_data(
                request,
                print_file=print_file,
                filament_data_json=request.POST.get('filament_data', '[]')
            )

            work_order = print_file.work_order
            produced_per_print = print_file.produced_quantity

            objects_already_produced = work_order.print_files.exclude(id=print_file.id).aggregate(total=Sum('produced_quantity'))['total'] or 0

            if produced_per_print > 0:
                remaining_to_produce = work_order.quantity - objects_already_produced - produced_per_print

                if remaining_to_produce > 0:
                    copies_to_suggest = remaining_to_produce // produced_per_print
                    final_remainder = remaining_to_produce % produced_per_print

                    if copies_to_suggest > 0 or final_remainder > 0:
                         return JsonResponse({
                            'status': 'ok_suggestion',
                            'message': 'File aggiunto!',
                            'suggestion': {
                                'count': copies_to_suggest,
                                'remainder': final_remainder,
                                'file_id': print_file.id
                            }
                        })

            work_order.sync_status()
            return JsonResponse({'status': 'ok', 'message': 'File aggiunto con successo!'})
        else:
            return JsonResponse({'status': 'error', 'errors': form.errors.as_json()}, status=400)

    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Dati filamento non validi.'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'Errore imprevisto: {str(e)}'}, status=500)

@require_POST
@transaction.atomic
@login_required
def clone_print_file(request):
    try:
        data = json.loads(request.body)
        original_file_id = data.get('file_id')
        count = int(data.get('count', 0))

        if not original_file_id or count <= 0:
            return JsonResponse({'status': 'error', 'message': 'Dati per la clonazione non validi.'}, status=400)

        original_file = PrintFile.objects.select_related('work_order').get(id=original_file_id)

        base_name = re.sub(r'\s\(\d+\)$', '', original_file.name).strip()
        for suffix in [" (Copia)", " (Da ristampare)"]:
             if base_name.endswith(suffix):
                base_name = base_name[:-len(suffix)]

        existing_files = PrintFile.objects.filter(
            work_order=original_file.work_order,
            name__startswith=base_name
        )
        max_num = 0
        if existing_files.filter(name=base_name).exists():
            max_num = 1
        for file in existing_files:
            match = re.search(r'\((\d+)\)$', file.name)
            if match:
                num = int(match.group(1))
                if num > max_num:
                    max_num = num

        start_num = max_num + 1

        for i in range(count):
            new_name = f"{base_name} ({start_num + i})"
            new_file = PrintFile.objects.create(
                work_order=original_file.work_order,
                name=new_name,
                printer=original_file.printer,
                plate=original_file.plate,
                print_time_seconds=original_file.print_time_seconds,
                status=PrintFile.Status.TODO,
                produced_quantity=original_file.produced_quantity,
                actual_quantity=0,
                queue_position=0
            )
            for usage in original_file.filament_usages.all():
                FilamentUsage.objects.create(
                    print_file=new_file,
                    spool=usage.spool,
                    grams_used=usage.grams_used
                )

        original_file.work_order.sync_status()
        return JsonResponse({'status': 'ok', 'message': f'{count} copie create con successo.'})
    except PrintFile.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'File originale non trovato.'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'Errore durante la clonazione: {str(e)}'}, status=500)


@require_POST
@login_required
def edit_print_file(request, file_id):
    instance = get_object_or_404(PrintFile, id=file_id)

    try:
        filament_data = json.loads(request.POST.get('filament_data', '[]'))
        if not filament_data:
            return JsonResponse({'status': 'error', 'message': 'È richiesto almeno un filamento.'}, status=400)

        try:
            days = int(request.POST.get('print_time_days', 0) or 0)
            hours = int(request.POST.get('print_time_hours', 0) or 0)
            minutes = int(request.POST.get('print_time_minutes', 0) or 0)
            total_seconds = (days * 86400) + (hours * 3600) + (minutes * 60)
        except (ValueError, TypeError):
            return JsonResponse({'status': 'error', 'message': 'Il tempo di stampa deve essere un numero valido.'}, status=400)

        if total_seconds < 60:
            return JsonResponse({'status': 'error', 'message': 'Il tempo di stampa deve essere di almeno 1 minuto.'}, status=400)

        form = PrintFileEditForm(request.POST, instance=instance)
        if form.is_valid():
            new_status = form.cleaned_data.get('status')

            if new_status == 'PRINTING' and instance.work_order.status == WorkOrder.Status.QUOTE:
                 return JsonResponse({
                    'status': 'error',
                    'message': 'Impossibile mettere in stampa se l\'ordine è ancora in "Preventivo". Spostalo in "Da stampare".'
                }, status=400)

            print_file = form.save(commit=False)
            print_file.print_time_seconds = total_seconds

            if print_file.actual_quantity is None:
                print_file.actual_quantity = 0

            print_file.save()
            instance.work_order.sync_status()

            wasted_grams_str = request.POST.get('wasted_grams') if new_status == 'FAILED' else None

            _handle_filament_data(
                request,
                print_file=print_file,
                filament_data_json=request.POST.get('filament_data', '[]'),
                wasted_grams_str=wasted_grams_str
            )

            return JsonResponse({'status': 'ok', 'message': 'Modifiche salvate!', 'new_print_status': print_file.status})
        else:
            return JsonResponse({'status': 'error', 'errors': form.errors.as_json()}, status=400)

    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Dati filamento non validi.'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'Errore imprevisto: {str(e)}'}, status=500)

@require_POST
@transaction.atomic
@login_required
def requeue_print_file(request, file_id):
    try:
        original_file = get_object_or_404(PrintFile, id=file_id)

        data = json.loads(request.body)
        planned_filaments = data.get('filaments', [])

        new_file = PrintFile.objects.create(
            work_order=original_file.work_order,
            name=f"{original_file.name.replace(' (Da ristampare)', '')} (Da ristampare)",
            printer=original_file.printer,
            plate=original_file.plate,
            print_time_seconds=original_file.print_time_seconds,
            status=PrintFile.Status.TODO,
            queue_position=0
        )

        if planned_filaments:
            for usage_data in planned_filaments:
                spool_id = usage_data.get('spool_id')
                grams = usage_data.get('grams')
                if spool_id and grams:
                    spool = get_object_or_404(Spool, id=spool_id)
                    FilamentUsage.objects.create(
                        print_file=new_file,
                        spool=spool,
                        grams_used=grams
                    )
        else:
            for usage in original_file.filament_usages.all():
                FilamentUsage.objects.create(
                    print_file=new_file,
                    spool=usage.spool,
                    grams_used=usage.grams_used
                )

        return JsonResponse({'status': 'ok', 'message': 'File rimesso in coda con successo.'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
def get_print_file_details(request, file_id):
    print_file = get_object_or_404(PrintFile, id=file_id)
    data = model_to_dict(print_file, fields=['name', 'printer', 'plate', 'project_part', 'status', 'produced_quantity', 'actual_quantity'])
    data['print_time_seconds'] = print_file.print_time_seconds
    data['filaments_used'] = list(print_file.filament_usages.select_related('spool__filament').values('spool__filament_id', 'spool_id', 'grams_used'))
    return JsonResponse(data)

@login_required
def api_get_all_projects(request):
    work_orders = WorkOrder.objects.filter(status__in=['QUOTE', 'TODO', 'PRINTING', 'PRINTED']).order_by('name')
    data = [{'id': wo.id, 'name': wo.name} for wo in work_orders]
    return JsonResponse(data, safe=False)


@require_POST
@login_required
def delete_print_file(request, file_id):
    try:
        print_file = get_object_or_404(PrintFile, id=file_id)
        print_file.delete()
        return JsonResponse({'status': 'ok', 'message': 'File eliminato con successo.'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@require_POST
@login_required
def update_project_status(request):
    try:
        data = json.loads(request.body)
        project_id, new_status = data.get('project_id'), data.get('new_status')
        if not project_id or not new_status:
            return HttpResponseBadRequest("Dati mancanti.")
        work_order = WorkOrder.objects.get(id=project_id)
        work_order.status = new_status
        work_order.save()
        return JsonResponse({'status': 'ok', 'message': f'Ordine {work_order.name} aggiornato'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@require_POST
@login_required
@transaction.atomic
def reprint_project(request, project_id):
    original_wo = get_object_or_404(WorkOrder.objects.prefetch_related('print_files__filament_usages__spool'), id=project_id)

    new_wo = WorkOrder.objects.create(
        name=f"{original_wo.name} (Ristampa)",
        category=original_wo.category,
        priority=original_wo.priority,
        quantity=original_wo.quantity,
        notes=original_wo.notes,
        status=WorkOrder.Status.TODO
    )

    for old_file in original_wo.print_files.exclude(status='FAILED'):
        new_file = PrintFile.objects.create(
            work_order=new_wo,
            name=old_file.name,
            printer=old_file.printer,
            plate=old_file.plate,
            print_time_seconds=old_file.print_time_seconds,
            status=PrintFile.Status.TODO
        )
        for usage in old_file.filament_usages.all():
            FilamentUsage.objects.create(
                print_file=new_file,
                spool=usage.spool,
                grams_used=usage.grams_used
            )

    return redirect('project_dashboard')

@require_POST
@login_required
def update_project_inline(request, project_id):
    try:
        data = json.loads(request.body)
        field = data.get('field')
        value = data.get('value')

        work_order = get_object_or_404(WorkOrder, id=project_id)

        if field not in ['status', 'priority']:
            return JsonResponse({'status': 'error', 'message': 'Campo non valido.'}, status=400)

        setattr(work_order, field, value)
        work_order.save()

        return JsonResponse({'status': 'ok', 'message': f'Campo {field} aggiornato.'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@require_POST
@transaction.atomic
@login_required
def create_project_from_quote(request):
    try:
        data = json.loads(request.body)

        if not data.get('name') or not data.get('materials'):
            return JsonResponse({'status': 'error', 'message': 'Nome dell\'ordine e materiali sono obbligatori.'}, status=400)

        total_seconds = (int(data.get('hours', 0)) * 3600) + (int(data.get('minutes', 0)) * 60)
        if total_seconds <= 0:
            return JsonResponse({'status': 'error', 'message': 'Il tempo di stampa deve essere maggiore di zero.'}, status=400)

        new_wo = WorkOrder.objects.create(
            name=data['name'],
            notes=f"Creato da preventivo in data {timezone.now().strftime('%d/%m/%Y')}",
            status=WorkOrder.Status.QUOTE
        )

        print_file = PrintFile.objects.create(
            work_order=new_wo,
            name=f"{data['name']} (file unico)",
            print_time_seconds=total_seconds,
            status=PrintFile.Status.TODO
        )

        for material in data['materials']:
            filament_id = material.get('filament_id')
            grams = material.get('grams')
            if filament_id and grams:
                first_available_spool = Spool.objects.filter(filament_id=filament_id).first()

                if first_available_spool:
                    FilamentUsage.objects.create(
                        print_file=print_file,
                        spool=first_available_spool,
                        grams_used=Decimal(grams)
                    )
                else:
                    filament = get_object_or_404(Filament, id=filament_id)
                    return JsonResponse({
                        'status': 'error',
                        'message': f"Nessuna bobina disponibile per il filamento '{filament}'. Aggiungine una prima di creare l'ordine."
                    }, status=400)

        return JsonResponse({
            'status': 'ok',
            'message': 'Ordine creato con successo!',
            'project_url': reverse('project_detail', args=[new_wo.id])
        })

    except (json.JSONDecodeError, KeyError, TypeError) as e:
        return JsonResponse({'status': 'error', 'message': f'Dati non validi: {str(e)}'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'Errore del server: {str(e)}'}, status=500)

@require_POST
@transaction.atomic
@login_required
def reopen_project(request, pk):
    work_order = get_object_or_404(WorkOrder, pk=pk)

    # 1. Check stato ordine
    if work_order.status != WorkOrder.Status.DONE:
        return JsonResponse({'status': 'error', 'message': 'L\'ordine non è completato.'})

    # 2. Recupera tutti gli stock item di questo ordine
    related_stock_items = StockItem.objects.filter(work_order=work_order)

    # 3. VERIFICA VENDITE
    items_sold = related_stock_items.filter(
        status=StockItem.Status.SOLD
    ).exists()

    # --- BIVIO ---
    if items_sold:
        return JsonResponse({
            'status': 'sold',
            'message': 'Impossibile riaprire: oggetti già venduti.'
        })

    # 4. Esecuzione Riapertura (Se nessuno è stato venduto)
    try:
        with transaction.atomic():
            # Cancella gli oggetti a magazzino (che saranno IN_STOCK o POST_PROD)
            count, _ = related_stock_items.delete()

            # Ripristina ordine
            work_order.status = WorkOrder.Status.TODO
            work_order.completed_at = None
            work_order.save()

        target_url = reverse('project_dashboard')
        return JsonResponse({'status': 'ok', 'redirect_url': target_url})

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})

@login_required
def projects_library(request):
    search_query = request.GET.get('q', '')
    category_filter = request.GET.get('category', '')
    printer_filter = request.GET.get('printer', '')
    sort_by = request.GET.get('sort', 'newest')  # Default: più recente (per data aggiunta)
    
    # Base QuerySet
    projects = Project.objects.all().prefetch_related('master_print_files', 'parts')
    
    # 1. Filtri
    if search_query:
        projects = projects.filter(name__icontains=search_query)
    if category_filter:
        projects = projects.filter(category_id=category_filter)
    if printer_filter:
        projects = projects.filter(master_print_files__printer_id=printer_filter).distinct()
        
    # 2. Ordinamento
    if sort_by == 'updated':
        projects = projects.order_by('-updated_at')
    else: # newest o default
        projects = projects.order_by('-created_at')

    context = {
        'projects': projects,
        'page_title': 'Libreria Progetti',
        'all_categories': Category.objects.all(),
        'all_printers': Printer.objects.all(),
        'master_project_form': MasterProjectForm()
    }
    return render(request, 'app_3dmage_management/master_projects_library.html', context)

@require_POST
@login_required
def add_master_project(request):
    form = MasterProjectForm(request.POST, request.FILES)
    if form.is_valid():
        from ..models import ProjectPart
        master_project = form.save()
        
        # Creiamo le parti iniziali basandoci sulla scelta dell'utente
        initial_parts = form.cleaned_data.get('initial_parts_count', 1) or 1
        for i in range(initial_parts):
            ProjectPart.objects.create(
                project=master_project,
                name=f"Parte {i+1}",
                order=i+1
            )
        
        # Gestione Output iniziali dal POST
        from ..models import ProjectOutput
        output_names = request.POST.getlist('output_names[]')
        output_quantities = request.POST.getlist('output_quantities[]')
        for name, qty in zip(output_names, output_quantities):
            # Se il nome è vuoto, usa il nome del progetto
            o_name = name.strip() or master_project.name
            try:
                q = int(qty) if qty else 1
            except ValueError:
                q = 1
            ProjectOutput.objects.create(project=master_project, name=o_name, quantity=q)
            
        return redirect('project_master_detail', pk=master_project.id)
    
    # Se il form non è valido, mostra gli errori
    for field, errors in form.errors.items():
        for error in errors:
            messages.error(request, f"Errore nel campo {field}: {error}")
            
    return redirect('projects_library')

@login_required
def project_master_detail(request, pk):
    project = get_object_or_404(Project.objects.prefetch_related(
        'master_print_files__filament_usages',
        'parts'
    ), pk=pk)
    
    # Costruiamo una lista di dizionari per gestire la visualizzazione per parti
    # dato che un file può stare in più parti (M2M)
    parts_with_files = []
    
    # 1. Parti definite
    for part in project.parts.all():
        files = list(project.master_print_files.filter(project_parts=part).order_by('name'))
        for f in files:
            f.dtag = f.printer.tag if f.printer and f.printer.tag else "-"
        parts_with_files.append({
            'part': part,
            'files': files,
            'display_name': part.name
        })
    
    # 2. File senza parte
    unassigned_files = list(project.master_print_files.filter(project_parts__isnull=True).order_by('name'))
    for f in unassigned_files:
        f.dtag = f.printer.tag if f.printer and f.printer.tag else "-"
    if unassigned_files:
        parts_with_files.append({
            'part': None,
            'files': unassigned_files,
            'display_name': "File non assegnati"
        })

    context = {
        'project': project,
        'category_name': project.category.name if project.category else "Senza Categoria",
        'parts_with_files': parts_with_files,
        'page_title': f'Dettagli Master: {project.name}',
        'edit_master_form': MasterProjectForm(instance=project),
        'master_print_file_form': MasterPrintFileForm(),
        'all_filaments': Filament.objects.all().order_by('material', 'color_code'),
        'all_filaments_json': [
            {'id': f.id, 'name': f"{f.material}-{f.color_code}-{f.brand}", 'color_hex': f.color_hex or '#555'}
            for f in Filament.objects.all().order_by('material', 'color_code')
        ],
    }
    return render(request, 'app_3dmage_management/master_project_detail.html', context)

@require_POST
@login_required
def edit_master_project(request, pk):
    project = get_object_or_404(Project, pk=pk)
    form = MasterProjectForm(request.POST, request.FILES, instance=project)
    if form.is_valid():
        master_project = form.save()
        
        # Gestione Output dal POST (Sincronizzazione)
        from ..models import ProjectOutput
        output_names = request.POST.getlist('output_names[]')
        output_quantities = request.POST.getlist('output_quantities[]')
        output_ids = request.POST.getlist('output_ids[]') # Presenti se modifichiamo esistenti
        
        provided_ids = [int(oid) for oid in output_ids if oid]
        master_project.outputs.exclude(id__in=provided_ids).delete()
        
        for o_id, o_name_raw, o_qty in zip(output_ids, output_names, output_quantities):
            # Se il nome è vuoto, usa il nome del progetto
            o_name = o_name_raw.strip() or master_project.name
            try:
                qty = int(o_qty) if o_qty else 1
            except ValueError:
                qty = 1
                
            if o_id:
                try:
                    output = ProjectOutput.objects.get(id=o_id, project=master_project)
                    output.name = o_name
                    output.quantity = qty
                    output.save()
                except ProjectOutput.DoesNotExist:
                    ProjectOutput.objects.create(project=master_project, name=o_name, quantity=qty)
            else:
                ProjectOutput.objects.create(project=master_project, name=o_name, quantity=qty)

        # Gestione Parti dal POST (Sincronizzazione)
        from ..models import ProjectPart
        part_names = request.POST.getlist('part_names[]')
        part_ids = request.POST.getlist('part_ids[]')
        provided_part_ids = [int(pid) for pid in part_ids if pid]
        
        # Elimina parti rimosse
        master_project.parts.exclude(id__in=provided_part_ids).delete()
        
        for i, (p_id, p_name) in enumerate(zip(part_ids, part_names)):
            if not p_name.strip(): continue
            if p_id:
                try:
                    part = ProjectPart.objects.get(id=p_id, project=master_project)
                    part.name = p_name
                    part.order = i
                    part.save()
                except ProjectPart.DoesNotExist:
                    ProjectPart.objects.create(project=master_project, name=p_name, order=i)
            else:
                ProjectPart.objects.create(project=master_project, name=p_name, order=i)

        return redirect('project_master_detail', pk=project.id)
    
    # Se il form non è valido, mostra gli errori
    for field, errors in form.errors.items():
        for error in errors:
            messages.error(request, f"Errore nel campo {field}: {error}")
            
    return redirect('project_master_detail', pk=project.id)

@require_POST
@login_required
def delete_master_project(request, pk):
    project = get_object_or_404(Project, pk=pk)
    project.delete()
    return redirect('projects_library')

@require_POST
@login_required
def edit_master_notes(request, pk):
    project = get_object_or_404(Project, pk=pk)
    notes = request.POST.get('notes')
    project.notes = notes
    project.save()
    return redirect('project_master_detail', pk=project.id)

@require_POST
@login_required
def add_master_print_file(request, pk):
    project = get_object_or_404(Project, pk=pk)
    form = MasterPrintFileForm(request.POST)
    if form.is_valid():
        mpf = form.save(commit=False)
        mpf.project = project
        days = form.cleaned_data.get('estimated_time_days', 0) or 0
        hours = form.cleaned_data.get('estimated_time_hours', 0) or 0
        minutes = form.cleaned_data.get('estimated_time_minutes', 0) or 0
        mpf.estimated_time_seconds = (days * 86400) + (hours * 3600) + (minutes * 60)
        
        mpf.save()
        
        # Handle Project Parts (M2M)
        part_ids = request.POST.getlist('project_parts')
        if part_ids:
            mpf.project_parts.set(part_ids)
        else:
            mpf.project_parts.clear()
            
        mpf.produced_quantity = int(request.POST.get('produced_quantity', 1))
        
        mpf.save()
        _handle_master_filament_data(mpf, request.POST.get('filament_data', '[]'))
    return redirect('project_master_detail', pk=project.id)

def _handle_master_filament_data(mpf, filament_data_json):
    mpf.filament_usages.all().delete()
    try:
        filament_data = json.loads(filament_data_json)
    except:
        return
        
    for usage in filament_data:
        filament_id = usage.get('filament_id')
        grams = usage.get('grams')
        if filament_id and grams and Decimal(str(grams)) > 0:
            filament = get_object_or_404(Filament, id=filament_id)
            MasterFilamentUsage.objects.create(master_print_file=mpf, filament=filament, grams_used=grams)

@login_required
def get_master_print_file_details(request, file_id):
    mpf = get_object_or_404(MasterPrintFile, id=file_id)
    data = {
        'name': mpf.name,
        'printer': mpf.printer_id,
        'plate': mpf.plate_id,
        'project_parts': list(mpf.project_parts.values_list('id', flat=True)),
        'produced_quantity': mpf.produced_quantity,
        'estimated_time_days': mpf.estimated_time_seconds // 86400,
        'estimated_time_hours': (mpf.estimated_time_seconds % 86400) // 3600,
        'estimated_time_minutes': (mpf.estimated_time_seconds % 3600) // 60,
        'filaments': [
            {'filament_id': u.filament_id, 'grams': float(u.grams_used)}
            for u in mpf.filament_usages.all()
        ]
    }
    return JsonResponse(data)

@require_POST
@login_required
def edit_master_print_file(request, file_id):
    mpf = get_object_or_404(MasterPrintFile, id=file_id)
    form = MasterPrintFileForm(request.POST, instance=mpf)
    if form.is_valid():
        mpf = form.save(commit=False)
        days = form.cleaned_data.get('estimated_time_days', 0) or 0
        hours = form.cleaned_data.get('estimated_time_hours', 0) or 0
        minutes = form.cleaned_data.get('estimated_time_minutes', 0) or 0
        mpf.estimated_time_seconds = (days * 86400) + (hours * 3600) + (minutes * 60)
        
        mpf.save()
        
        # Handle Project Parts (M2M)
        part_ids = request.POST.getlist('project_parts')
        if part_ids:
            mpf.project_parts.set(part_ids)
        else:
            mpf.project_parts.clear()
            
        mpf.produced_quantity = int(request.POST.get('produced_quantity', 1))
        
        mpf.save()
        _handle_master_filament_data(mpf, request.POST.get('filament_data', '[]'))
    return redirect('project_master_detail', pk=mpf.project.id)

@require_POST
@login_required
def delete_master_print_file(request, file_id):
    mpf = get_object_or_404(MasterPrintFile, id=file_id)
    project_id = mpf.project.id
    mpf.delete()
    return redirect('project_master_detail', pk=project_id)

@require_POST
@login_required
@transaction.atomic
def create_from_template(request, pk):
    master_project = get_object_or_404(Project.objects.prefetch_related('master_print_files__filament_usages'), pk=pk)
    
    import json
    batch_data_str = request.POST.get('batch_data')
    
    if batch_data_str:
        try:
            batches = json.loads(batch_data_str)
        except json.JSONDecodeError:
            batches = []
    else:
        # Fallback se il JS non avesse inviato batch_data (compatibilità)
        # Cerchiamo di ricostruire un singolo lotto dai campi classici
        try:
            requested_quantity = int(request.POST.get('quantity', 1))
        except (ValueError, TypeError):
            requested_quantity = 1
        
        # Mappa stampante singola
        single_printers = {}
        for key, value in request.POST.items():
            if key.startswith('printer_for_part_'):
                part_id = key.split('_')[-1]
                single_printers[part_id] = value
        
        batches = [{'quantity': requested_quantity, 'printers': single_printers}]

    if not batches:
        return redirect('project_master_detail', pk=pk)

    # 1. Calcoliamo la quantità totale dell'ordine
    total_requested_quantity = sum(b.get('quantity', 0) for b in batches)

    # 2. Creiamo il WorkOrder (Ordine di Lavoro)
    new_wo = WorkOrder.objects.create(
        name=master_project.name,
        category=master_project.category,
        quantity=total_requested_quantity,
        project=master_project,
        status=WorkOrder.Status.TODO,
        notes=master_project.notes
    )
    
    # 3. Creiamo i PrintFile per ogni lotto
    for batch_idx, batch in enumerate(batches):
        batch_qty = batch.get('quantity', 0)
        if batch_qty <= 0:
            continue
            
        part_printer_map = batch.get('printers', {})
        
        for mpf in master_project.master_print_files.all():
            # Otteniamo le parti a cui appartiene il file (o una lista con None se non ne ha)
            file_parts = list(mpf.project_parts.all())
            if not file_parts:
                file_parts = [None]
                
            for part in file_parts:
                part_id_str = str(part.id) if part else 'None'
                selected_printer_id = part_printer_map.get(part_id_str)
                
                # Filtri Selezione Parte/Stampante nel lotto
                if selected_printer_id == 'skip':
                    continue
                
                if selected_printer_id:
                    # Se è stata scelta una stampante specifica per la parte in questo lotto,
                    # il file deve corrispondere a quella stampante
                    if mpf.printer and str(mpf.printer_id) != str(selected_printer_id):
                        continue
                elif mpf.printer:
                    # Se il file richiede una stampante ma non è configurata nel lotto, lo saltiamo
                    continue

                # Calcolo Moltiplicatore per il file in questo lotto
                file_multiplier = math.ceil(batch_qty / mpf.produced_quantity) if mpf.produced_quantity > 0 else 1

                for i in range(file_multiplier):
                    batch_suffix = f" (Set {batch_idx + 1})" if len(batches) > 1 else ""
                    multiplier_suffix = f" (Batch {i+1})" if file_multiplier > 1 else ""
                    part_suffix = f" [{part.name}]" if part else ""
                    
                    pf_name = f"{mpf.name}{part_suffix}{batch_suffix}{multiplier_suffix}"
                    
                    actual_printer_id = selected_printer_id if selected_printer_id and selected_printer_id != 'skip' else mpf.printer_id
                    
                    pf = PrintFile.objects.create(
                        work_order=new_wo,
                        master_print_file=mpf,
                        project_part=part,
                        name=pf_name,
                        print_time_seconds=mpf.estimated_time_seconds,
                        printer_id=actual_printer_id,
                        plate=mpf.plate,
                        produced_quantity=mpf.produced_quantity,
                        status=PrintFile.Status.TODO
                    )
                    
                    for master_usage in mpf.filament_usages.all():
                        spool = Spool.objects.filter(
                            filament=master_usage.filament,
                            is_active=True
                        ).first()
                        
                        if spool:
                            FilamentUsage.objects.create(
                                print_file=pf,
                                spool=spool,
                                grams_used=master_usage.grams_used
                            )

    return redirect('project_detail', project_id=new_wo.id)

@require_POST
@login_required
@transaction.atomic
def promote_to_master(request, project_id):
    """
    Crea un nuovo Progetto Master basandosi su un Ordine di Lavoro esistente.
    Utile per migrare dati storici o promuovere ordini personalizzati a template.
    """
    work_order = get_object_or_404(WorkOrder.objects.prefetch_related('print_files__filament_usages'), id=project_id)

    if work_order.project:
        return JsonResponse({'status': 'error', 'message': 'Questo ordine è già collegato a un Progetto Master.'}, status=400)

    # 1. Crea il Progetto Master
    master_project = Project.objects.create(
        name=work_order.name,
        category=work_order.category,
        notes=work_order.notes,
        base_quantity=1
    )

    # 2. Crea i MasterPrintFile basandosi sui file dell'ordine
    # Cerchiamo di raggruppare i file per nome se sono cloni, per evitare ridondanze nel master
    processed_names = set()
    
    for wo_file in work_order.print_files.all():
        # Puliamo il nome da eventuali " (1)", " (Copia)", ecc.
        base_name = re.sub(r'\s\(\d+\)$', '', wo_file.name).strip()
        for suffix in [" (Copia)", " (Da ristampare)"]:
            if base_name.endswith(suffix):
                base_name = base_name[:-len(suffix)]
        
        if base_name in processed_names:
            continue
            
        processed_names.add(base_name)

        # Creiamo il MasterPrintFile
        master_file = MasterPrintFile.objects.create(
            project=master_project,
            name=base_name,
            estimated_time_seconds=wo_file.print_time_seconds,
            printer=wo_file.printer,
            plate=wo_file.plate,
            produced_quantity=wo_file.produced_quantity
        )

        # Copiamo i filamenti
        for usage in wo_file.filament_usages.all():
            if usage.spool and usage.spool.filament:
                MasterFilamentUsage.objects.create(
                    master_print_file=master_file,
                    filament=usage.spool.filament,
                    grams_used=usage.grams_used
                )

    # 3. Colleghiamo l'ordine corrente al nuovo Master
    work_order.project = master_project
    work_order.save()

    return JsonResponse({
        'status': 'ok',
        'message': f'Progetto Master "{master_project.name}" creato correttamente e collegato a questo ordine.'
    })

@require_POST
@login_required
def manage_project_parts(request, pk):
    project = get_object_or_404(Project, pk=pk)
    part_names = request.POST.getlist('part_names[]')
    part_ids = request.POST.getlist('part_ids[]')
    
    # Simple logic: delete parts not in part_ids, update existing, add new
    existing_parts = project.parts.all()
    provided_ids = [int(pid) for pid in part_ids if pid]
    
    # Delete removed parts (files will be set to null project_part)
    existing_parts.exclude(id__in=provided_ids).delete()
    
    for i, (p_id, p_name) in enumerate(zip(part_ids, part_names)):
        if not p_name.strip(): continue
        if p_id:
            part = ProjectPart.objects.get(id=p_id)
            part.name = p_name
            part.order = i
            part.save()
        else:
            ProjectPart.objects.create(project=project, name=p_name, order=i)
            
    return redirect('project_master_detail', pk=project.id)

@require_POST
@login_required
def edit_project_part(request, part_id):
    part = get_object_or_404(ProjectPart, id=part_id)
    name = request.POST.get('name')
    if name:
        part.name = name
        part.save()
    return JsonResponse({'status': 'ok'})

@require_POST
@login_required
def delete_project_part(request, part_id):
    part = get_object_or_404(ProjectPart, id=part_id)
    project_id = part.project.id
    part.delete()
    return redirect('project_master_detail', pk=project_id)
@require_POST
@login_required
def manage_project_outputs(request, pk):
    from ..models import ProjectOutput
    project = get_object_or_404(Project, pk=pk)
    output_names = request.POST.getlist('output_names[]')
    output_quantities = request.POST.getlist('output_quantities[]')
    output_ids = request.POST.getlist('output_ids[]')
    
    existing_outputs = project.outputs.all()
    provided_ids = [int(oid) for oid in output_ids if oid]
    
    # Rimuoviamo gli output non presenti nella richiesta
    existing_outputs.exclude(id__in=provided_ids).delete()
    
    for i, (o_id, o_name, o_qty) in enumerate(zip(output_ids, output_names, output_quantities)):
        if not o_name.strip(): continue
        qty = int(o_qty) if o_qty else 1
        if o_id:
            output = ProjectOutput.objects.get(id=o_id)
            output.name = o_name
            output.quantity = qty
            output.save()
        else:
            ProjectOutput.objects.create(project=project, name=o_name, quantity=qty)
            
    return redirect('project_master_detail', pk=project.id)
