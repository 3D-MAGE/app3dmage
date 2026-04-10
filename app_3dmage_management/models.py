import datetime
from django.db import models
from django.db.models import Sum, F, Case, When, IntegerField, Value
from django.utils import timezone
from django.conf import settings
from decimal import Decimal
from .managers import WorkOrderManager

def bump_global_version():
    """Update a global version timestamp to signal HTMX clients to refresh."""
    from decimal import Decimal
    try:
        # Use a safe string conversion for Decimal
        # Use a safe string conversion for Decimal, modulo 100000 to fit in max_digits=10
        ts = str(timezone.now().timestamp() % 100000)
        new_val = Decimal(ts)
        
        # Robust update: Try to update directly first (efficient)
        updated = GlobalSetting.objects.filter(key='app_last_updated').update(value=new_val)
        
        if updated == 0:
            # If not found, create it
            GlobalSetting.objects.create(key='app_last_updated', value=new_val)
            
    except Exception:
        # If update/create failed (e.g. corruption causing issues even on update), 
        # delete and recreate.
        try:
            GlobalSetting.objects.filter(key='app_last_updated').delete()
            ts = str(timezone.now().timestamp() % 100000)
            new_val = Decimal(ts)
            GlobalSetting.objects.create(key='app_last_updated', value=new_val)
        except Exception:
            pass # Last resort, prevent crash


# Modello per le Categorie dei progetti
class Category(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="Nome Categoria")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Categoria"
        verbose_name_plural = "Categorie"

# Modello per le Stampanti
class Printer(models.Model):
    name = models.CharField(max_length=100, verbose_name="Nome Stampante")
    model = models.CharField(max_length=100, blank=True, verbose_name="Modello")
    power_consumption = models.PositiveIntegerField(
        default=150,
        help_text="Consumo medio in Watt della stampante durante la stampa."
    )
    # NUOVO CAMPO: Data dell'ultimo reset del contatore di manutenzione
    last_maintenance_reset = models.DateTimeField(default=timezone.now, verbose_name="Ultimo Reset Manutenzione")
    tag = models.CharField(max_length=10, blank=True, null=True, verbose_name="Tag Stampante (es. MK, A1)")


    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Stampante"
        verbose_name_plural = "Stampanti"

# Modello per i Piatti di stampa, collegati a una stampante
class Plate(models.Model):
    name = models.CharField(max_length=100, verbose_name="Nome Piatto")
    printer = models.ForeignKey(Printer, on_delete=models.CASCADE, related_name="plates", verbose_name="Stampante")

    def __str__(self):
        return f"{self.printer.name} - {self.name}"

    class Meta:
        verbose_name = "Piatto"
        verbose_name_plural = "Piatti"

# Modello per i Tipi di Filamento

class FilamentUsage(models.Model):
    print_file = models.ForeignKey('PrintFile', on_delete=models.CASCADE, related_name='filament_usages')
    spool = models.ForeignKey('Spool', on_delete=models.CASCADE, related_name='usages')

    grams_used = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        default=0.00,
        verbose_name="Grammi Usati"
    )

    def __str__(self):
        return f"{self.grams_used}g di {self.spool.filament} per {self.print_file.name}"


class Filament(models.Model):
    MATERIAL_CHOICES = [
        ('PLA', 'PLA'), ('PETG', 'PETG'), ('ABS', 'ABS'), ('TPU', 'TPU'), ('ASA', 'ASA'),
    ]

    material = models.CharField(max_length=10, choices=MATERIAL_CHOICES, verbose_name="Materiale")
    color_code = models.CharField(max_length=3, verbose_name="Codice Colore")
    brand = models.CharField(max_length=50, verbose_name="Marca")
    color_hex = models.CharField(max_length=7, default="#FFFFFF", verbose_name="Codice Colore HEX")
    color_name = models.CharField(max_length=100, blank=True, verbose_name="Nome Colore")
    nozzle_temp = models.PositiveIntegerField(default=215, verbose_name="Temperatura Ugello (°C)")
    bed_temp = models.PositiveIntegerField(default=60, verbose_name="Temperatura Piatto (°C)")
    volumetric_speed = models.PositiveIntegerField(default=15, verbose_name="Velocità Volumetrica (mm³/s)")
    notes = models.TextField(blank=True, verbose_name="Note")

    @property
    def total_initial_weight(self):
        return self.spools.aggregate(total=models.Sum('initial_weight_g'))['total'] or 0

    @property
    def total_used_weight(self):
        return FilamentUsage.objects.filter(
            spool__filament=self,
            print_file__status__in=['DONE', 'FAILED']
        ).aggregate(total=models.Sum('grams_used'))['total'] or 0

    @property
    def remaining_weight(self):
        return self.total_initial_weight - self.total_used_weight

    def has_active_spools(self):
        return self.spools.filter(is_active=True).exists()

    def find_alternative(self):
        """Trova un filamento alternativo con lo stesso materiale e codice colore, ma marca diversa, che abbia bobine attive."""
        return Filament.objects.filter(
            material=self.material,
            color_code=self.color_code
        ).exclude(id=self.id).filter(
            spools__is_active=True
        ).distinct().first()

    def __str__(self):
        return f"{self.material}-{self.color_code}-{self.brand}"

    class Meta:
        verbose_name = "Filamento"
        verbose_name_plural = "Filamenti"
        ordering = ['material', 'brand', 'color_code']


