from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from decimal import Decimal
from django.utils import timezone

from .models import (
    RawMaterial, RawMaterialPurchase, Project, WorkOrder, 
    PaymentMethod, Expense, ProjectRawMaterial, WorkOrderRawMaterial
)

class RawMaterialsBusinessLogicTests(TestCase):
    def setUp(self):
        # Setup payment method
        self.payment_method = PaymentMethod.objects.create(name="Cassa Test", balance=Decimal("100.00"))
        
        # Setup raw material
        self.material = RawMaterial.objects.create(name="Magnet 10x2", notes="Test notes")
        
        # Setup users for view testing
        self.user = User.objects.create_user(username='testuser', password='password')
        self.client = Client()

    def test_purchase_creates_expense_and_deducts_balance(self):
        """Test that registering a raw material purchase updates balance and creates an Expense."""
        self.client.login(username='testuser', password='password')
        
        # Register purchase via view
        response = self.client.post(reverse('add_raw_material_purchase'), {
            'raw_material': self.material.id,
            'quantity': 50,
            'cost': '10.00',
            'purchase_date': timezone.now().date().strftime('%Y-%m-%d'),
            'purchase_link': '',
            'payment_method': self.payment_method.id
        })
        
        self.assertEqual(response.status_code, 302)
        
        # Verify purchase was created
        purchase = RawMaterialPurchase.objects.first()
        self.assertIsNotNone(purchase)
        self.assertEqual(purchase.quantity, 50)
        self.assertEqual(purchase.cost, Decimal("10.00"))
        
        # Verify expense was created
        expense = Expense.objects.first()
        self.assertIsNotNone(expense)
        self.assertEqual(expense.amount, Decimal("10.00"))
        self.assertEqual(expense.category.name, "Materie Prime")
        self.assertEqual(purchase.expense, expense)
        
        # Verify payment method balance was updated
        self.payment_method.refresh_from_db()
        self.assertEqual(self.payment_method.balance, Decimal("90.00"))

    def test_delete_purchase_refunds_balance_and_deletes_expense(self):
        """Test that deleting a purchase storns the expense and refunds the payment method balance."""
        self.client.login(username='testuser', password='password')
        
        # Create a purchase
        purchase = RawMaterialPurchase.objects.create(
            raw_material=self.material,
            quantity=50,
            cost=Decimal("10.00"),
            purchase_date=timezone.now().date(),
            payment_method=self.payment_method
        )
        # Create corresponding expense
        expense = Expense.objects.create(
            description="Acquisto materia prima: 50x Magnet 10x2",
            amount=Decimal("10.00"),
            expense_date=purchase.purchase_date,
            payment_method=self.payment_method
        )
        purchase.expense = expense
        purchase.save()
        
        # Deduct balance manually as done in view logic
        self.payment_method.balance -= Decimal("10.00")
        self.payment_method.save()
        
        # Call delete purchase view
        response = self.client.post(reverse('delete_raw_material_purchase', args=[purchase.id]))
        self.assertEqual(response.status_code, 200)
        
        # Verify purchase is deleted
        self.assertFalse(RawMaterialPurchase.objects.filter(id=purchase.id).exists())
        # Verify expense is deleted
        self.assertFalse(Expense.objects.filter(id=expense.id).exists())
        
        # Verify payment method balance was refunded
        self.payment_method.refresh_from_db()
        self.assertEqual(self.payment_method.balance, Decimal("100.00"))

    def test_stock_quantities_and_warnings(self):
        """Test available_quantity, remaining_quantity, pending_quantity and shortage calculations."""
        # 1. Purchase 20 magnets
        purchase = RawMaterialPurchase.objects.create(
            raw_material=self.material,
            quantity=20,
            cost=Decimal("4.00"), # unit cost = 0.20
            purchase_date=timezone.now().date(),
            payment_method=self.payment_method
        )
        
        self.assertEqual(self.material.total_purchased, 20)
        self.assertEqual(self.material.remaining_quantity, 20)
        self.assertEqual(self.material.available_quantity, 20)
        self.assertEqual(self.material.average_unit_cost, Decimal("0.20"))
        
        # 2. Create work order demanding 5 magnets
        wo1 = WorkOrder.objects.create(name="Active Order", status=WorkOrder.Status.TODO)
        worm1 = WorkOrderRawMaterial.objects.create(work_order=wo1, raw_material=self.material, quantity=5)
        
        self.assertEqual(self.material.total_pending, 5)
        self.assertEqual(self.material.available_quantity, 15)
        self.assertFalse(worm1.is_insufficient)
        self.assertEqual(worm1.shortage_quantity, 0)
        
        # 3. Create another work order demanding 20 magnets (total requested 25, stock 20)
        wo2 = WorkOrder.objects.create(name="Active Order 2", status=WorkOrder.Status.PRINTING)
        worm2 = WorkOrderRawMaterial.objects.create(work_order=wo2, raw_material=self.material, quantity=20)
        
        self.assertEqual(self.material.total_pending, 25)
        self.assertEqual(self.material.available_quantity, -5) # Shortage of 5
        self.assertTrue(worm2.is_insufficient)
        self.assertEqual(worm2.shortage_quantity, 5)
        
        # 4. Complete first work order (wo1 status -> DONE)
        wo1.status = WorkOrder.Status.DONE
        wo1.save()
        
        # Now 5 are consumed, 20 are pending
        self.assertEqual(self.material.total_used, 5)
        self.assertEqual(self.material.total_pending, 20)
        self.assertEqual(self.material.remaining_quantity, 15)
        self.assertEqual(self.material.available_quantity, -5) # Still shortage of 5

    def test_cloning_from_master_project(self):
        """Test that Project.create_work_order correctly copies raw materials with multiplied quantities."""
        project = Project.objects.create(name="Master Model", base_quantity=1)
        ProjectRawMaterial.objects.create(project=project, raw_material=self.material, quantity=3)
        
        # Create work order with quantity of 4 sets
        wo = project.create_work_order(quantity=4)
        
        # Verify work order raw material quantity: 3 * 4 = 12
        worm = wo.raw_materials.first()
        self.assertIsNotNone(worm)
        self.assertEqual(worm.raw_material, self.material)
        self.assertEqual(worm.quantity, 12)

    def test_work_order_cost_calculation(self):
        """Test that WorkOrder.full_total_cost incorporates raw material costs."""
        # Setup purchase
        RawMaterialPurchase.objects.create(
            raw_material=self.material,
            quantity=10,
            cost=Decimal("5.00"), # unit cost = 0.50
            purchase_date=timezone.now().date(),
            payment_method=self.payment_method
        )
        
        wo = WorkOrder.objects.create(name="Costly Order", status=WorkOrder.Status.TODO)
        WorkOrderRawMaterial.objects.create(work_order=wo, raw_material=self.material, quantity=6)
        
        # Cost of raw materials should be 6 * 0.50 = 3.00
        # Since there are no print files, full_total_cost should be exactly 3.00
        self.assertEqual(wo.full_total_cost, Decimal("3.00"))

    def test_create_from_template_view_copies_raw_materials(self):
        """Test that the create_from_template view copies raw materials from project template to work order."""
        self.client.login(username='testuser', password='password')
        
        project = Project.objects.create(name="Template Project", base_quantity=1)
        ProjectRawMaterial.objects.create(project=project, raw_material=self.material, quantity=5)
        
        # Post to create_from_template view
        response = self.client.post(reverse('create_from_template', args=[project.id]), {
            'quantity': 3,
            'ignore_warnings': 'true'
        })
        
        self.assertEqual(response.status_code, 302)
        
        # Verify work order was created and raw materials were copied
        wo = WorkOrder.objects.filter(project=project).first()
        self.assertIsNotNone(wo)
        self.assertEqual(wo.quantity, 3)
        
        worm = wo.raw_materials.first()
        self.assertIsNotNone(worm)
        self.assertEqual(worm.raw_material, self.material)
        self.assertEqual(worm.quantity, 15) # 5 * 3
