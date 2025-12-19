import json
import re
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

from ..models import Project, PrintFile, StockItem, FilamentUsage, Spool, Filament
from ..forms import ProjectForm, PrintFileForm, PrintFileEditForm, CompleteProjectForm
from .filaments import _handle_filament_data # Importing helper function


@login_required
def project_detail(request, project_id):
    queryset = Project.objects.prefetch_related(
        Prefetch('print_files', queryset=PrintFile.objects.select_related('printer', 'plate')
                 .prefetch_related('filament_usages__spool__filament').order_by('created_at'))
    )
    project = get_object_or_404(queryset, id=project_id)

    total_project_cost = sum(file.total_cost for file in project.print_files.all())

    referer = request.GET.get('from', 'kanban')

    if request.method == 'POST' and 'add_print_file_form' in request.POST:
        print_file_form = PrintFileForm(request.POST)
        if print_file_form.is_valid():
            new_print_file = print_file_form.save(commit=False)
            new_print_file.project = project
            minutes = print_file_form.cleaned_data['print_time_minutes']
            new_print_file.print_time_seconds = minutes * 60
            new_print_file.save()
            return redirect('project_detail', project_id=project.id)
    else:
        print_file_form = PrintFileForm(initial={'project': project})

    context = {
        'project': project,
        'total_project_cost': total_project_cost,
        'completion_form': CompleteProjectForm(initial={'stock_item_name': project.name, 'stock_item_quantity': project.quantity}),
        'edit_project_form': ProjectForm(instance=project),
        'add_print_file_form': print_file_form,
        'edit_print_file_form': PrintFileEditForm(),
        'can_be_completed': not project.print_files.filter(status__in=['TODO', 'PRINTING']).exists() and project.print_files.exists(),
        'page_title': 'Progetti',
        'referer': referer
    }
    return render(request, 'app_3dmage_management/project_detail.html', context)

@require_POST
@login_required
def add_project(request):
    form = ProjectForm(request.POST)
    if form.is_valid():
        form.save()
    return redirect(request.META.get('HTTP_REFERER', 'project_dashboard'))

