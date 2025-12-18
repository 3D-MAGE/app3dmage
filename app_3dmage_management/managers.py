from django.db import models
from django.db.models import Sum, Case, When, Value, DecimalField, F, IntegerField, ExpressionWrapper
from django.db.models.functions import Coalesce
from decimal import Decimal

class ProjectQuerySet(models.QuerySet):
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
            project=OuterRef('pk')
        ).values('project').annotate(
            total=Sum('print_time_seconds')
        ).values('total')

        # 2. Remaining Print Time Subquery
        remaining_time_sub = PrintFile.objects.filter(
            project=OuterRef('pk'),
            status='TODO'
        ).values('project').annotate(
            total=Sum('print_time_seconds')
        ).values('total')

        # 3. Material Cost Subquery
        # Needs to join FilamentUsage to PrintFile, then filter by project
        cost_sub = FilamentUsage.objects.filter(
            print_file__project=OuterRef('pk')
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
        ).values('print_file__project').annotate(
            total=Sum('usage_cost')
        ).values('total')

        # 4. Printing status check (any file printing?)
        # We can use Exists for efficiency
        from django.db.models import Exists
        is_printing_sub = Exists(
            PrintFile.objects.filter(project=OuterRef('pk'), status='PRINTING')
        )

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
            annotated_material_cost=Coalesce(Subquery(cost_sub), Decimal('0.00'), output_field=DecimalField())
        )

class ProjectManager(models.Manager):
    def get_queryset(self):
        return ProjectQuerySet(self.model, using=self._db)

    def with_annotations(self):
        return self.get_queryset().with_annotations()
