from django import forms
from .models import Project, PrintFile, Category, Printer, Plate, Filament, Spool, StockItem, Expense, PaymentMethod, ExpenseCategory, MaintenanceLog, GlobalSetting
import datetime

class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ['name', 'category', 'priority', 'quantity', 'notes']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Es. Scatola Drone Ike'}),
            'category': forms.Select(attrs={'class': 'form-select', 'placeholder': 'Scegliere una categoria'}),
            'priority': forms.Select(attrs={'class': 'form-select'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
        labels = {
            'name': 'Nome Progetto',
            'category': 'Categoria',
            'priority': 'Priorità',
            'status': 'Status',
            'quantity': 'Quantità Oggetti ordine',
            'notes': 'Annotazioni',
        }

class PrintFileForm(forms.ModelForm):
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
        fields = ['name', 'project', 'plate', 'printer', 'produced_quantity', 'actual_quantity']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Inserire il nome del gcode'}),
            'project': forms.Select(attrs={'class': 'form-select'}),
            'plate': forms.Select(attrs={'class': 'form-select'}),
        }

class StockItemForm(forms.ModelForm):
    quantity_to_sell = forms.IntegerField(
        label="Quantità da vendere",
        min_value=1,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        required=False
    )
    sold_at = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        required=False,
        label="Data Vendita"
    )
    project_notes = forms.CharField(
        label="Annotazioni Progetto",
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
        fields = ['name', 'quantity', 'suggested_price', 'status', 'project_notes', 'sold_at', 'sale_price', 'payment_method', 'sold_to', 'notes']
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
            'sold_at': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'sale_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'sold_to': forms.TextInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }
        labels = { 'sold_at': 'Data Vendita', 'sale_price': 'Prezzo di Vendita (per unità)', 'payment_method': 'Metodo Pagamento', 'sold_to': 'Venduto a', 'notes': 'Note' }

class PrintFileEditForm(forms.ModelForm):
    print_time_hours = forms.IntegerField(label="Ore", min_value=0, required=False, widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ore'}))
    print_time_minutes = forms.IntegerField(label="Minuti", min_value=0, max_value=59, required=False, widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Min'}))
    class Meta:
        model = PrintFile
        fields = ['name', 'printer', 'plate', 'status', 'produced_quantity', 'actual_quantity']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'printer': forms.Select(attrs={'class': 'form-select'}),
            'plate': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'produced_quantity': forms.NumberInput(attrs={'class': 'form-control'}),
            'actual_quantity': forms.NumberInput(attrs={'class': 'form-control'}),
        }
        labels = { 'produced_quantity': 'Oggetti per Stampa', 'actual_quantity': 'Oggetti Stampati Effettivi' }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['actual_quantity'].required = False

class CompleteProjectForm(forms.Form):
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
            'filament': forms.Select(attrs={'class': 'form-select'}),
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
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
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
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
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
        fields = ['name', 'model', 'power_consumption']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'model': forms.TextInput(attrs={'class': 'form-control'}),
            'power_consumption': forms.NumberInput(attrs={'class': 'form-control'}),
        }
        labels = { 'name': 'Nome Stampante', 'model': 'Modello', 'power_consumption': 'Consumo (Watt)' }

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
    log_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}), label="Data Intervento")
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
