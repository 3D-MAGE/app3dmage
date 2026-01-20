from django.urls import path, include
from . import views
from django.views.generic import TemplateView

urlpatterns = [
    path('accounts/', include('django.contrib.auth.urls')),

    # Progetti
    path('', views.project_dashboard, name='project_dashboard'),
    path('projects/kanban/', views.project_kanban_board, name='project_kanban_board'),
    path('project/add/', views.add_project, name='add_project'),
    path('project/<int:project_id>/', views.project_detail, name='project_detail'),
    path('project/<int:project_id>/edit/', views.edit_project, name='edit_project'),
    path('project/<int:project_id>/sync-master/', views.sync_work_order_to_master, name='sync_work_order_to_master'),
    path('project/<int:project_id>/promote-master/', views.promote_to_master, name='promote_to_master'),
    path('project/<int:project_id>/complete/', views.complete_project, name='complete_project'),
    path('project/<int:project_id>/reprint/', views.reprint_project, name='reprint_project'),
    path('project/<int:project_id>/delete/', views.delete_project, name='delete_project'),
    path('project/<int:project_id>/update_inline/', views.update_project_inline, name='update_project_inline'),
    path('project/<int:project_id>/notes/edit/', views.edit_work_order_notes, name='edit_work_order_notes'),
    path('project/<int:pk>/reopen/', views.reopen_project, name='reopen_project'),

    # Libreria Progetti (Master)
    path('library/', views.projects_library, name='projects_library'),
    path('library/add/', views.add_master_project, name='add_master_project'),
    path('library/<int:pk>/', views.project_master_detail, name='project_master_detail'),
    path('library/<int:pk>/edit/', views.edit_master_project, name='edit_master_project'),
    path('library/<int:pk>/delete/', views.delete_master_project, name='delete_master_project'),
    path('library/<int:pk>/create_order/', views.create_from_template, name='create_from_template'),
    path('library/<int:pk>/add_file/', views.add_master_print_file, name='add_master_print_file'),
    path('library/<int:pk>/outputs/manage/', views.manage_project_outputs, name='manage_project_outputs'),
    path('library/<int:pk>/notes/edit/', views.edit_master_notes, name='edit_master_notes'),
    path('library/<int:pk>/parts/manage/', views.manage_project_parts, name='manage_project_parts'),
    path('library/part/<int:part_id>/edit/', views.edit_project_part, name='edit_project_part'),
    path('library/part/<int:part_id>/delete/', views.delete_project_part, name='delete_project_part'),
    path('library/file/<int:file_id>/details/', views.get_master_print_file_details, name='get_master_print_file_details'),
    path('library/file/<int:file_id>/edit/', views.edit_master_print_file, name='edit_master_print_file'),
    path('library/file/<int:file_id>/delete/', views.delete_master_print_file, name='delete_master_print_file'),

    # API
    path('api/filaments/', views.api_get_all_filaments, name='api_get_all_filaments'),
    path('api/filament/<int:filament_id>/spools/', views.api_get_filament_spools, name='api_get_filament_spools'),
    path('api/projects/', views.api_get_all_projects, name='api_get_all_projects'),
    path('api/costs/', views.api_get_costs, name='api_get_costs'),
    path('api/notifications/', views.api_get_notifications, name='api_get_notifications'),
    path('api/notifications/mark_as_read/', views.api_mark_notifications_as_read, name='api_mark_notifications_as_read'),
    path('api/notifications/<int:notification_id>/delete/', views.api_delete_notification, name='api_delete_notification'),


    # File di Stampa
    path('printfile/add/', views.add_print_file, name='add_print_file'),
    path('printfile/<int:file_id>/details/', views.get_print_file_details, name='get_print_file_details'),
    path('printfile/<int:file_id>/edit/', views.edit_print_file, name='edit_print_file'),
    path('printfile/<int:file_id>/delete/', views.delete_print_file, name='delete_print_file'),
    path('printfile/<int:file_id>/requeue/', views.requeue_print_file, name='requeue_print_file'),
    path('printfile/<int:file_id>/set_status/', views.set_print_file_status, name='set_print_file_status'),
    path('printfile/clone/', views.clone_print_file, name='clone_print_file'),


    # Coda di Stampa
    path('printers/queue/', views.print_queue_board, name='print_queue_board'),

    # Filamenti
    path('filaments/', views.filament_dashboard, name='filament_dashboard'),
    path('spool/add/', views.add_spool, name='add_spool'),
    path('spool/<int:spool_id>/details/', views.get_spool_details, name='get_spool_details'),
    path('spool/<int:spool_id>/edit/', views.edit_spool, name='edit_spool'),
    path('filament/<int:filament_id>/details/', views.get_filament_details, name='get_filament_details'),
    path('filament/add/', views.add_filament, name='add_filament'),
    path('filament/<int:filament_id>/edit/', views.edit_filament, name='edit_filament'),
    path('filament/<int:filament_id>/delete/', views.delete_filament, name='delete_filament'),
    path('spool/<int:spool_id>/delete/', views.delete_spool, name='delete_spool'),
    path('spool/<int:spool_id>/toggle_status/', views.toggle_spool_status, name='toggle_spool_status'),

    # Magazzino
    path('inventory/', views.inventory_dashboard, name='inventory_dashboard'),
    path('stock_item/add/', views.add_stock_item, name='add_stock_item'),
    path('ajax/stock_item/<int:item_id>/details/', views.get_stock_item_details, name='get_stock_item_details'),
    path('ajax/stock_item/<int:item_id>/update/', views.update_stock_item, name='update_stock_item'),
    path('ajax/stock_item/<int:item_id>/delete/', views.delete_stock_item, name='delete_stock_item'),

    # EXPORT CSV
    path('export/stock-sales-csv/', views.export_stock_sales_csv, name='export_stock_sales_csv'),

    # Vendite
    path('sales/', views.sales_dashboard, name='sales_dashboard'),
    path('sales/<int:item_id>/details/', views.get_sale_details, name='get_sale_details'),
    path('sales/<int:item_id>/edit/', views.edit_sale, name='edit_sale'),
    path('sale/<int:stock_item_id>/reverse/', views.reverse_sale, name='reverse_sale'),

    # Contabilità
    path('accounting/', views.accounting_dashboard, name='accounting_dashboard'),
    path('expense/add/', views.add_expense, name='add_expense'),
    path('income/add/', views.add_manual_income, name='add_manual_income'),
    path('funds/transfer/', views.transfer_funds, name='transfer_funds'),
    path('payment_method/<int:method_id>/correct/', views.correct_balance, name='correct_balance'),
    path('expense/<int:expense_id>/details/', views.get_expense_details, name='get_expense_details'),
    path('expense/<int:expense_id>/edit/', views.edit_expense, name='edit_expense'),
    path('expense/<int:expense_id>/delete/', views.delete_expense, name='delete_expense'),
    path('sale/<int:stock_item_id>/reverse/', views.reverse_sale, name='reverse_sale'),


    # Preventivi
    path('quotes/save/', views.save_quote, name='save_quote'),
    path('quotes/<int:quote_id>/delete/', views.delete_quote, name='delete_quote'),
    path('quotes/<int:quote_id>/details/', views.get_quote_details, name='get_quote_details'),
    path('quotes/create_project/', views.create_project_from_quote, name='create_project_from_quote'),


    # Impostazioni
    path('settings/', views.settings_dashboard, name='settings_dashboard'),
    path('settings/printer/add/', views.add_printer, name='add_printer'),
    path('settings/printer/<int:pk>/details/', views.get_printer_details, name='get_printer_details'),
    path('settings/printer/<int:pk>/edit/', views.edit_printer, name='edit_printer'),
    path('settings/printer/<int:pk>/delete/', views.delete_printer, name='delete_printer'),
    path('settings/plate/add/', views.add_plate, name='add_plate'),
    path('settings/plate/<int:pk>/details/', views.get_plate_details, name='get_plate_details'),
    path('settings/plate/<int:pk>/edit/', views.edit_plate, name='edit_plate'),
    path('settings/plate/<int:pk>/delete/', views.delete_plate, name='delete_plate'),
    path('settings/category/add/', views.add_category, name='add_category'),
    path('settings/category/<int:pk>/details/', views.get_category_details, name='get_category_details'),
    path('settings/category/<int:pk>/edit/', views.edit_category, name='edit_category'),
    path('settings/category/<int:pk>/delete/', views.delete_category, name='delete_category'),
    path('settings/payment_method/add/', views.add_payment_method, name='add_payment_method'),
    path('settings/payment_method/<int:pk>/details/', views.get_payment_method_details, name='get_payment_method_details'),
    path('settings/payment_method/<int:pk>/edit/', views.edit_payment_method, name='edit_payment_method'),
    path('settings/payment_method/<int:pk>/delete/', views.delete_payment_method, name='delete_payment_method'),
    path('settings/expense_category/add/', views.add_expense_category, name='add_expense_category'),
    path('settings/expense_category/<int:pk>/details/', views.get_expense_category_details, name='get_expense_category_details'),
    path('settings/expense_category/<int:pk>/edit/', views.edit_expense_category, name='edit_expense_category'),
    path('settings/expense_category/<int:pk>/delete/', views.delete_expense_category, name='delete_expense_category'),
    path('settings/maintenance/add/', views.add_maintenance_log, name='add_maintenance_log'),

    path('settings/general/update/', views.update_general_settings, name='update_general_settings'),
    path('quotes/', views.quote_calculator, name='quote_calculator'),


    # Viste AJAX
    path('ajax/load-plates/', views.load_plates, name='ajax_load_plates'),
    path('ajax/update_project_status/', views.update_project_status, name='update_project_status'),
    path('ajax/update_print_queue/', views.update_print_queue, name='update_print_queue'),
    path('ajax/stock_item/<int:item_id>/details/', views.get_stock_item_details, name='get_stock_item_details'),
    path('ajax/stock_item/<int:item_id>/update/', views.update_stock_item, name='update_stock_item'),
    path('ajax/get_spools/', views.get_spools_for_filament, name='get_spools_for_filament'),

    # Sync & Locking
    path('ajax/check-updates/', views.check_updates, name='check_updates'),
    path('ajax/lock/<str:model_type>/<int:item_id>/', views.lock_item, name='lock_item'),
    path('ajax/unlock/<str:model_type>/<int:item_id>/', views.unlock_item, name='unlock_item'),

    # NUOVO URL PER IL SERVICE WORKER
    path('serviceworker.js', TemplateView.as_view(
        template_name="serviceworker.js",
        content_type='application/javascript'
    ), name='serviceworker'),


]
