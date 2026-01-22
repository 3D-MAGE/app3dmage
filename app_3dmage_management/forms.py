from django import forms
from .models import WorkOrder, PrintFile, Project, MasterPrintFile, Category, Printer, Plate, Filament, Spool, StockItem, Expense, PaymentMethod, ExpenseCategory, MaintenanceLog, GlobalSetting, ProjectPart
import datetime

class WorkOrderForm(forms.ModelForm):
    class Meta:
        model = WorkOrder
        fields = ['name', 'category', 'priority', 'quantity', 'notes']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Es. Scatola Drone Ike'}),
            'category': forms.Select(attrs={'class': 'form-select', 'placeholder': 'Scegliere una categoria'}),
            'priority': forms.Select(attrs={'class': 'form-select'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
        labels = {
            'name': 'Nome Ordine di Lavoro',
            'category': 'Categoria',
            'priority': 'Priorità',
            'status': 'Status',
            'quantity': 'N° Set da produrre (Master Unit)',
            'notes': 'Annotazioni',
        }

class PrintFileForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        work_order = kwargs.pop('work_order', None)
        super().__init__(*args, **kwargs)
        # Attempt to find work_order if not explicitly passed
        if not work_order:
            if self.instance and hasattr(self.instance, 'work_order'):
                work_order = self.instance.work_order
            elif 'initial' in kwargs and 'work_order' in kwargs['initial']:
                work_order = kwargs['initial']['work_order']
        
        if work_order and hasattr(work_order, 'project') and work_order.project:
            self.fields['project_part'].queryset = ProjectPart.objects.filter(project=work_order.project)
        elif work_order:
            self.fields['project_part'].queryset = ProjectPart.objects.none()
            
    print_time_hours = forms.IntegerField(label="Ore", min_value=0, required=False, widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ore', 'value': 0}))
    print_time_minutes = forms.IntegerField(label="Minuti", min_value=0, max_value=59, required=False, widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Min', 'value': 0}))
    printer = forms.ModelChoiceField(
        queryset=Printer.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select'}),
        empty_label="Seleziona stampante",
        label="Stampante Usata"
    )
    produced_quantity = forms.IntegerField(
        label="Oggetti per Stampa",
        min_value=1,
        initial=1,
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    actual_quantity = forms.IntegerField(
        label="Oggetti Stampati Effettivi",
        min_value=0,
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    class Meta:
        model = PrintFile
        fields = ['name', 'work_order', 'plate', 'printer', 'project_part', 'produced_quantity', 'actual_quantity']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Inserire il nome del gcode'}),
            'work_order': forms.Select(attrs={'class': 'form-select'}),
            'plate': forms.Select(attrs={'class': 'form-select'}),
            'project_part': forms.Select(attrs={'class': 'form-select'}),
        }

class StockItemForm(forms.ModelForm):
    quantity_to_sell = forms.IntegerField(
        label="Quantità da vendere",
        min_value=1,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        required=False
    )
    sold_at = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}, format='%Y-%m-%d'),
        required=False,
        label="Data Vendita",
        initial=datetime.date.today
    )
    work_order_notes = forms.CharField(
        label="Annotazioni Ordine",
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        required=False
    )
    payment_method = forms.ModelChoiceField(
        queryset=PaymentMethod.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select'}),
        required=False,
        label="Metodo Pagamento",
        empty_label="--- DA PAGARE ---"
    )

    class Meta:
        model = StockItem
        fields = ['name', 'quantity', 'suggested_price', 'status', 'work_order_notes', 'sold_at', 'sale_price', 'payment_method', 'sold_to', 'notes']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'suggested_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'sale_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'sold_to': forms.TextInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }
        labels = {
            'suggested_price': 'Prezzo Vendita Previsto'
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filtra lo stato per rimuovere 'SOLD' (Venduto) dalle opzioni di modifica manuale.
        # Lo manteniamo se l'oggetto è già venduto o se stiamo sottomettendo la vendita (status='SOLD' nei dati).
        if 'status' in self.fields:
            data = kwargs.get('data') or (args[0] if args else None)
            submitted_status = data.get('status') if data else None
            current_status = getattr(self.instance, 'status', None)

            if current_status != 'SOLD' and submitted_status != 'SOLD':
                self.fields['status'].choices = [
                    (c[0], c[1]) for c in self.fields['status'].choices if c[0] != 'SOLD'
                ]

class ManualStockItemForm(forms.ModelForm):
    class Meta:
        model = StockItem
        fields = ['name', 'quantity', 'suggested_price', 'material_cost']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'suggested_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'material_cost': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }
        labels = { 'name': "Nome Oggetto", 'quantity': "Quantità", 'suggested_price': 'Prezzo Vendita Previsto', 'material_cost': 'Costo Materiali Totale' }

class SaleEditForm(forms.ModelForm):
    payment_method = forms.ModelChoiceField(
        queryset=PaymentMethod.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select'}),
        required=False,
        label="Metodo Pagamento",
        empty_label="--- DA PAGARE ---"
    )

    class Meta:
        model = StockItem
        fields = ['sold_at', 'sale_price', 'payment_method', 'sold_to', 'notes']
        widgets = {
            'sold_at': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}, format='%Y-%m-%d'),
            'sale_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'sold_to': forms.TextInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.initial['sold_at'] = datetime.date.today()
        labels = { 'sold_at': 'Data Vendita', 'sale_price': 'Prezzo di Vendita (per unità)', 'payment_method': 'Metodo Pagamento', 'sold_to': 'Venduto a', 'notes': 'Note' }

class PrintFileEditForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        work_order = kwargs.pop('work_order', None)
        super().__init__(*args, **kwargs)
        if not work_order:
            if self.instance and hasattr(self.instance, 'work_order'):
                work_order = self.instance.work_order
        
        if work_order and hasattr(work_order, 'project') and work_order.project:
            self.fields['project_part'].queryset = ProjectPart.objects.filter(project=work_order.project)
        elif work_order:
            self.fields['project_part'].queryset = ProjectPart.objects.none()
            
        self.fields['actual_quantity'].required = False

    print_time_hours = forms.IntegerField(label="Ore", min_value=0, required=False, widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ore'}))
    print_time_minutes = forms.IntegerField(label="Minuti", min_value=0, max_value=59, required=False, widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Min'}))
    class Meta:
        model = PrintFile
        fields = ['name', 'printer', 'plate', 'project_part', 'status', 'produced_quantity', 'actual_quantity']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'printer': forms.Select(attrs={'class': 'form-select'}),
            'plate': forms.Select(attrs={'class': 'form-select'}),
            'project_part': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'produced_quantity': forms.NumberInput(attrs={'class': 'form-control'}),
            'actual_quantity': forms.NumberInput(attrs={'class': 'form-control'}),
        }
        labels = { 'produced_quantity': 'Oggetti per Stampa', 'actual_quantity': 'Oggetti Stampati Effettivi', 'project_part': 'Parte Progetto' }

class CompleteWorkOrderForm(forms.Form):
    stock_item_name = forms.CharField(label="Nome Oggetto per Magazzino", widget=forms.TextInput(attrs={'class': 'form-control'}))
    stock_item_quantity = forms.IntegerField(label="Quantità da Mettere a Magazzino", min_value=1, widget=forms.NumberInput(attrs={'class': 'form-control'}))
    labor_cost = forms.DecimalField(
        label="Costo Manodopera (€)",
        min_value=0,
        initial=0.00,
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Es. 5.50'})
    )

class FilamentForm(forms.ModelForm):
    class Meta:
        model = Filament
        fields = ['material', 'color_code', 'brand', 'color_hex', 'color_name', 'nozzle_temp', 'bed_temp', 'volumetric_speed', 'notes']
        widgets = {
            'color_hex': forms.TextInput(attrs={'type': 'color', 'class': 'form-control form-control-color'}),
            'color_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Es. Nero, Rosso Fuoco, Bianco Gesso'}),
            'material': forms.Select(attrs={'class': 'form-select'}),
            'color_code': forms.TextInput(attrs={'class': 'form-control'}),
            'brand': forms.TextInput(attrs={'class': 'form-control'}),
            'nozzle_temp': forms.NumberInput(attrs={'class': 'form-control'}),
            'bed_temp': forms.NumberInput(attrs={'class': 'form-control'}),
            'volumetric_speed': forms.NumberInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

class SpoolForm(forms.ModelForm):
    payment_method = forms.ModelChoiceField(
        queryset=PaymentMethod.objects.all(),
        label="Pagato con",
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    purchase_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        label="Data Acquisto",
        initial=datetime.date.today
        )

    class Meta:
        model = Spool
        fields = ['filament', 'initial_weight_g', 'cost', 'purchase_date', 'purchase_link', 'payment_method']
        widgets = {
            # MODIFICA: Rimosso il widget per 'filament' per gestirlo nel template
            'filament': forms.Select(),
            'initial_weight_g': forms.NumberInput(attrs={'class': 'form-control'}),
            'cost': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'purchase_link': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://...'}),
        }

class SpoolEditForm(forms.ModelForm):
    correction = forms.DecimalField(
        label="Correzione Grammi (+/-)",
        required=False,
        help_text="Aggiungi o sottrai grammi. Es: -50 per togliere, 25 per aggiungere.",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Es. -50 o 25'})
    )

    class Meta:
        model = Spool
        fields = ['cost', 'purchase_link', 'is_active', 'correction']
        widgets = {
            'cost': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'purchase_link': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://...'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class ExpenseForm(forms.ModelForm):
    # MODIFIED: Set the default date to today
    expense_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}, format='%Y-%m-%d'),
        label="Data Spesa",
        initial=datetime.date.today
    )
    class Meta:
        model = Expense
        fields = ['description', 'amount', 'category', 'expense_date', 'payment_method', 'notes']
        widgets = {
            'description': forms.TextInput(attrs={'class': 'form-control'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'payment_method': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

class ManualIncomeForm(forms.ModelForm):
    sold_at = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}, format='%Y-%m-%d'),
        label="Data Entrata",
        initial=datetime.date.today
    )
    class Meta:
        model = StockItem
        fields = ['name', 'sale_price', 'payment_method', 'sold_at', 'notes']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'sale_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'payment_method': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }
        labels = {
            'name': 'Descrizione Entrata',
            'sale_price': 'Importo (€)',
            'payment_method': 'Accreditato su',
            'notes': 'Note'
        }