class Spool(models.Model):
    filament = models.ForeignKey(Filament, on_delete=models.CASCADE, related_name="spools", verbose_name="Filamento")
    identifier = models.CharField(max_length=2, blank=True, verbose_name="Identificatore")
    initial_weight_g = models.PositiveIntegerField(default=1000, verbose_name="Peso Iniziale (g)")
    weight_adjustment = models.DecimalField(max_digits=7, decimal_places=2, default=0.00, verbose_name="Aggiustamento Manuale (g)")
    cost = models.DecimalField(max_digits=8, decimal_places=2, verbose_name="Costo (€)")
    purchase_date = models.DateField(default=timezone.now, verbose_name="Data Acquisto")
    purchase_link = models.URLField(max_length=512, blank=True, null=True, verbose_name="Link Acquisto")
    is_active = models.BooleanField(default=True, verbose_name="Attiva")

    @property
    def remaining_weight(self):
        """Peso (g) basato sulle stampe completate (DONE/FAILED)."""
        used = self.usages.filter(print_file__status__in=['DONE', 'FAILED']).aggregate(total=Sum('grams_used'))['total'] or Decimal('0.00')
        return (Decimal(self.initial_weight_g) + Decimal(str(self.weight_adjustment))) - used

    @property
    def pending_weight(self):
        """Peso (g) impegnato per stampe in coda (TODO/PRINTING)."""
        return self.usages.filter(print_file__status__in=['TODO', 'PRINTING']).aggregate(total=Sum('grams_used'))['total'] or Decimal('0.00')

    @property
    def available_weight(self):
        """Peso (g) realmente disponibile (rimanente - impegnato)."""
        return max(Decimal('0.00'), self.remaining_weight - self.pending_weight)

    # MODIFICA: Logica di assegnazione automatica lettera (A, B, C...)
    def save(self, *args, **kwargs):
        if not self.identifier:
            # Conta quante bobine esistono già per questo filamento
            existing_count = Spool.objects.filter(filament=self.filament).count()
            # Genera la lettera: 0->A, 1->B, 2->C, etc. (65 è il codice ASCII per 'A')
            # Nota: questo sistema semplice funziona fino alla Z.
            self.identifier = chr(65 + existing_count)
        super().save(*args, **kwargs)

    def __str__(self):
        weight_kg = self.initial_weight_g / 1000
        weight_str = f"{int(weight_kg) if weight_kg.is_integer() else weight_kg}Kg"

        # Usa l'identificatore salvato, oppure "A" di default se per qualche motivo è vuoto
        id_display = self.identifier if self.identifier else "A"

        # NUOVO FORMATO: Colore - Data Identificatore - Peso
        # Es: Nero - 05/25 B - 1Kg
        return f"{self.filament.color_name} - {self.purchase_date.strftime('%m/%y')} {id_display} - {weight_str}"

    class Meta:
        verbose_name = "Bobina"
        verbose_name_plural = "Bobine"
        ordering = ['purchase_date', 'identifier']

