
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings') # Assuming config is the project root
django.setup()

from app_3dmage_management.models import Project, ProjectOutput

def migrate_base_quantities():
    projects = Project.objects.all()
    count = 0
    for project in projects:
        if not project.outputs.exists():
            ProjectOutput.objects.create(
                project=project,
                name=project.name,
                quantity=project.base_quantity
            )
            count += 1
    print(f"Migrated {count} projects to ProjectOutput structure.")

if __name__ == "__main__":
    migrate_base_quantities()
