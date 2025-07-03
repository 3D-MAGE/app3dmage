# in app_3dmage_management/tests.py

from django.test import TestCase
from .models import Project, PrintFile

class ProjectModelTests(TestCase):

    def test_progress_percentage_no_files(self):
        """Verifica che la percentuale di avanzamento sia 0 se non ci sono file di stampa."""
        # 1. Preparazione: Crea un progetto senza file
        project = Project.objects.create(name="Progetto Vuoto")

        # 2. Azione: Accedi alla proprietà
        progress = project.progress_percentage

        # 3. Verifica: Il risultato deve essere 0
        self.assertEqual(progress, 0)

    def test_progress_percentage_half_done(self):
        """Verifica il calcolo della percentuale con metà dei file completati."""
        # 1. Preparazione: Crea un progetto e 4 file associati
        project = Project.objects.create(name="Progetto a Metà")
        PrintFile.objects.create(project=project, name="file1", status=PrintFile.Status.DONE)
        PrintFile.objects.create(project=project, name="file2", status=PrintFile.Status.DONE)
        PrintFile.objects.create(project=project, name="file3", status=PrintFile.Status.TODO)
        PrintFile.objects.create(project=project, name="file4", status=PrintFile.Status.FAILED)

        # 2. Azione: Accedi alla proprietà
        progress = project.progress_percentage

        # 3. Verifica: 2 file su 4 sono 'DONE', quindi ci aspettiamo il 50%
        # Nota: la tua logica attuale conta solo i file 'DONE' sul totale.
        self.assertEqual(progress, 50)

    def test_progress_percentage_all_done(self):
        """Verifica che la percentuale sia 100 se tutti i file sono completati."""
        # 1. Preparazione
        project = Project.objects.create(name="Progetto Finito")
        PrintFile.objects.create(project=project, name="file1", status=PrintFile.Status.DONE)
        PrintFile.objects.create(project=project, name="file2", status=PrintFile.Status.DONE)

        # 2. Azione
        progress = project.progress_percentage

        # 3. Verifica
        self.assertEqual(progress, 100)