# Modello per i Progetti Master (Ricettario)
class Project(models.Model):
    name = models.CharField(max_length=200, verbose_name="Nome Progetto")
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Categoria")
    base_quantity = models.PositiveIntegerField(default=1, verbose_name="Quantità Base")
    preview_image = models.ImageField(upload_to='project_previews/', null=True, blank=True, verbose_name="Immagine Anteprima")
    suggested_selling_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Prezzo di Vendita Suggerito")
    dimensions = models.CharField(max_length=100, null=True, blank=True, verbose_name="Dimensioni")
    notes = models.TextField(blank=True, verbose_name="Annotazioni Master")
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True) # Per "Ultima modifica"
    
    def create_work_order(self, quantity=1, priority='MEDIUM', status='TODO', notes=''):
        """
        Clona questo progetto Master in un nuovo Ordine di Lavoro (WorkOrder),
        creando ricorsivamente tutti i PrintFile e i FilamentUsage associati.
        """
        import math
        # I modelli sono definiti nello stesso file e saranno disponibili a runtime.
        # Definiamo i riferimenti locali se necessario o usiamoli direttamente.
        
        # 1. Crea il WorkOrder
        new_wo = WorkOrder.objects.create(
            name=self.name,
            category=self.category,
            quantity=quantity,
            project=self,
            priority=priority,
            status=status,
            notes=notes or self.notes
        )
        
        # 2. Crea i PrintFile basandosi sui file Master
        for mpf in self.master_print_files.all():
            # Otteniamo le parti a cui appartiene il file (o una lista con None se non ne ha)
            file_parts = list(mpf.project_parts.all())
            if not file_parts:
                file_parts = [None]
                
            for part in file_parts:
                # Calcolo Moltiplicatore per il file (quanti set di pezzi servono)
                # Per semplicità nel re-print rapido assumiamo 1 set se non diversamente specificato
                file_multiplier = 1 # In create_from_template era math.ceil(batch_qty / mpf.produced_quantity)
                
                for i in range(file_multiplier):
                    multiplier_suffix = f" ({i+1})" if file_multiplier > 1 else ""
                    pf_name = f"{mpf.name}{multiplier_suffix}"
                    
                    pf = PrintFile.objects.create(
                        work_order=new_wo,
                        master_print_file=mpf,
                        project_part=part,
                        name=pf_name,
                        print_time_seconds=mpf.estimated_time_seconds,
                        printer_id=mpf.printer_id,
                        plate=mpf.plate,
                        produced_quantity=mpf.produced_quantity,
                        status=PrintFile.Status.TODO
                    )
                    
                    # 3. Crea FilamentUsage
                    for master_usage in mpf.filament_usages.all():
                        target_filament = master_usage.filament
                        
                        # Selezione automatica bobina
                        spools = Spool.objects.filter(filament=target_filament, is_active=True)
                        suitable_spools = sorted(
                            [s for s in spools if s.available_weight >= master_usage.grams_used],
                            key=lambda x: x.available_weight
                        )
                        
                        spool = None
                        if suitable_spools:
                            spool = suitable_spools[0]
                        else:
                            spool = sorted(list(spools), key=lambda x: x.available_weight, reverse=True)[0] if spools.exists() else None
                        
                        if spool:
                            FilamentUsage.objects.create(
                                print_file=pf,
                                spool=spool,
                                grams_used=master_usage.grams_used
                            )
        return new_wo

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Progetto (Master)"
        verbose_name_plural = "Progetti (Master)"

# Modello per gli Output previsti di un progetto
class ProjectOutput(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="outputs", verbose_name="Progetto Master")
    name = models.CharField(max_length=200, verbose_name="Nome Output")
    quantity = models.PositiveIntegerField(default=1, verbose_name="Quantità Base")
    # Facoltativo: un codice o suffisso per l'ID personalizzato
    code_suffix = models.CharField(max_length=5, blank=True, null=True, verbose_name="Suffisso Codice")

    def __str__(self):
        return f"{self.project.name} - {self.name} (x{self.quantity})"

    class Meta:
        verbose_name = "Output Progetto"
        verbose_name_plural = "Output Progetti"

# Modello per le Parti di un Progetto Master
class ProjectPart(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="parts", verbose_name="Progetto Master")
    name = models.CharField(max_length=100, verbose_name="Nome Parte")
    order = models.PositiveIntegerField(default=1, verbose_name="Ordine")

    def __str__(self):
        return f"{self.project.name} - {self.name}"

    class Meta:
        verbose_name = "Parte Progetto"
        verbose_name_plural = "Parti Progetto"
        ordering = ['order']


