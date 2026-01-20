from django.core.management.base import BaseCommand
from app_3dmage_management.models import WorkOrder, Project, MasterPrintFile, PrintFile
from django.db import transaction

class Command(BaseCommand):
    help = 'Migrate existing WorkOrder data to the new Project (Master) architecture'

    def handle(self, *args, **options):
        self.stdout.write('Starting migration...')
        
        with transaction.atomic():
            # 1. Create Master Projects from WorkOrders
            work_orders = WorkOrder.objects.all()
            for wo in work_orders:
                # Find or create a Master Project based on name and category
                master_project, created = Project.objects.get_or_create(
                    name=wo.name,
                    category=wo.category,
                    defaults={
                        'base_quantity': wo.quantity,
                        'notes': f"Migrato da Ordine {wo.custom_id or wo.id}",
                        'created_at': wo.created_at
                    }
                )
                
                if created:
                    self.stdout.write(f'Created Master Project: {master_project.name}')
                
                # Link WorkOrder to Master Project
                wo.project = master_project
                wo.save()
                
                # 2. Create Master Print Files from WorkOrder PrintFiles
                for pf in wo.print_files.all():
                    master_pf, pf_created = MasterPrintFile.objects.get_or_create(
                        project=master_project,
                        name=pf.name,
                        defaults={
                            'estimated_time_seconds': pf.print_time_seconds,
                            'suggested_printer': pf.printer,
                            'suggested_plate': pf.plate
                        }
                    )
                    
                    if pf_created:
                        self.stdout.write(f'  Created Master Print File: {master_pf.name}')
                    
                    # Link PrintFile to Master Print File
                    pf.master_print_file = master_pf
                    pf.save()
        
        self.stdout.write(self.style.SUCCESS('Migration completed successfully!'))
