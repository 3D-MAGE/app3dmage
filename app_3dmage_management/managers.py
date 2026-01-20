from django.db import models
from django.db.models import Sum, Case, When, Value, DecimalField, F, IntegerField, ExpressionWrapper
from django.db.models.functions import Coalesce
from decimal import Decimal

class WorkOrderQuerySet(models.QuerySet):
    def with_annotations(self):
        """
        Applies standard annotations used in dashboards:
        - total_print_time_seconds
        - remaining_print_time_seconds
        - annotated_material_cost
        Uses Subqueries to avoid duplication from joins.
        """
        from django.db.models import OuterRef, Subquery
        from .models import PrintFile, FilamentUsage

        # 1. Total Print Time Subquery
        total_time_sub = PrintFile.objects.filter(
            work_order=OuterRef('pk')
        ).values('work_order').annotate(
            total=Sum('print_time_seconds')
        ).values('total')

        # 2. Remaining Print Time Subquery
        remaining_time_sub = PrintFile.objects.filter(
            work_order=OuterRef('pk'),
            status='TODO'
        ).values('work_order').annotate(
            total=Sum('print_time_seconds')
        ).values('total')

        # 3. Material Cost Subquery
        # Needs to join FilamentUsage to PrintFile, then filter by work_order
        cost_sub = FilamentUsage.objects.filter(
            print_file__work_order=OuterRef('pk')
        ).annotate(
            usage_cost=ExpressionWrapper(
                F('grams_used') * F('spool__cost') /
                Case(
                    When(spool__initial_weight_g=0, then=Value(1)),
                    default=F('spool__initial_weight_g'),
                    output_field=DecimalField()
                ),
                output_field=DecimalField()
            )
        ).values('print_file__work_order').annotate(
            total=Sum('usage_cost')
        ).values('total')

        # 4. Printing status check (any file printing?)
        # We can use Exists for efficiency
        from django.db.models import Exists
        is_printing_sub = Exists(
            PrintFile.objects.filter(work_order=OuterRef('pk'), status='PRINTING')
        )

        # 5. Progress percentage subquery (done files / total files)
        from django.db.models import Count, Q, FloatField
        
        total_files_sub = PrintFile.objects.filter(
            work_order=OuterRef('pk')
        ).exclude(status='FAILED').values('work_order').annotate(
            count=Count('id')
        ).values('count')
        
        done_files_sub = PrintFile.objects.filter(
            work_order=OuterRef('pk'),
            status='DONE'
        ).values('work_order').annotate(
            count=Count('id')
        ).values('count')

        return self.annotate(
            priority_order=Case(
                When(priority='URGENT', then=Value(0)),
                When(priority='HIGH', then=Value(1)),
                When(priority='MEDIUM', then=Value(2)),
                When(priority='LOW', then=Value(3)),
                default=Value(4),
                output_field=IntegerField()
            ),
            total_print_time_seconds=Coalesce(Subquery(total_time_sub), Value(0), output_field=IntegerField()),
            remaining_print_time_seconds=Coalesce(Subquery(remaining_time_sub), Value(0), output_field=IntegerField()),
            is_printing_any=Case(
                When(is_printing_sub, then=Value(1)),
                default=Value(0),
                output_field=IntegerField()
            ),
            annotated_material_cost=Coalesce(Subquery(cost_sub), Decimal('0.00'), output_field=DecimalField()),
            total_files_count=Coalesce(Subquery(total_files_sub), Value(0), output_field=IntegerField()),
            done_files_count=Coalesce(Subquery(done_files_sub), Value(0), output_field=IntegerField()),
            progress_percentage_value=Case(
                When(total_files_count=0, then=Value(0.0)),
                default=ExpressionWrapper(
                    F('done_files_count') * 100.0 / F('total_files_count'),
                    output_field=FloatField()
                ),
                output_field=FloatField()
            )
        )

class WorkOrderManager(models.Manager):
    def get_queryset(self):
        return WorkOrderQuerySet(self.model, using=self._db)

    def with_annotations(self):
        return self.get_queryset().with_annotations()
