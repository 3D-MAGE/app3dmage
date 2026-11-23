import json
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST, require_GET
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Q
from django.forms.models import model_to_dict

from ..models import Note, Filament, RawMaterial, Printer, WorkOrder
from ..forms import NoteForm


@login_required
def notes_dashboard(request):
    search_query = request.GET.get('q', '').strip()
    category_filter = request.GET.get('category', '').strip()
    status_filter = request.GET.get('status', 'active').strip()  # active, completed, all
    priority_filter = request.GET.get('priority', '').strip()

    notes_qs = Note.objects.select_related('filament', 'raw_material', 'printer', 'work_order')

    if search_query:
        notes_qs = notes_qs.filter(
            Q(title__icontains=search_query) |
            Q(description__icontains=search_query)
        )

    if category_filter:
        notes_qs = notes_qs.filter(category=category_filter)

    if priority_filter:
        notes_qs = notes_qs.filter(priority=priority_filter)

    if status_filter == 'active':
        notes_qs = notes_qs.filter(is_completed=False)
    elif status_filter == 'completed':
        notes_qs = notes_qs.filter(is_completed=True)

    # Ordina: se attive, prima urgenti/scadute, poi per data creazione
    notes = notes_qs.order_by('is_completed', '-due_date', '-created_at')

    # Contatori globali
    all_notes = Note.objects.all()
    active_count = all_notes.filter(is_completed=False).count()
    completed_count = all_notes.filter(is_completed=True).count()
    today = timezone.now().date()
    overdue_count = all_notes.filter(is_completed=False, due_date__lt=today).count()

    context = {
        'notes': notes,
        'form': NoteForm(),
        'page_title': 'Note & Promemoria',
        'search_query': search_query,
        'category_filter': category_filter,
        'status_filter': status_filter,
        'priority_filter': priority_filter,
        'categories': Note.Category.choices,
        'priorities': Note.Priority.choices,
        'active_count': active_count,
        'completed_count': completed_count,
        'overdue_count': overdue_count,
        'today': today,
    }

    if request.headers.get('HX-Request'):
        return render(request, 'app_3dmage_management/partials/notes_list.html', context)

    return render(request, 'app_3dmage_management/notes.html', context)


@require_POST
@login_required
def add_note(request):
    form = NoteForm(request.POST)
    if form.is_valid():
        note = form.save()
        if request.headers.get('HX-Request') or request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'ok', 'id': note.id, 'title': note.title})
        return redirect('notes_dashboard')
    
    if request.headers.get('HX-Request') or request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'status': 'error', 'errors': form.errors.as_json()}, status=400)
    return redirect('notes_dashboard')


@require_POST
@login_required
def quick_add_note(request):
    title = request.POST.get('title', '').strip()
    category = request.POST.get('category', Note.Category.PURCHASE)
    priority = request.POST.get('priority', Note.Priority.MEDIUM)
    due_date = request.POST.get('due_date', '').strip() or None

    if not title:
        return JsonResponse({'status': 'error', 'message': 'Il titolo è obbligatorio.'}, status=400)

    note = Note.objects.create(
        title=title,
        category=category,
        priority=priority,
        due_date=due_date
    )
    return JsonResponse({'status': 'ok', 'id': note.id, 'title': note.title})


@login_required
def get_note_details(request, note_id):
    note = get_object_or_404(Note, id=note_id)
    data = {
        'id': note.id,
        'title': note.title,
        'description': note.description,
        'category': note.category,
        'priority': note.priority,
        'due_date': note.due_date.strftime('%Y-%m-%d') if note.due_date else '',
        'filament': note.filament_id,
        'raw_material': note.raw_material_id,
        'printer': note.printer_id,
        'work_order': note.work_order_id,
        'is_completed': note.is_completed,
    }
    return JsonResponse(data)


@require_POST
@login_required
def edit_note(request, note_id):
    note = get_object_or_404(Note, id=note_id)
    form = NoteForm(request.POST, instance=note)
    if form.is_valid():
        form.save()
        return JsonResponse({'status': 'ok'})
    return JsonResponse({'status': 'error', 'errors': form.errors.as_json()}, status=400)


@require_POST
@login_required
def toggle_note(request, note_id):
    note = get_object_or_404(Note, id=note_id)
    note.is_completed = not note.is_completed
    if note.is_completed:
        note.completed_at = timezone.now()
    else:
        note.completed_at = None
    note.save()
    return JsonResponse({
        'status': 'ok',
        'is_completed': note.is_completed,
        'id': note.id
    })


@require_POST
@login_required
def delete_note(request, note_id):
    note = get_object_or_404(Note, id=note_id)
    note.delete()
    if request.headers.get('HX-Request') or request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'status': 'ok'})
    return redirect('notes_dashboard')


@login_required
@require_GET
def api_quick_notes(request):
    """Restituisce le note attive non completate per il pannello rapido offcanvas."""
    active_notes = Note.objects.filter(is_completed=False).order_by('-due_date', '-created_at')[:15]
    today = timezone.now().date()
    data = []
    for n in active_notes:
        data.append({
            'id': n.id,
            'title': n.title,
            'category': n.get_category_display(),
            'category_code': n.category,
            'priority': n.priority,
            'due_date': n.due_date.strftime('%d/%m/%Y') if n.due_date else None,
            'is_overdue': n.due_date < today if n.due_date else False,
            'is_due_today': n.due_date == today if n.due_date else False,
        })
    return JsonResponse({'notes': data, 'count': Note.objects.filter(is_completed=False).count()})
