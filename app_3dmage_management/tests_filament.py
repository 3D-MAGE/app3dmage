from django.test import TestCase
from .models import Filament, Spool, WorkOrder, PrintFile, FilamentUsage, Project
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


class FilamentFilterAndSearchTests(TestCase):
    def setUp(self):
        from django.contrib.auth.models import User
        self.user = User.objects.create_user(username='filtertester', password='secret')
        self.client.force_login(self.user)

        self.pla_red = Filament.objects.create(
            material='PLA', color_code='100', brand='AMZ', color_name='Rosso Fuoco', color_hex='#FF0000'
        )
        self.pla_black = Filament.objects.create(
            material='PLA', color_code='000', brand='SUN', color_name='Nero', color_hex='#000000'
        )
        self.petg_red = Filament.objects.create(
            material='PETG', color_code='105', brand='SUN-M', color_name='Rosso Traslucido', color_hex='#CC0000'
        )
        self.petg_exhausted_blue = Filament.objects.create(
            material='PETG', color_code='400', brand='ESU', color_name='Blu Cobalto', color_hex='#0000FF'
        )

        Spool.objects.create(filament=self.pla_red, initial_weight_g=1000, cost=20, is_active=True)
        Spool.objects.create(filament=self.pla_black, initial_weight_g=1000, cost=18, is_active=True)
        Spool.objects.create(filament=self.petg_red, initial_weight_g=1000, cost=22, is_active=True)
        Spool.objects.create(filament=self.petg_exhausted_blue, initial_weight_g=1000, cost=22, is_active=False)

    def test_filter_by_material(self):
        from django.urls import reverse
        res_pla = self.client.get(reverse('filament_dashboard'), {'material': 'PLA'})
        self.assertEqual(res_pla.status_code, 200)
        active_ids = list(res_pla.context['active_filaments'].values_list('id', flat=True))
        self.assertCountEqual(active_ids, [self.pla_red.id, self.pla_black.id])

        res_petg = self.client.get(reverse('filament_dashboard'), {'material': 'PETG'})
        self.assertEqual(res_petg.status_code, 200)
        active_petg_ids = list(res_petg.context['active_filaments'].values_list('id', flat=True))
        exhausted_petg_ids = list(res_petg.context['exhausted_filaments'].values_list('id', flat=True))
        self.assertEqual(active_petg_ids, [self.petg_red.id])
        self.assertEqual(exhausted_petg_ids, [self.petg_exhausted_blue.id])

    def test_filter_by_brand(self):
        from django.urls import reverse
        res = self.client.get(reverse('filament_dashboard'), {'brand': 'SUN-M'})
        self.assertEqual(res.status_code, 200)
        active_ids = list(res.context['active_filaments'].values_list('id', flat=True))
        self.assertEqual(active_ids, [self.petg_red.id])

    def test_search_by_color_code_multiword_and_composite(self):
        from django.urls import reverse
        # Ricerca per nome colore ("rosso")
        res_color = self.client.get(reverse('filament_dashboard'), {'q': 'rosso'})
        self.assertCountEqual(
            list(res_color.context['active_filaments'].values_list('id', flat=True)),
            [self.pla_red.id, self.petg_red.id]
        )

        # Ricerca multi-parola ("PLA rosso")
        res_multi = self.client.get(reverse('filament_dashboard'), {'q': 'PLA rosso'})
        self.assertEqual(
            list(res_multi.context['active_filaments'].values_list('id', flat=True)),
            [self.pla_red.id]
        )

        # Ricerca per codice colore ("100")
        res_code = self.client.get(reverse('filament_dashboard'), {'q': '100'})
        self.assertEqual(
            list(res_code.context['active_filaments'].values_list('id', flat=True)),
            [self.pla_red.id]
        )

        # Ricerca per codice composito ("PLA-100-AMZ") e marca con trattino ("SUN-M")
        res_comp = self.client.get(reverse('filament_dashboard'), {'q': 'PLA-100-AMZ'})
        self.assertEqual(
            list(res_comp.context['active_filaments'].values_list('id', flat=True)),
            [self.pla_red.id]
        )
        res_hyphen_brand = self.client.get(reverse('filament_dashboard'), {'q': 'SUN-M'})
        self.assertEqual(
            list(res_hyphen_brand.context['active_filaments'].values_list('id', flat=True)),
            [self.petg_red.id]
        )

    def test_hx_request_partial_and_auto_expand_exhausted(self):
        from django.urls import reverse
        res = self.client.get(
            reverse('filament_dashboard'),
            {'q': 'blu'},
            HTTP_HX_REQUEST='true'
        )
        self.assertEqual(res.status_code, 200)
        self.assertTemplateUsed(res, 'app_3dmage_management/partials/filaments_tables.html')
        self.assertEqual(list(res.context['active_filaments']), [])
        self.assertEqual(
            list(res.context['exhausted_filaments'].values_list('id', flat=True)),
            [self.petg_exhausted_blue.id]
        )
        html = res.content.decode('utf-8')
        self.assertIn('id="collapseEsauriti" class="accordion-collapse collapse show"', html)
        self.assertIn('Blu Cobalto', html)

    def test_api_and_context_include_color_metadata(self):
        import json
        from django.urls import reverse

        # 1. api_get_all_filaments
        res_api = self.client.get(reverse('api_get_all_filaments'))
        self.assertEqual(res_api.status_code, 200)
        api_data = json.loads(res_api.content)
        red_entry = next(item for item in api_data if item['id'] == self.pla_red.id)
        self.assertEqual(red_entry['color_name'], 'Rosso Fuoco')
        self.assertEqual(red_entry['material'], 'PLA')
        self.assertEqual(red_entry['color_code'], '100')
        self.assertEqual(red_entry['brand'], 'AMZ')

        # 2. project_master_detail context all_filaments_json
        master = Project.objects.create(name='Test Master')
        res_master = self.client.get(reverse('project_master_detail', args=[master.id]))
        self.assertEqual(res_master.status_code, 200)
        master_filaments = res_master.context['all_filaments_json']
        master_red = next(item for item in master_filaments if item['id'] == self.pla_red.id)
        self.assertEqual(master_red['color_name'], 'Rosso Fuoco')
        self.assertEqual(master_red['material'], 'PLA')
        self.assertEqual(master_red['color_code'], '100')
        self.assertEqual(master_red['brand'], 'AMZ')

        # 3. api_get_costs
        res_costs = self.client.get(reverse('api_get_costs'))
        self.assertEqual(res_costs.status_code, 200)
        costs_data = json.loads(res_costs.content)
        costs_red = next(item for item in costs_data['filaments'] if item['id'] == self.pla_red.id)
        self.assertEqual(costs_red['color_name'], 'Rosso Fuoco')
        self.assertEqual(costs_red['material'], 'PLA')
        self.assertEqual(costs_red['color_code'], '100')
        self.assertEqual(costs_red['brand'], 'AMZ')

