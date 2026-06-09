# in app_3dmage_management/tests.py

from django.test import TestCase
from .models import WorkOrder, PrintFile, Project, ProjectPart

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


