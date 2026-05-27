from django.contrib import admin, messages
from django.db import transaction, models
from .models import (
    Category, Printer, Plate, Filament, Spool, Project, MasterPrintFile, WorkOrder, PrintFile,
    StockItem, PaymentMethod, Expense, ExpenseCategory, MaintenanceLog, GlobalSetting, Quote, Notification
)

# Registra i modelli per renderli visibili nel pannello di amministrazione
admin.site.register(Category)
admin.site.register(Printer)
admin.site.register(Plate)
admin.site.register(Filament)
admin.site.register(Spool)
admin.site.register(Project)
admin.site.register(MasterPrintFile)
admin.site.register(PrintFile)
admin.site.register(StockItem)
admin.site.register(PaymentMethod)
admin.site.register(Expense)
admin.site.register(ExpenseCategory)
admin.site.register(MaintenanceLog)
admin.site.register(GlobalSetting)
admin.site.register(Quote)
admin.site.register(Notification)

@admin.register(WorkOrder)
class WorkOrderAdmin(admin.ModelAdmin):
    actions = ['merge_work_orders']
    list_display = ('id', 'custom_id', 'name', 'status', 'priority', 'quantity', 'created_at')
    list_filter = ('status', 'priority', 'category')
    search_fields = ('name', 'custom_id')

    @admin.action(description='Unisci ordini di lavoro selezionati')
    def merge_work_orders(self, request, queryset):
        if queryset.count() < 2:
            self.message_user(request, "Devi selezionare almeno due ordini per unirli.", messages.ERROR)
            return

        # Ordina per data di creazione per trovare il più vecchio come destinazione
        ordered_qs = queryset.order_by('created_at')
        destination_wo = ordered_qs.first()
        source_wos = ordered_qs[1:]

        try:
            with transaction.atomic():
                total_qty_added = 0
                notes_added = []
                
                for src_wo in source_wos:
                    total_qty_added += src_wo.quantity
                    
                    if src_wo.notes:
                        notes_added.append(f"[{src_wo.name}]: {src_wo.notes}")
                    
                    # Sposta i file di stampa
                    src_wo.print_files.update(work_order=destination_wo)
                    
                    # Sposta gli stock items associati
                    StockItem.objects.filter(work_order=src_wo).update(work_order=destination_wo)
                    
                    # Elimina l'ordine sorgente
                    src_wo.delete()

                # Aggiorna l'ordine destinatario
                destination_wo.quantity += total_qty_added
                if notes_added:
                    additional_notes = "\n\n--- Note Ordini Uniti ---\n" + "\n".join(notes_added)
                    destination_wo.notes = (destination_wo.notes or "") + additional_notes
                
                # Ricalcola la quantità prodotta dall'unione degli stock items
                destination_wo.produced_quantity = StockItem.objects.filter(work_order=destination_wo).aggregate(
                    total=models.Sum('quantity')
                )['total'] or 0
                
                destination_wo.sync_status()
                destination_wo.save()

            self.message_user(
                request, 
                f"Ordini uniti con successo in '{destination_wo.name}' (ID: {destination_wo.id}).", 
                messages.SUCCESS
            )
        except Exception as e:
            self.message_user(request, f"Errore durante l'unione: {str(e)}", messages.ERROR)