# Modello per i File di Stampa Master (Template)
class MasterPrintFile(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="master_print_files")
    project_parts = models.ManyToManyField(ProjectPart, related_name="master_print_files", blank=True, verbose_name="Parti")
    name = models.CharField(max_length=200, verbose_name="Nome File")
    estimated_time_seconds = models.PositiveIntegerField(default=0)
    printer = models.ForeignKey(Printer, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Stampante")
    plate = models.ForeignKey(Plate, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Piatto")
    produced_quantity = models.PositiveIntegerField(default=1, verbose_name="Oggetti per Stampa")
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Quando un file master viene salvato, aggiorniamo la data del progetto padre
        self.project.save()

    def delete(self, *args, **kwargs):
        project = self.project
        super().delete(*args, **kwargs)
        # Quando un file master viene eliminato, aggiorniamo la data del progetto padre
        project.save()

    @property
    def total_grams(self):
        return self.filament_usages.aggregate(total=Sum('grams_used'))['total'] or 0.0

    def __str__(self):
        return f"{self.project.name} - {self.name}"

# Modello per l'associazione Filamenti -> File Master
class MasterFilamentUsage(models.Model):
    master_print_file = models.ForeignKey(MasterPrintFile, on_delete=models.CASCADE, related_name='filament_usages')
    filament = models.ForeignKey(Filament, on_delete=models.CASCADE, verbose_name="Filamento Consigliato")
    grams_used = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        default=0.00,
        verbose_name="Grammi Stimati"
    )

    def __str__(self):
        return f"{self.master_print_file.name} - {self.filament} ({self.grams_used}g)"

# Modello per i Progetti (ora Ordini di Lavoro)
class WorkOrder(models.Model):
    class Priority(models.TextChoices):
        URGENT = 'URGENT', 'Urgente'
        HIGH = 'HIGH', 'Alta'
        MEDIUM = 'MEDIUM', 'Media'
        LOW = 'LOW', 'Bassa'

    class Status(models.TextChoices):
        QUOTE = 'QUOTE', 'Preventivo'
        TODO = 'TODO', 'Da stampare'
        PRINTING = 'PRINTING', 'In stampa'
        PRINTED = 'PRINTED', 'Stampato'
        DONE = 'DONE', 'Completato'

    objects = WorkOrderManager()

    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True, related_name="work_orders", verbose_name="Progetto Master")
    custom_id = models.CharField(max_length=10, null=True, blank=True, unique=True, verbose_name="ID Personalizzato")
    name = models.CharField(max_length=200, verbose_name="Nome Progetto")
    created_at = models.DateTimeField(default=timezone.now, verbose_name="Creato il")
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.MEDIUM, verbose_name="Priorità")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.QUOTE, verbose_name="Status")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="Data Completamento")
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Categoria")
    quantity = models.PositiveIntegerField(default=1, verbose_name="Quantità oggetti ordine")
    delivery_date = models.DateField(null=True, blank=True, verbose_name="Data Consegna Prevista")
    notes = models.TextField(blank=True, verbose_name="Annotazioni")
    actual_quantity = models.PositiveIntegerField(default=0)
    produced_quantity = models.PositiveIntegerField(default=0)
    
    # Locking for multi-user sync
    locked_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='locked_projects')
    locked_at = models.DateTimeField(null=True, blank=True)

    def is_locked(self, user=None):
        if not self.locked_by or not self.locked_at:
            return False
        # Lock expires after 5 minutes
        if timezone.now() > self.locked_at + datetime.timedelta(minutes=5):
            return False
        if user and self.locked_by == user:
            return False
        return True

    @property
    def total_print_time(self):
        total_seconds = self.print_files.aggregate(total=Sum('print_time_seconds'))['total'] or 0
        return str(datetime.timedelta(seconds=total_seconds))

    @property
    def remaining_print_time(self):
        total_seconds = self.print_files.filter(status='TODO').aggregate(total=Sum('print_time_seconds'))['total'] or 0
        return str(datetime.timedelta(seconds=total_seconds))

    @property
    def progress(self):
        total_valid_files = self.print_files.exclude(status='FAILED').count()
        if total_valid_files == 0:
            return "0/0"
        done_files = self.print_files.filter(status='DONE').count()
        return f"{done_files}/{total_valid_files}"

    @property
    def progress_percentage(self):
        total_valid_files = self.print_files.exclude(status='FAILED').count()
        if total_valid_files == 0:
            return 0
        done_files = self.print_files.filter(status='DONE').count()
        return (done_files * 100) / total_valid_files

    @property
    def total_filament_grams(self):
        return FilamentUsage.objects.filter(print_file__work_order=self).aggregate(total=models.Sum('grams_used'))['total'] or 0

    @property
    def filament_summary(self):
        filament_names = Filament.objects.filter(
            spools__usages__print_file__project=self
        ).distinct().values_list('material', 'color_code', 'brand')
        return ", ".join([f"{mat}-{col}-{brand}" for mat, col, brand in filament_names])

    @property
    def total_material_cost(self):
        total_cost = Decimal('0.00')
        for print_file in self.print_files.all():
            for usage in print_file.filament_usages.all():
                if usage.spool and usage.spool.initial_weight_g > 0:
                    cost_per_gram = usage.spool.cost / Decimal(usage.spool.initial_weight_g)
                    total_cost += Decimal(usage.grams_used) * cost_per_gram
        return total_cost.quantize(Decimal('0.01'))

    # NUOVA PROPRIETA' per il costo totale comprensivo
    @property
    def full_total_cost(self):
        total_cost = Decimal('0.00')
        for print_file in self.print_files.all():
            # La property total_cost del PrintFile include già materiale, elettricità e usura
            total_cost += print_file.total_cost
        return total_cost

    @property
    def total_objects_printed(self):
        return self.print_files.aggregate(total=Sum('actual_quantity'))['total'] or 0

    @property
    def total_expected_pieces(self):
        """Calcola il numero totale di pezzi attesi per tutti gli output definiti nel progetto."""
        if not self.project:
            return self.quantity
        total_pieces_per_set = self.project.outputs.aggregate(Sum('quantity'))['quantity__sum'] or 1
        return self.quantity * total_pieces_per_set

    @property
    def remaining_objects(self):
        """Pezzi totali attesi meno pezzi effettivamente aggiunti a magazzino."""
        return max(0, self.total_expected_pieces - self.produced_quantity)

    @property
    def remaining_to_stock(self):
        return max(0, self.quantity - self.produced_quantity)

    @property
    def delivery_status_color(self):
        if not self.delivery_date:
            return "secondary"
        delta = (self.delivery_date - datetime.date.today()).days
        if delta < 0:
            return "danger border border-white"
        elif delta <= 1:
            return "danger"
        elif delta <= 3:
            return "warning text-dark"
        else:
            return "success"

    def get_remaining_for_output(self, output):
        """Calcola quanti pezzi di un determinato output devono ancora essere versati a magazzino."""
        if not self.project:
            return 0
        from django.db.models import Sum
        # In un ordine, 'quantity' è il numero di SET.
        num_sets = self.quantity
        total_expected = int(num_sets * output.quantity)
        
        from .models import StockItem
        produced = StockItem.objects.filter(work_order=self, name=output.name).aggregate(Sum('quantity'))['quantity__sum'] or 0
        return max(0, total_expected - produced)

    def get_printed_ready_to_stock_for_output(self, output):
        """
        Calcola quanti pezzi di un determinato output sono stati stampati (DONE) 
        ma non ancora versati a magazzino.
        """
        if not self.project:
            return 0
            
        from django.db.models import Sum
        # 1. Quanti pezzi totali sono stati stampati (DONE)
        total_printed = self.print_files.filter(status='DONE').aggregate(Sum('actual_quantity'))['actual_quantity__sum'] or 0
        
        # 2. Distribuzione proporzionale per questo output
        total_pieces_per_set = self.project.outputs.all().aggregate(Sum('quantity'))['quantity__sum'] or 1
        # Se l'output contribuisce per N pezzi su un totale di M nel set:
        proportion = Decimal(output.quantity) / Decimal(total_pieces_per_set)
        
        # Pezzi stampati teorici per questo output
        printed_for_output = int(Decimal(total_printed) * proportion)
        
        # 3. Sottraiamo quelli già versati a magazzino
        from .models import StockItem
        already_stocked = StockItem.objects.filter(work_order=self, name=output.name).aggregate(Sum('quantity'))['quantity__sum'] or 0
        
        return max(0, printed_for_output - already_stocked)

    def sync_status(self):
        """
        Sincronizza lo stato del progetto in base ai suoi print_files.
        - Se almeno uno è PRINTING -> Progetto = PRINTING.
        - Se tutti sono DONE/FAILED (e nessuno PRINTING/TODO) -> Progetto = PRINTED.
        - Se ce ne sono in TODO (e nessuno in PRINTING) -> Progetto = TODO.
        """
        if self.status in [self.Status.DONE, self.Status.QUOTE]:
            return

        # Recupera tutti i file del progetto
        files = self.print_files.all()
        if not files.exists():
            return

        if files.filter(status='PRINTING').exists():
            new_status = self.Status.PRINTING
        elif not files.filter(status__in=['TODO', 'PRINTING']).exists():
            # Se tutti i file sono DONE o FAILED
            new_status = self.Status.PRINTED
        else:
            # Ci sono dei TODO, ma niente in PRINTING
            new_status = self.Status.TODO
        
        if self.status != new_status:
            self.status = new_status
            self.save()

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        bump_global_version()

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Ordine di Lavoro"
        verbose_name_plural = "Ordini di Lavoro"
        ordering = ['-created_at']

