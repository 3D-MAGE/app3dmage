# in app_3dmage_management/tests.py

from django.test import TestCase
from .models import WorkOrder, PrintFile, Project, ProjectPart, StockItem

class WorkOrderModelTests(TestCase):

    def test_progress_percentage_no_files(self):
        """Verifica che la percentuale di avanzamento sia 0 se non ci sono file di stampa."""
        # 1. Preparazione: Crea un progetto senza file
        work_order = WorkOrder.objects.create(name="Progetto Vuoto")

        # 2. Azione: Accedi alla proprietà
        progress = work_order.progress_percentage

        # 3. Verifica: Il risultato deve essere 0
        self.assertEqual(progress, 0)

    def test_progress_percentage_half_done(self):
        """Verifica il calcolo della percentuale con metà dei file completati."""
        # 1. Preparazione: Crea un progetto e 4 file associati
        work_order = WorkOrder.objects.create(name="Progetto a Metà")
        PrintFile.objects.create(work_order=work_order, name="file1", status=PrintFile.Status.DONE)
        PrintFile.objects.create(work_order=work_order, name="file2", status=PrintFile.Status.DONE)
        PrintFile.objects.create(work_order=work_order, name="file3", status=PrintFile.Status.TODO)
        PrintFile.objects.create(work_order=work_order, name="file3_b", status=PrintFile.Status.TODO)
        PrintFile.objects.create(work_order=work_order, name="file4", status=PrintFile.Status.FAILED)

        # 2. Azione: Accedi alla proprietà
        progress = work_order.progress_percentage

        # 3. Verifica: 2 file su 4 (validi) sono 'DONE', quindi ci aspettiamo il 50%. I FALLITI sono esclusi.
        self.assertEqual(progress, 50)

    def test_progress_percentage_all_done(self):
        """Verifica che la percentuale sia 100 se tutti i file sono completati."""
        # 1. Preparazione
        work_order = WorkOrder.objects.create(name="Progetto Finito")
        PrintFile.objects.create(work_order=work_order, name="file1", status=PrintFile.Status.DONE)
        PrintFile.objects.create(work_order=work_order, name="file2", status=PrintFile.Status.DONE)

        # 2. Azione
        progress = work_order.progress_percentage

        # 3. Verifica
        self.assertEqual(progress, 100)


from .models import PaymentMethod, Expense, ExpenseCategory
from django.utils import timezone
from django.urls import reverse

class ExpenseAccountingTests(TestCase):
    def setUp(self):
        from django.contrib.auth.models import User
        self.user = User.objects.create_user(username='testuser', password='password')
        self.client.force_login(self.user)
        self.category = ExpenseCategory.objects.create(name="Materiali")
        self.payment_method = PaymentMethod.objects.create(name="Cassa", balance=100.00)


    def test_add_expense_deducts_balance(self):
        response = self.client.post(reverse('add_expense'), {
            'description': 'Spesa 1',
            'amount': '20.00',
            'category': self.category.id,
            'payment_method': self.payment_method.id,
            'expense_date': timezone.now().date().strftime('%Y-%m-%d'),
        })
        self.payment_method.refresh_from_db()
        self.assertEqual(float(self.payment_method.balance), 80.00)



    def test_edit_expense_adjusts_balance(self):
        expense = Expense.objects.create(
            description='Spesa 1',
            amount=20.00,
            category=self.category,
            payment_method=self.payment_method,
            expense_date=timezone.now().date()
        )
        self.payment_method.balance = 80.00
        self.payment_method.save()

        response = self.client.post(reverse('edit_expense', args=[expense.id]), {
            'description': 'Spesa 1 Modificata',
            'amount': '30.00',
            'category': self.category.id,
            'payment_method': self.payment_method.id,
            'expense_date': timezone.now().date().strftime('%Y-%m-%d'),
        })
        
        self.payment_method.refresh_from_db()
        self.assertEqual(float(self.payment_method.balance), 70.00)