@require_POST
@login_required
def edit_project(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    form = ProjectForm(request.POST, instance=project)
    if form.is_valid():
        form.save()
        return JsonResponse({'status': 'ok'})
    return JsonResponse({'status': 'error', 'errors': form.errors.as_json()}, status=400)

@require_POST
@transaction.atomic
@login_required
def complete_project(request, project_id):
    project = get_object_or_404(Project.objects.prefetch_related('print_files'), id=project_id)
    form = CompleteProjectForm(request.POST)

    if form.is_valid():
        current_year_str = timezone.now().strftime('%y')
        last_project_this_year = Project.objects.filter(custom_id__startswith=current_year_str, custom_id__regex=r'^\d{5}$').order_by('-custom_id').first()
        new_sequential = 1
        if last_project_this_year:
            try:
                last_sequential = int(last_project_this_year.custom_id[2:])
                new_sequential = last_sequential + 1
            except (ValueError, IndexError):
                pass
        new_custom_id = f"{current_year_str}{new_sequential:03d}"

        project.status = Project.Status.DONE
        project.completed_at = timezone.now()
        project.custom_id = new_custom_id
        project.save()

        stock_item_quantity = form.cleaned_data['stock_item_quantity']
        labor_cost_for_batch = form.cleaned_data.get('labor_cost') or Decimal('0.00')

        production_cost_for_batch = project.full_total_cost

        total_cost_for_batch = production_cost_for_batch + labor_cost_for_batch

        cost_per_item = total_cost_for_batch / stock_item_quantity if stock_item_quantity > 0 else Decimal('0.00')

        suggested_price_per_item = cost_per_item * Decimal('1.5')

        stock_item, created = StockItem.objects.update_or_create(
            project=project,
            defaults={
                'custom_id': new_custom_id,
                'name': form.cleaned_data['stock_item_name'],
                'quantity': stock_item_quantity,
                'material_cost': production_cost_for_batch.quantize(Decimal('0.01')),
                'labor_cost': labor_cost_for_batch.quantize(Decimal('0.01')),
                'status': StockItem.Status.POST_PROD,
                'suggested_price': suggested_price_per_item.quantize(Decimal('0.01'))
            }
        )

        return redirect('inventory_dashboard')

    return redirect('project_detail', project_id=project.id)

@require_POST
@login_required
def delete_project(request, project_id):
    project = get_object_or_404(Project, id=project_id)
    project.delete()
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

        form = PrintFileForm(request.POST)
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

            project = print_file.project
            produced_per_print = print_file.produced_quantity

            objects_already_produced = project.print_files.exclude(id=print_file.id).aggregate(total=Sum('produced_quantity'))['total'] or 0

            if produced_per_print > 0:
                remaining_to_produce = project.quantity - objects_already_produced - produced_per_print

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

            project.sync_status()
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

        original_file = PrintFile.objects.select_related('project').get(id=original_file_id)

        base_name = re.sub(r'\s\(\d+\)$', '', original_file.name).strip()
        for suffix in [" (Copia)", " (Da ristampare)"]:
             if base_name.endswith(suffix):
                base_name = base_name[:-len(suffix)]

        existing_files = PrintFile.objects.filter(
            project=original_file.project,
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
                project=original_file.project,
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

        original_file.project.sync_status()
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

            if new_status == 'PRINTING' and instance.project.status == Project.Status.QUOTE:
                 return JsonResponse({
                    'status': 'error',
                    'message': 'Impossibile mettere in stampa se il progetto è ancora in "Preventivo". Spostalo in "Da stampare".'
                }, status=400)

            print_file = form.save(commit=False)
            print_file.print_time_seconds = total_seconds

            if print_file.actual_quantity is None:
                print_file.actual_quantity = 0

            print_file.save()
            instance.project.sync_status()

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
            project=original_file.project,
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
    data = model_to_dict(print_file, fields=['name', 'printer', 'plate', 'status', 'produced_quantity', 'actual_quantity'])
    data['print_time_seconds'] = print_file.print_time_seconds
    data['filaments_used'] = list(print_file.filament_usages.select_related('spool__filament').values('spool__filament_id', 'spool_id', 'grams_used'))
    return JsonResponse(data)

@login_required
def api_get_all_projects(request):
    projects = Project.objects.filter(status__in=['QUOTE', 'TODO', 'PRINTING', 'PRINTED']).order_by('name')
    data = [{'id': p.id, 'name': p.name} for p in projects]
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
        project = Project.objects.get(id=project_id)
        project.status = new_status
        project.save()
        return JsonResponse({'status': 'ok', 'message': f'Progetto {project.name} aggiornato'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@require_POST
@login_required
def reprint_project(request, project_id):
    original_project = get_object_or_404(Project.objects.prefetch_related('print_files__filament_usages__spool'), id=project_id)

    new_project = Project.objects.create(
        name=f"{original_project.name} (Ristampa)",
        category=original_project.category,
        priority=original_project.priority,
        quantity=original_project.quantity,
        notes=original_project.notes,
        status=Project.Status.TODO
    )

    for old_file in original_project.print_files.exclude(status='FAILED'):
        new_file = PrintFile.objects.create(
            project=new_project,
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

        project = get_object_or_404(Project, id=project_id)

        if field not in ['status', 'priority']:
            return JsonResponse({'status': 'error', 'message': 'Campo non valido.'}, status=400)

        setattr(project, field, value)
        project.save()

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
            return JsonResponse({'status': 'error', 'message': 'Nome del progetto e materiali sono obbligatori.'}, status=400)

        total_seconds = (int(data.get('hours', 0)) * 3600) + (int(data.get('minutes', 0)) * 60)
        if total_seconds <= 0:
            return JsonResponse({'status': 'error', 'message': 'Il tempo di stampa deve essere maggiore di zero.'}, status=400)

        new_project = Project.objects.create(
            name=data['name'],
            notes=f"Creato da preventivo in data {timezone.now().strftime('%d/%m/%Y')}",
            status=Project.Status.QUOTE
        )

        print_file = PrintFile.objects.create(
            project=new_project,
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
                        'message': f"Nessuna bobina disponibile per il filamento '{filament}'. Aggiungine una prima di creare il progetto."
                    }, status=400)

        return JsonResponse({
            'status': 'ok',
            'message': 'Progetto creato con successo!',
            'project_url': reverse('project_detail', args=[new_project.id])
        })

    except (json.JSONDecodeError, KeyError, TypeError) as e:
        return JsonResponse({'status': 'error', 'message': f'Dati non validi: {str(e)}'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'Errore del server: {str(e)}'}, status=500)

@require_POST
@transaction.atomic
@login_required
def reopen_project(request, pk):
    project = get_object_or_404(Project, pk=pk)

    # 1. Check stato progetto
    if project.status != Project.Status.DONE:
        return JsonResponse({'status': 'error', 'message': 'Il progetto non è completato.'})

    # 2. Recupera tutti gli stock item di questo progetto
    related_stock_items = StockItem.objects.filter(project=project)

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

            # Ripristina progetto
            project.status = Project.Status.TODO
            project.completed_at = None
            project.save()

        target_url = reverse('project_dashboard')
        return JsonResponse({'status': 'ok', 'redirect_url': target_url})

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})