# Modello per i singoli File di Stampa (.gcode)
class PrintFile(models.Model):
    class Status(models.TextChoices):
        TODO = 'TODO', 'Da Stampare'
        PRINTING = 'PRINTING', 'In Stampa'
        DONE = 'DONE', 'Stampato'
        FAILED = 'FAILED', 'Fallito'

    name = models.CharField(max_length=200, verbose_name="Nome G-Code")
    work_order = models.ForeignKey(WorkOrder, on_delete=models.CASCADE, related_name="print_files", verbose_name="Ordine di Lavoro")
    master_print_file = models.ForeignKey(MasterPrintFile, on_delete=models.SET_NULL, null=True, blank=True, related_name="instances", verbose_name="Template Originale")
    project_part = models.ForeignKey(ProjectPart, on_delete=models.SET_NULL, null=True, blank=True, related_name="print_files", verbose_name="Parte")
    created_at = models.DateTimeField(default=timezone.now, verbose_name="Data Creazione")
    printer = models.ForeignKey(Printer, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Stampante Usata", related_name="print_files")
    plate = models.ForeignKey(Plate, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Piatto Usato")
    print_time_seconds = models.PositiveIntegerField(default=0, verbose_name="Tempo di Stampa (secondi)")
    spools = models.ManyToManyField('Spool', through='FilamentUsage', related_name="print_files_usage")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.TODO, verbose_name="Status Stampa")
    queue_position = models.PositiveIntegerField(default=0, verbose_name="Posizione in Coda")
    produced_quantity = models.PositiveIntegerField(default=1, verbose_name="Oggetti per Stampa")
    actual_quantity = models.PositiveIntegerField(default=0, verbose_name="Oggetti Stampati Effettivi")

    @property
    def print_time_formatted(self):
        return str(datetime.timedelta(seconds=self.print_time_seconds))

    @property
    def material_cost(self):
        total_cost = Decimal('0.00')
        for usage in self.filament_usages.all():
            if usage.spool and usage.spool.initial_weight_g > 0:
                cost_per_gram = usage.spool.cost / Decimal(usage.spool.initial_weight_g)
                total_cost += Decimal(usage.grams_used) * cost_per_gram
        return total_cost

    @property
    def electricity_cost(self):
        if not self.print_time_seconds or not self.printer or self.printer.power_consumption <= 0:
            return Decimal('0.00')

        cost_setting, _ = GlobalSetting.objects.get_or_create(
            key='electricity_cost_kwh',
            defaults={'value': Decimal('0.25')}
        )
        cost_kwh = cost_setting.value

        hours = Decimal(self.print_time_seconds) / Decimal(3600)
        kwh_used = (Decimal(self.printer.power_consumption) * hours) / Decimal(1000)
        return (kwh_used * cost_kwh)

    @property
    def wear_tear_cost(self):
        if not self.print_time_seconds:
            return Decimal('0.00')

        wear_setting, _ = GlobalSetting.objects.get_or_create(
            key='wear_tear_coefficient',
            defaults={'value': Decimal('0.10')}
        )
        wear_cost_per_hour = wear_setting.value

        hours = Decimal(self.print_time_seconds) / Decimal(3600)
        return (hours * wear_cost_per_hour)

    @property
    def total_cost(self):
        return self.material_cost + self.electricity_cost + self.wear_tear_cost

    @property
    def total_grams_used(self):
        return self.filament_usages.aggregate(total=Sum('grams_used'))['total'] or 0

    @property
    def filament_types_summary(self):
        filaments = Filament.objects.filter(spools__usages__print_file=self).distinct()
        if not filaments:
            return "N/D"
        return ", ".join([str(f) for f in filaments])

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "File di Stampa"
        verbose_name_plural = "File di Stampa"
        ordering = ['queue_position']

# Modello per i Metodi di Pagamento
class PaymentMethod(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="Nome Metodo")
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Saldo Attuale")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Metodo di Pagamento"
        verbose_name_plural = "Metodi di Pagamento"

class StockItemQuerySet(models.QuerySet):
    def with_net_values(self):
        """
        Annotates net revenue and net profit at the DB level.
        Logic:
        - Satispay Business: 1% fee (0.99 multiplier)
        - SumUp / Sum Up: 1.95% fee (0.9805 multiplier)
        - Others: 0 fee (1.0 multiplier)
        """
        from django.db.models import FloatField, DecimalField
        return self.annotate(
            # Coalesce to avoid null results in math
            safe_sale_price=Case(When(sale_price__isnull=True, then=Value(0)), default=F('sale_price'), output_field=DecimalField(max_digits=10, decimal_places=2)),
            annotated_total_gross=F('safe_sale_price') * F('quantity'),
            annotated_production_cost=F('material_cost') + F('labor_cost'),
            multiplier=Case(
                When(payment_method__name__icontains='satispay business', then=Value(0.99)),
                When(payment_method__name__icontains='sumup', then=Value(0.9805)),
                When(payment_method__name__icontains='sum up', then=Value(0.9805)),
                default=Value(1.0),
                output_field=FloatField()
            )
        ).annotate(
            annotated_net_revenue=Case(
                When(payment_method__isnull=True, then=F('annotated_total_gross')),
                default=F('annotated_total_gross') * F('multiplier'),
                output_field=DecimalField(max_digits=10, decimal_places=2)
            )
        ).annotate(
            annotated_net_profit=F('annotated_net_revenue') - F('annotated_production_cost')
        )

# Modello per gli Oggetti a Magazzino
class SaleType(models.TextChoices):
    COMMERCIAL = 'COMMERCIAL', 'Commerciale'
    PERSONAL = 'PERSONAL', 'Personale'

class StockItem(models.Model):
    class Status(models.TextChoices):
        POST_PROD = 'POST_PROD', 'Post-Produzione'
        IN_STOCK = 'IN_STOCK', 'A Magazzino'
        CONSIGNMENT = 'CONSIGNMENT', 'Conto Vendita'
        SOLD = 'SOLD', 'Venduto'

    work_order = models.ForeignKey(WorkOrder, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Ordine di Lavoro Originale")
    custom_id = models.CharField(max_length=10, null=True, blank=True, verbose_name="ID Personalizzato")
    name = models.CharField(max_length=200, verbose_name="Nome Oggetto")
    quantity = models.PositiveIntegerField(default=1, verbose_name="Quantità")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.POST_PROD, verbose_name="Stato")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Aggiunto il")
    material_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Costo Materiali")
    labor_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Costo Manodopera")
    suggested_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Prezzo di Vendita Previsto")
    sold_at = models.DateField(null=True, blank=True, verbose_name="Data Vendita")
    sale_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Prezzo di Vendita")
    payment_method = models.ForeignKey(PaymentMethod, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Metodo di Pagamento")
    sold_to = models.CharField(max_length=100, blank=True, verbose_name="Venduto a (o rimborsato da)")
    notes = models.TextField(blank=True, verbose_name="Note sulla vendita")

    # Locking for multi-user sync
    locked_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='locked_stock')
    locked_at = models.DateTimeField(null=True, blank=True)

    def is_locked(self, user=None):
        if not self.locked_by or not self.locked_at:
            return False
        if timezone.now() > self.locked_at + datetime.timedelta(minutes=5):
            return False
        if user and self.locked_by == user:
            return False
        return True

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        bump_global_version()

    objects = StockItemQuerySet.as_manager()

    @property
    def total_cost(self):
        """Material cost + Labor cost."""
        return (self.material_cost or Decimal('0.00')) + (self.labor_cost or Decimal('0.00'))

    def get_net_revenue(self):
        """
        Calculates the revenue after commissions based on payment method.
        Treats current sale_price as GROSS.
        Returns total revenue (price * qty) minus fees.
        """
        total_gross = (self.sale_price or Decimal('0.00')) * self.quantity
        if not self.payment_method:
            return total_gross
        
        method_name = self.payment_method.name.lower()
        if 'satispay business' in method_name:
            return (total_gross * Decimal('0.99')).quantize(Decimal('0.01')) # 1% fee
        elif 'sumup' in method_name or 'sum up' in method_name:
            return (total_gross * Decimal('0.9805')).quantize(Decimal('0.01')) # 1.95% fee
        
        return total_gross

    def get_net_profit(self):
        """Net revenue minus total production cost."""
        return self.get_net_revenue() - self.total_cost

    @property
    def cost_per_item(self):
        if self.quantity > 0:
            return (self.material_cost / self.quantity).quantize(Decimal('0.01'))
        return Decimal('0.00')

    def __str__(self):
        return f"{self.name} (x{self.quantity}) - {self.get_status_display()}"

    class Meta:
        verbose_name = "Oggetto a Magazzino"
        verbose_name_plural = "Oggetti a Magazzino"
        ordering = ['-created_at']


class ExpenseCategory(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="Nome Categoria Spesa")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Categoria Spesa"
        verbose_name_plural = "Categorie Spesa"

class Expense(models.Model):
    description = models.CharField(max_length=255, verbose_name="Descrizione")
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Importo (€)")
    category = models.ForeignKey(ExpenseCategory, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Categoria")
    expense_date = models.DateField(default=timezone.now, verbose_name="Data Spesa")
    payment_method = models.ForeignKey('PaymentMethod', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Pagato con")
    notes = models.TextField(blank=True, verbose_name="Note")

    def __str__(self):
        return f"{self.description} - {self.amount}€"

    class Meta:
        verbose_name = "Spesa"
        verbose_name_plural = "Spese"
        ordering = ['-expense_date']

class MaintenanceLog(models.Model):
    printer = models.ForeignKey(Printer, on_delete=models.CASCADE, related_name='maintenance_logs', verbose_name="Stampante")
    log_date = models.DateField(default=timezone.now, verbose_name="Data Intervento")
    description = models.CharField(max_length=255, verbose_name="Descrizione Intervento")
    notes = models.TextField(blank=True, verbose_name="Note Aggiuntive")
    cost = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Costo Ricambi (€)")

    def __str__(self):
        return f"Manutenzione su {self.printer.name} il {self.log_date}"

    class Meta:
        verbose_name = "Log Manutenzione"
        verbose_name_plural = "Log Manutenzioni"
        ordering = ['-log_date']

class GlobalSetting(models.Model):
    key = models.CharField(max_length=100, unique=True, verbose_name="Chiave Impostazione")
    value = models.DecimalField(max_digits=10, decimal_places=4, verbose_name="Valore")

    def __str__(self):
        return self.key

class Quote(models.Model):
    name = models.CharField(max_length=255, verbose_name="Nome Preventivo")
    total_cost = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Costo Totale")
    details = models.JSONField(verbose_name="Dettagli Preventivo")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Creato il")

    def __str__(self):
        return f"{self.name} - {self.total_cost}€"

    class Meta:
        ordering = ['-created_at']

class Notification(models.Model):
    class NotificationLevel(models.TextChoices):
        INFO = 'INFO', 'Info'
        SUCCESS = 'SUCCESS', 'Successo'
        WARNING = 'WARNING', 'Attenzione'
        DANGER = 'DANGER', 'Pericolo'

    message = models.CharField(max_length=255, verbose_name="Messaggio")
    level = models.CharField(max_length=10, choices=NotificationLevel.choices, default=NotificationLevel.INFO)
    is_read = models.BooleanField(default=False, verbose_name="Letta")
    created_at = models.DateTimeField(auto_now_add=True)
    related_url = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return self.message

    class Meta:
        ordering = ['-created_at']
