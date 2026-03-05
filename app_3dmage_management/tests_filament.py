from django.test import TestCase
from .models import Filament, Spool, WorkOrder, PrintFile, FilamentUsage
from decimal import Decimal

class FilamentWeightTests(TestCase):
    def setUp(self):
        self.filament = Filament.objects.create(
            material='PLA', color_code='BLK', brand='Generic', color_hex='#000000'
        )
        self.spool1 = Spool.objects.create(
            filament=self.filament, initial_weight_g=1000, identifier='A', cost=20
        )
        self.spool2 = Spool.objects.create(
            filament=self.filament, initial_weight_g=1000, identifier='B', cost=20
        )
        self.wo = WorkOrder.objects.create(name="Test WO")

    def test_available_weight_calculation(self):
        """Verifica che available_weight sottragga correttamente i lavori in coda."""
        # Crea un lavoro completato (DONE) -> deve diminuire remaining_weight
        pf_done = PrintFile.objects.create(work_order=self.wo, name="Done Job", status='DONE')
        FilamentUsage.objects.create(print_file=pf_done, spool=self.spool1, grams_used=200)

        # Crea un lavoro in coda (TODO) -> deve diminuire available_weight ma non remaining_weight
        pf_todo = PrintFile.objects.create(work_order=self.wo, name="Todo Job", status='TODO')
        FilamentUsage.objects.create(print_file=pf_todo, spool=self.spool1, grams_used=300)

        self.assertEqual(self.spool1.remaining_weight, Decimal('800.00'))
        self.assertEqual(self.spool1.pending_weight, Decimal('300.00'))
        self.assertEqual(self.spool1.available_weight, Decimal('500.00'))

    def test_spool_sorting_emptiest_first(self):
        """Verifica che le bobine siano proposte partendo dalla più vuota adatta."""
        # Spool A: 1000g totali, 500g usati/impegnati -> 500g disponibili
        pf = PrintFile.objects.create(work_order=self.wo, name="Job 1", status='DONE')
        FilamentUsage.objects.create(print_file=pf, spool=self.spool1, grams_used=500)

        # Spool B: 1000g totali, 200g usati/impegnati -> 800g disponibili
        pf2 = PrintFile.objects.create(work_order=self.wo, name="Job 2", status='DONE')
        FilamentUsage.objects.create(print_file=pf2, spool=self.spool2, grams_used=200)

        # Se chiediamo le bobine per il filamento, spool1 (500g) deve venire prima di spool2 (800g)
        from .views.filaments import get_spools_for_filament
        from django.test import RequestFactory
        factory = RequestFactory()
        request = factory.get(f'/api/spools/?filament_id={self.filament.id}')
        
        # Simula login
        from django.contrib.auth.models import User
        user = User.objects.create_user(username='testuser')
        request.user = user

        import json
        response = get_spools_for_filament(request)
        data = json.loads(response.content)

        self.assertEqual(data[0]['id'], self.spool1.id)
        self.assertEqual(data[1]['id'], self.spool2.id)
