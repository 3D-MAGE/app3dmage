import os
import django
import sys

# Setup Django environment
sys.path.append('/Users/mirko/app 3dmage_management')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project_3dmage.settings')
django.setup()

from app_3dmage_management.models import Project, Category, Printer, MasterPrintFile, Plate
from app_3dmage_management.templatetags.app_filters import get_project_printers

def run_test():
    print("--- Setting up test data ---")
    
    # 1. Create Category
    cat, _ = Category.objects.get_or_create(name="Test Category")
    
    # 2. Create Project
    proj, _ = Project.objects.get_or_create(name="Test Project Master", category=cat)
    
    # 3. Create Printers
    p_tagged, _ = Printer.objects.get_or_create(name="Printer Tagged", defaults={'tag': 'TAG1'})
    p_untagged, _ = Printer.objects.get_or_create(name="Printer NoTag", defaults={'tag': None})
    
    # 4. Create Master Print Files
    mpf1, _ = MasterPrintFile.objects.get_or_create(name="File 1", project=proj, printer=p_tagged)
    mpf2, _ = MasterPrintFile.objects.get_or_create(name="File 2", project=proj, printer=p_untagged)

    print(f"Project: {proj.name}")
    print(f"Category: {proj.category.name if proj.category else 'NONE'}")
    
    print("\n--- Testing get_project_printers filter ---")
    printers = get_project_printers(proj)
    for p in printers:
        print(f"Printer: ID='{p['id']}', Name='{p['name']}', Tag='{p['tag']}'")

    print("\n--- Done ---")

if __name__ == "__main__":
    run_test()