class TransferForm(forms.Form):
    amount = forms.DecimalField(label="Importo", widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}))
    source = forms.ModelChoiceField(queryset=PaymentMethod.objects.all(), label="Da Conto", widget=forms.Select(attrs={'class': 'form-select'}))
    destination = forms.ModelChoiceField(queryset=PaymentMethod.objects.all(), label="A Conto", widget=forms.Select(attrs={'class': 'form-select'}))
    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("source") == cleaned_data.get("destination"):
            raise forms.ValidationError("Il conto di origine e destinazione non possono essere gli stessi.")
        return cleaned_data

class CorrectBalanceForm(forms.Form):
    new_balance = forms.DecimalField(label="Nuovo Saldo Corretto", widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}))

class PrinterForm(forms.ModelForm):
    class Meta:
        model = Printer
        fields = ['name', 'model', 'power_consumption', 'tag']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'model': forms.TextInput(attrs={'class': 'form-control'}),
            'power_consumption': forms.NumberInput(attrs={'class': 'form-control'}),
            'tag': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Es. MK, A1'}),
        }
        labels = { 
            'name': 'Nome Stampante', 
            'model': 'Modello', 
            'power_consumption': 'Consumo (Watt)',
            'tag': 'Tag Breve (per filtri)'
        }

