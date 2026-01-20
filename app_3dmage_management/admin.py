from django.contrib import admin
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
admin.site.register(WorkOrder)
admin.site.register(PrintFile)
admin.site.register(StockItem)
admin.site.register(PaymentMethod)
admin.site.register(Expense)
admin.site.register(ExpenseCategory)
admin.site.register(MaintenanceLog)
admin.site.register(GlobalSetting)
admin.site.register(Quote)
admin.site.register(Notification)
