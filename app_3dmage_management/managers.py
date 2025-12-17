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
        """
        cost_annotation = Sum(
            ExpressionWrapper(
                F('print_files__filament_usages__grams_used') *
                F('print_files__filament_usages__spool__cost') /
                Case(
                    When(print_files__filament_usages__spool__initial_weight_g=0, then=Value(1)),
                    default=F('print_files__filament_usages__spool__initial_weight_g'),
                    output_field=DecimalField()
                ),
                output_field=DecimalField()
            )
        )

        return self.annotate(
            total_print_time_seconds=Sum('print_files__print_time_seconds', default=0),
            remaining_print_time_seconds=Sum(
                Case(
                    When(print_files__status='TODO', then='print_files__print_time_seconds'),
                    default=Value(0)
                ),
                output_field=IntegerField()
            ),
            annotated_material_cost=Coalesce(cost_annotation, Decimal('0.00'), output_field=DecimalField())
        )

class ProjectManager(models.Manager):
    def get_queryset(self):
        return ProjectQuerySet(self.model, using=self._db)

    def with_annotations(self):
        return self.get_queryset().with_annotations()
