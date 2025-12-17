from django.shortcuts import render
from django.db.models import Sum, Case, When, Value, DecimalField, F, Q, IntegerField, Prefetch
from django.db.models.functions import Coalesce
from django.contrib.auth.decorators import login_required
from decimal import Decimal

from ..models import Project, Category, Filament, FilamentUsage
from ..forms import ProjectForm, PrintFileForm, PrintFileEditForm

@login_required
def project_dashboard(request):
    # Determina la vista corrente (active o completed)
    view_mode = request.GET.get('view', 'active')
    # CALCOLO CONTATORI (Totale In Corso e Da Stampare)
    active_count = Project.objects.exclude(status='DONE').count()
    todo_count = Project.objects.filter(status='TODO').count()
    # Filtri per Progetti Attivi
    search_query = request.GET.get('q', '')
    status_filter = request.GET.get('status', '')
    category_filter = request.GET.get('category', '')

    # Filtri per Progetti Completati
    completed_search_query = request.GET.get('q_completed', '')
    completed_year_filter = request.GET.get('year_completed', '')
    completed_category_filter = request.GET.get('category_completed', '')
    completed_filament_filter = request.GET.get('filament_completed', '')


    # Flag per mantenere aperte le sezioni dei filtri
    active_filters_applied = bool(search_query or status_filter or category_filter)
    completed_filters_applied = bool(completed_search_query or completed_year_filter or completed_category_filter or completed_filament_filter)

    # Anni disponibili per il filtro dei progetti completati
    completed_project_years = Project.objects.filter(
        status='DONE', completed_at__isnull=False
    ).dates('completed_at', 'year', order='DESC')

    all_projects = Project.objects.select_related('category').all()

    # Inizializzo le liste vuote
    active_projects = []
    completed_projects = []


    # --- Gestione Progetti Attivi (Solo se view_mode è active) ---
    if view_mode == 'active':
        sort_active = request.GET.get('sort_active', 'name')
        order_active = request.GET.get('order_active', 'asc')
        order_prefix_active = '-' if order_active == 'desc' else ''

        active_projects_query = all_projects.exclude(status='DONE').with_annotations()

        if search_query:
            q_filter = Q(name__icontains=search_query) | Q(custom_id__icontains=search_query)
            if search_query.isdigit():
                q_filter |= Q(id=search_query)
            active_projects_query = active_projects_query.filter(q_filter)
        if status_filter:
            active_projects_query = active_projects_query.filter(status=status_filter)
        if category_filter:
            active_projects_query = active_projects_query.filter(category_id=category_filter)

        valid_sort_fields_active = ['name', 'priority', 'status', 'remaining_print_time_seconds', 'total_print_time_seconds', 'category__name']
        if sort_active not in valid_sort_fields_active:
            sort_active = 'name'
        active_projects = active_projects_query.order_by(f'{order_prefix_active}{sort_active}')

    # Variabili per il template (default vuoti per evitare errori)
    else:
        sort_active = 'name'
        order_active = 'asc'

    # --- Gestione Progetti Completati (Solo se view_mode è completed) ---
    if view_mode == 'completed':
        sort_completed = request.GET.get('sort_completed', 'completed_at')
        order_completed = request.GET.get('order_completed', 'desc')
        order_prefix_completed = '-' if order_completed == 'desc' else ''

        completed_projects_query = all_projects.filter(status='DONE').prefetch_related(
            Prefetch(
                'print_files__filament_usages',
                queryset=FilamentUsage.objects.select_related('spool__filament'),
                to_attr='detailed_filament_usages'
            )
        ).with_annotations().annotate(
            total_grams_used=Coalesce(Sum('print_files__filament_usages__grams_used'), Decimal('0.00'))
        )

        if completed_search_query:
            q_filter_completed = Q(name__icontains=completed_search_query) | Q(custom_id__icontains=completed_search_query)
            if completed_search_query.isdigit():
                q_filter_completed |= Q(id=completed_search_query)
            completed_projects_query = completed_projects_query.filter(q_filter_completed)

        if completed_year_filter and completed_year_filter.isdigit():
            completed_projects_query = completed_projects_query.filter(completed_at__year=int(completed_year_filter))
        if completed_category_filter:
            completed_projects_query = completed_projects_query.filter(category_id=completed_category_filter)
        if completed_filament_filter:
            completed_projects_query = completed_projects_query.filter(print_files__filament_usages__spool__filament_id=completed_filament_filter).distinct()

        valid_sort_fields_completed = ['name', 'completed_at', 'total_print_time_seconds', 'annotated_material_cost', 'category__name', 'total_grams_used']
        if sort_completed not in valid_sort_fields_completed:
            sort_completed = 'completed_at'
        completed_projects = completed_projects_query.order_by(f'{order_prefix_completed}{sort_completed}')

        for project in completed_projects:
            usages = {}
            for pf in project.print_files.all():
                for usage in getattr(pf, 'detailed_filament_usages', []):
                    filament = usage.spool.filament
                    if filament.id not in usages:
                        usages[filament.id] = {
                            'name': str(filament),
                            'color_hex': filament.color_hex,
                        }
            project.filament_summary_details = list(usages.values())

    else:
        sort_completed = 'completed_at'
        order_completed = 'desc'

    context = {
        'view_mode': view_mode, # Passiamo la modalità corrente al template
        'active_projects': active_projects,
        'completed_projects': completed_projects,
        'active_count': active_count,
        'todo_count': todo_count,
        'all_categories': Category.objects.all(),
        'all_filaments': Filament.objects.all().order_by('material', 'brand', 'color_name'),
        'all_statuses': Project.Status.choices,
        'project_form': ProjectForm(),
        'add_print_file_form': PrintFileForm(),
        'edit_print_file_form': PrintFileEditForm(),
        'page_title': 'Progetti',
        'current_view': 'table',
        'search_query': search_query,
        'status_filter': status_filter,
        'category_filter': category_filter,
        'active_filters_applied': active_filters_applied,
        'sort_active': sort_active,
        'order_active': order_active,
        'completed_search_query': completed_search_query,
        'completed_year_filter': completed_year_filter,
        'completed_category_filter': completed_category_filter,
        'completed_filament_filter': completed_filament_filter,
        'completed_filters_applied': completed_filters_applied,
        'completed_project_years': [d.year for d in completed_project_years],
        'sort_completed': sort_completed,
        'order_completed': order_completed,
    }
    return render(request, 'app_3dmage_management/dashboard.html', context)

@login_required
def project_kanban_board(request):
    kanban_columns = []
    statuses_to_show = [status for status in Project.Status.choices if status[0] != 'DONE']
    for status_id, status_name in statuses_to_show:
        projects_in_status = Project.objects.filter(status=status_id).prefetch_related(
            'print_files__printer',
            'print_files__plate',
            'print_files__filament_usages__spool__filament'
        )
        kanban_columns.append({'status_id': status_id, 'status_name': status_name, 'projects': projects_in_status})
    context = {'kanban_columns': kanban_columns, 'project_form': ProjectForm(), 'print_file_form': PrintFileForm(), 'page_title': 'Progetti', 'current_view': 'kanban'}
    return render(request, 'app_3dmage_management/kanban_board.html', context)