class PlateForm(forms.ModelForm):
    class Meta:
        model = Plate
        fields = ['printer', 'name']
        widgets = {
            'printer': forms.Select(attrs={'class': 'form-select'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
        }
        labels = { 'printer': 'Stampante Associata', 'name': 'Nome Piatto' }

class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name']
        widgets = { 'name': forms.TextInput(attrs={'class': 'form-control'}) }
        labels = { 'name': 'Nome Categoria' }

class PaymentMethodForm(forms.ModelForm):
    class Meta:
        model = PaymentMethod
        fields = ['name', 'balance']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'balance': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }
        labels = { 'name': 'Nome Metodo', 'balance': 'Saldo Iniziale/Corrente' }

class ExpenseCategoryForm(forms.ModelForm):
    class Meta:
        model = ExpenseCategory
        fields = ['name']
        widgets = { 'name': forms.TextInput(attrs={'class': 'form-control'}) }
        labels = { 'name': 'Nome Categoria Spesa' }

class MaintenanceLogForm(forms.ModelForm):
    log_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}, format='%Y-%m-%d'),
        label="Data Intervento",
        initial=datetime.date.today
    )
    class Meta:
        model = MaintenanceLog
        fields = ['printer', 'log_date', 'description', 'notes', 'cost']
        widgets = {
            'printer': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.TextInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'cost': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }

class GeneralSettingsForm(forms.Form):
    electricity_cost = forms.DecimalField(
        label="Costo Elettricità (€/kWh)",
        decimal_places=4,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.0001'})
    )
    wear_tear_coefficient = forms.DecimalField(
        label="Coefficiente Usura Orario (€/ora)",
        decimal_places=4,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.0001'})
    )

class MasterProjectForm(forms.ModelForm):
    initial_parts_count = forms.IntegerField(
        label="Numero di Parti Iniziali",
        min_value=1,
        initial=1,
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 1})
    )
    class Meta:
        model = Project
        fields = ['name', 'category', 'preview_image', 'suggested_selling_price', 'dimensions', 'notes']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Es. Scatola Drone'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'preview_image': forms.FileInput(attrs={'class': 'form-control'}),
            'suggested_selling_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Es. 25.00'}),
            'dimensions': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Es. 10x10x5 cm'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }
        labels = {
            'name': 'Nome Progetto Master',
            'category': 'Categoria',
            'preview_image': 'Immagine Anteprima',
            'suggested_selling_price': 'Prezzo Vendita Suggerito (€)',
            'dimensions': 'Dimensioni (L x P x H)',
            'notes': 'Annotazioni Master',
        }

class MasterPrintFileForm(forms.ModelForm):
    estimated_time_days = forms.IntegerField(label="Giorni", min_value=0, required=False, widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'G', 'value': 0}))
    estimated_time_hours = forms.IntegerField(label="Ore", min_value=0, required=False, widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ore', 'value': 0}))
    estimated_time_minutes = forms.IntegerField(label="Minuti", min_value=0, max_value=59, required=False, widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Min', 'value': 0}))
    
    class Meta:
        model = MasterPrintFile
        fields = ['name', 'printer', 'plate', 'project_parts']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Es. Scocca Inferiore'}),
            'printer': forms.Select(attrs={'class': 'form-select'}),
            'plate': forms.Select(attrs={'class': 'form-select'}),
            'project_parts': forms.SelectMultiple(attrs={'class': 'form-select'}),
        }
        labels = {
            'name': 'Nome File Template',
            'printer': 'Stampante',
            'plate': 'Piatto',
            'project_parts': 'Parti Progetto',
        }