class PrintFileCloningTests(TestCase):
    def setUp(self):
        from django.contrib.auth.models import User
        self.user = User.objects.create_user(username='testuser', password='password')
        self.client.force_login(self.user)
        self.project = Project.objects.create(name="Progetto Master Test")
        self.part = ProjectPart.objects.create(project=self.project, name="Parte Superiore", order=1)
        self.work_order = WorkOrder.objects.create(name="Ordine Test", project=self.project)
        self.print_file = PrintFile.objects.create(
            work_order=self.work_order,
            name="file_originale.gcode",
            project_part=self.part,
            produced_quantity=3
        )

    def test_clone_print_file_retains_part_and_quantity(self):
        import json
        response = self.client.post(
            reverse('clone_print_file'),
            data=json.dumps({'file_id': self.print_file.id, 'count': 1}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        
        # Verify that the cloned print file has the correct project_part and produced_quantity
        cloned_file = PrintFile.objects.filter(name__contains="file_originale").exclude(id=self.print_file.id).first()
        self.assertIsNotNone(cloned_file)
        self.assertEqual(cloned_file.project_part, self.part)
        self.assertEqual(cloned_file.produced_quantity, 3)


from .models import Note, Notification, Spool, Filament, Printer, MasterPrintFile
from datetime import timedelta

class NoteAndNotificationTests(TestCase):
    def setUp(self):
        from django.contrib.auth.models import User
        self.user = User.objects.create_user(username='admin', password='password')
        self.client.force_login(self.user)

    def test_quick_add_note(self):
        response = self.client.post(reverse('quick_add_note'), {
            'title': 'Comprare colla stick',
            'category': 'PURCHASE',
            'priority': 'HIGH'
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Note.objects.count(), 1)
        note = Note.objects.first()
        self.assertEqual(note.title, 'Comprare colla stick')
        self.assertEqual(note.category, 'PURCHASE')
        self.assertEqual(note.priority, 'HIGH')
        self.assertFalse(note.is_completed)

    def test_toggle_note(self):
        note = Note.objects.create(title='Pulire piatto stampante', category='MAINTENANCE')
        self.assertFalse(note.is_completed)
        self.assertIsNone(note.completed_at)

        response = self.client.post(reverse('toggle_note', args=[note.id]))
        self.assertEqual(response.status_code, 200)
        note.refresh_from_db()
        self.assertTrue(note.is_completed)
        self.assertIsNotNone(note.completed_at)

        # Toggle back
        response = self.client.post(reverse('toggle_note', args=[note.id]))
        self.assertEqual(response.status_code, 200)
        note.refresh_from_db()
        self.assertFalse(note.is_completed)
        self.assertIsNone(note.completed_at)

    def test_api_quick_notes(self):
        Note.objects.create(title='Nota attiva 1', is_completed=False)
        Note.objects.create(title='Nota attiva 2', is_completed=False)
        Note.objects.create(title='Nota completata', is_completed=True)

        response = self.client.get(reverse('api_quick_notes'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['count'], 2)
        self.assertEqual(len(data['notes']), 2)

    def test_smart_notifications_generation(self):
        # 1. Nota scaduta
        yesterday = timezone.now().date() - timedelta(days=1)
        Note.objects.create(title='Ordinare PLA SUNLU Giallo', due_date=yesterday, is_completed=False)

        # 2. Bobina con meno di 150g
        filament = Filament.objects.create(material='PLA', color_code='01', brand='Sunlu', color_name='Rosso', color_hex='#FF0000')
        Spool.objects.create(filament=filament, initial_weight_g=100, cost=20.00, is_active=True)


        # 3. Ordine in ritardo
        WorkOrder.objects.create(name='Ordine Scaduto', status='PRINTING', delivery_date=yesterday)


        # Chiamata API notifiche
        response = self.client.get(reverse('api_get_notifications'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertGreaterEqual(data['count'], 3)

        # Segna tutte come lette
        mark_res = self.client.post(reverse('api_mark_notifications_as_read'))
        self.assertEqual(mark_res.status_code, 200)
        self.assertEqual(Notification.objects.filter(is_read=False).count(), 0)

    def test_notes_dashboard_and_filters(self):
        Note.objects.create(title='Comprare colla', category='PURCHASE', is_completed=False)
        Note.objects.create(title='Manutenzione ugello', category='MAINTENANCE', is_completed=True)

        # GET dashboard standard
        res = self.client.get(reverse('notes_dashboard'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Comprare colla')

        # Filtro completate
        res = self.client.get(reverse('notes_dashboard') + '?status=completed')
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Manutenzione ugello')

        # Richiesta HTMX parziale
        res_htmx = self.client.get(reverse('notes_dashboard'), HTTP_HX_REQUEST='true')
        self.assertEqual(res_htmx.status_code, 200)
        self.assertTemplateUsed(res_htmx, 'app_3dmage_management/partials/notes_list.html')

    def test_note_edit_and_delete(self):
        note = Note.objects.create(title='Titolo Vecchio', category='GENERAL')
        
        # Details
        res = self.client.get(reverse('get_note_details', args=[note.id]))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['title'], 'Titolo Vecchio')

        # Edit
        edit_res = self.client.post(reverse('edit_note', args=[note.id]), {
            'title': 'Titolo Aggiornato',
            'category': 'GENERAL',
            'priority': 'URGENT',
        })
        self.assertEqual(edit_res.status_code, 200)
        note.refresh_from_db()
        self.assertEqual(note.title, 'Titolo Aggiornato')
        self.assertEqual(note.priority, 'URGENT')

        # Delete
        del_res = self.client.post(reverse('delete_note', args=[note.id]), HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(del_res.status_code, 200)
        self.assertEqual(Note.objects.count(), 0)

    def test_create_from_template_with_specific_gcode_variant(self):
        import json
        printer = Printer.objects.create(name='Bambu X1C', model='X1C')
        project = Project.objects.create(name='Halloween Reaper Project')

        part = ProjectPart.objects.create(project=project, name='Grim Reaper', order=1)

        # File 1: variante singola (1 pz)
        file_1 = MasterPrintFile.objects.create(
            name='grim_reaper_1pz.gcode',
            printer=printer,
            project=project,
            produced_quantity=1
        )
        file_1.project_parts.add(part)

        # File 2: variante multipla (4 pz)
        file_4 = MasterPrintFile.objects.create(
            name='grim_reaper_4pz.gcode',
            printer=printer,
            project=project,
            produced_quantity=4
        )
        file_4.project_parts.add(part)

        # Creazione ordine selezionando esplicitamente la variante da 4 pz per qty 4
        batch_payload = [{
            'quantity': 4,
            'printers': {str(part.id): str(printer.id)},
            'files': {str(part.id): str(file_4.id)}
        }]

        response = self.client.post(
            reverse('create_from_template', args=[project.id]),
            {
                'batch_data': json.dumps(batch_payload),
                'ignore_warnings': 'true',
            }
        )
        self.assertEqual(response.status_code, 302)

        # Verifica WorkOrder creato
        wo = WorkOrder.objects.filter(project=project).latest('created_at')
        self.assertEqual(wo.quantity, 4)
        
        # Dev'essere stato creato ESATTAMENTE 1 PrintFile (il file da 4 pz moltiplicatore ceil(4/4) = 1)
        # e NON devono esserci duplicati o file da 1 pz!
        print_files = PrintFile.objects.filter(work_order=wo)
        self.assertEqual(print_files.count(), 1)
        self.assertIn('grim_reaper_4pz', print_files.first().name)

    def test_notifications_dashboard_and_clear(self):
        Notification.objects.create(message='Notifica 1', level='INFO', is_read=False)
        Notification.objects.create(message='Notifica 2', level='WARNING', is_read=True)

        res = self.client.get(reverse('notifications_dashboard'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Notifica 1')

        res_read = self.client.get(reverse('notifications_dashboard') + '?status=read')
        self.assertEqual(res_read.status_code, 200)
        self.assertContains(res_read, 'Notifica 2')

        res_clear = self.client.post(reverse('clear_all_notifications'))
        self.assertEqual(res_clear.status_code, 302)
        self.assertEqual(Notification.objects.count(), 0)

    def test_sales_sort_by_quantity(self):
        StockItem.objects.create(name='Item A', quantity=2, status='SOLD', sold_at=timezone.now().date())
        StockItem.objects.create(name='Item B', quantity=10, status='SOLD', sold_at=timezone.now().date())

        res = self.client.get(reverse('sales_dashboard') + '?sort=quantity&order=asc')
        self.assertEqual(res.status_code, 200)
        items = list(res.context['sold_items'])
        self.assertEqual(items[0].quantity, 2)
        self.assertEqual(items[1].quantity, 10)

        res_desc = self.client.get(reverse('sales_dashboard') + '?sort=quantity&order=desc')
        self.assertEqual(res_desc.status_code, 200)
        items_desc = list(res_desc.context['sold_items'])
        self.assertEqual(items_desc[0].quantity, 10)
        self.assertEqual(items_desc[1].quantity, 2)

    def test_work_order_parts_completion_calculation(self):
        project = Project.objects.create(name='Scatola con Coperchio')
        part_base = ProjectPart.objects.create(project=project, name='Base', pieces_per_item=1)
        part_lid = ProjectPart.objects.create(project=project, name='Coperchio', pieces_per_item=1)
        part_feet = ProjectPart.objects.create(project=project, name='Piedini', pieces_per_item=4)

        wo = WorkOrder.objects.create(project=project, name='Scatola con Coperchio', quantity=2)

        file_base = PrintFile.objects.create(work_order=wo, project_part=part_base, name='Base File', produced_quantity=2, actual_quantity=2, status='DONE')
        file_lid = PrintFile.objects.create(work_order=wo, project_part=part_lid, name='Lid File', produced_quantity=2, actual_quantity=2, status='DONE')
        file_feet = PrintFile.objects.create(work_order=wo, project_part=part_feet, name='Feet File', produced_quantity=4, actual_quantity=4, status='DONE')

        # Con 2 basi, 2 coperchi, ma solo 4 piedini (ne servivano 8 per 2 oggetti):
        # Oggetti finiti completi = 4 // 4 = 1 oggetto finito! Non 2!
        self.assertEqual(wo.completed_items, 1)
        self.assertEqual(wo.total_objects_printed, 1)

        # Se stampiamo un altro piatto di 4 piedini (totale 8 piedini):
        PrintFile.objects.create(work_order=wo, project_part=part_feet, name='Feet File 2', produced_quantity=4, actual_quantity=4, status='DONE')
        self.assertEqual(wo.completed_items, 2)
        self.assertEqual(wo.total_objects_printed, 2)

    def test_print_file_status_prepare(self):
        wo = WorkOrder.objects.create(name='Test Prep', status=WorkOrder.Status.TODO)
        pf = PrintFile.objects.create(work_order=wo, name='Gcode Prep', status=PrintFile.Status.PREPARE)
        self.assertEqual(pf.status, 'PREPARE')
        self.assertEqual(pf.get_status_display(), 'Da Preparare')

        # Verifica che non sia considerato stampato o completabile
        wo.sync_status()
        self.assertEqual(wo.status, WorkOrder.Status.TODO)
        
        # In coda di stampa sono presi solo TODO e PRINTING
        active_in_queue = PrintFile.objects.filter(
            status__in=['TODO', 'PRINTING'],
            work_order__status__in=['TODO', 'PRINTING']
        )
        self.assertNotIn(pf, active_in_queue)

    def test_single_part_name_matches_project(self):
        from django.contrib.auth.models import User
        user = User.objects.create_user('testu', 'test@example.com', 'pass123')
        self.client.force_login(user)

        res = self.client.post('/library/add/', {
            'name': 'Vaso Geometrico',
            'initial_parts_count': 1,
            'output_names[]': ['Vaso Geometrico'],
            'output_quantities[]': [1]
        })
        self.assertEqual(res.status_code, 302)
        proj = Project.objects.get(name='Vaso Geometrico')
        parts = proj.parts.all()
        self.assertEqual(parts.count(), 1)
        self.assertEqual(parts.first().name, 'Vaso Geometrico')


class CustomIdProgressiveTests(TestCase):
    def setUp(self):
        from django.contrib.auth.models import User
        self.user = User.objects.create_user('testuser_customid', 'test@example.com', 'pass123')
        self.client.force_login(self.user)
        self.current_year_prefix = timezone.now().strftime('%y')

    def test_get_next_custom_id_basic(self):
        from .models import get_next_custom_id
        # Inizialmente deve essere YY001
        expected_first = f"{self.current_year_prefix}001"
        self.assertEqual(get_next_custom_id(), expected_first)

    def test_manual_stock_item_progressive(self):
        res1 = self.client.post(reverse('add_stock_item'), {
            'name': 'Oggetto Manuale 1',
            'quantity': 1,
            'material_cost': '5.00',
            'labor_cost': '2.00',
            'suggested_price': '15.00'
        })
        self.assertEqual(res1.status_code, 200)
        item1 = StockItem.objects.get(name='Oggetto Manuale 1')
        self.assertEqual(item1.custom_id, f"{self.current_year_prefix}001")

        res2 = self.client.post(reverse('add_stock_item'), {
            'name': 'Oggetto Manuale 2',
            'quantity': 2,
            'material_cost': '10.00',
            'labor_cost': '4.00',
            'suggested_price': '25.00'
        })
        self.assertEqual(res2.status_code, 200)
        item2 = StockItem.objects.get(name='Oggetto Manuale 2')
        self.assertEqual(item2.custom_id, f"{self.current_year_prefix}002")

    def test_complete_work_order_after_manual_stock_item(self):
        """
        Verifica che completando un ordine di lavoro DOPO aver aggiunto oggetti manuali,
        gli oggetti a magazzino dell'ordine prendano il progressivo successivo
        e NON ripartano dallo stesso ID degli oggetti inseriti a mano.
        """
        import json
        # 1. Aggiungi un oggetto manuale -> deve avere YY001
        self.client.post(reverse('add_stock_item'), {
            'name': 'Manuale 1',
            'quantity': 1,
            'material_cost': '5.00',
            'labor_cost': '2.00',
            'suggested_price': '15.00'
        })
        manual_item = StockItem.objects.get(name='Manuale 1')
        self.assertEqual(manual_item.custom_id, f"{self.current_year_prefix}001")

        # 2. Crea e completa un ordine di lavoro
        wo = WorkOrder.objects.create(name='Ordine Test 1', quantity=1)
        outputs_data = json.dumps([{'name': 'Prodotto Da Ordine', 'quantity': 1}])

        res = self.client.post(reverse('complete_project', args=[wo.id]), {
            'outputs_data': outputs_data,
            'labor_cost': '0.00'
        })
        self.assertEqual(res.status_code, 302)

        wo.refresh_from_db()
        self.assertEqual(wo.custom_id, f"{self.current_year_prefix}002")

        order_stock_item = StockItem.objects.get(work_order=wo)
        # Non deve essere YY001 (che appartiene al manuale), ma YY002!
        self.assertEqual(order_stock_item.custom_id, f"{self.current_year_prefix}002")

        # 3. Aggiungi un altro oggetto manuale -> deve avere YY003
        self.client.post(reverse('add_stock_item'), {
            'name': 'Manuale 2',
            'quantity': 1,
            'material_cost': '5.00',
            'labor_cost': '2.00',
            'suggested_price': '15.00'
        })
        manual_item2 = StockItem.objects.get(name='Manuale 2')
        self.assertEqual(manual_item2.custom_id, f"{self.current_year_prefix}003")

        # 4. Crea e completa un secondo ordine con due output
        wo2 = WorkOrder.objects.create(name='Ordine Test 2', quantity=1)
        outputs_data2 = json.dumps([
            {'name': 'Parte A', 'quantity': 1},
            {'name': 'Parte B', 'quantity': 1}
        ])
        res2 = self.client.post(reverse('complete_project', args=[wo2.id]), {
            'outputs_data': outputs_data2,
            'labor_cost': '0.00'
        })
        self.assertEqual(res2.status_code, 302)

        wo2.refresh_from_db()
        self.assertEqual(wo2.custom_id, f"{self.current_year_prefix}004")

        order_items = StockItem.objects.filter(work_order=wo2)
        self.assertEqual(order_items.count(), 2)
        for it in order_items:
            self.assertEqual(it.custom_id, f"{self.current_year_prefix}004")







