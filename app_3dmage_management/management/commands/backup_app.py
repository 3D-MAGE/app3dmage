import os
import sys
import time
import shutil
import tarfile
import sqlite3
import datetime
import urllib.request
import urllib.parse
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = "Esegue un backup automatico e coerente del database SQLite e della cartella media (con rotazione e supporto off-site)"

    def add_arguments(self, parser):
        parser.add_argument(
            '--keep',
            type=int,
            default=14,
            help='Numero massimo di backup da conservare (default: 14)'
        )
        parser.add_argument(
            '--dest',
            type=str,
            default='',
            help='Cartella di destinazione dei backup (default: <BASE_DIR>/backups)'
        )

    def handle(self, *args, **options):
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        base_dir = Path(settings.BASE_DIR)

        # Destinazione cartella backup
        dest_dir = Path(options['dest']) if options['dest'] else (base_dir / "backups")
        dest_dir.mkdir(parents=True, exist_ok=True)

        temp_dir = dest_dir / f"tmp_{timestamp}"
        temp_dir.mkdir(parents=True, exist_ok=True)

        archive_name = f"3dmage_backup_{timestamp}.tar.gz"
        archive_path = dest_dir / archive_name

        self.stdout.write(self.style.NOTICE(f"Avvio procedura backup 3DMAGE ({timestamp})..."))

        try:
            # 1. Backup sicuro e a caldo del Database SQLite
            db_path = Path(settings.DATABASES['default']['NAME'])
            if db_path.exists():
                temp_db_copy = temp_dir / "db.sqlite3"
                self.stdout.write(f"- Creazione snapshot atomico del database ({db_path.name})...")
                
                src = sqlite3.connect(str(db_path))
                dst = sqlite3.connect(str(temp_db_copy))
                with dst:
                    src.backup(dst)
                dst.close()
                src.close()
            else:
                self.stdout.write(self.style.WARNING(f"- File database non trovato in {db_path}"))

            # 2. Inclusione cartella Media (se presente)
            media_dir = Path(settings.MEDIA_ROOT)
            if media_dir.exists() and any(media_dir.iterdir()):
                self.stdout.write(f"- Preparazione cartella media ({media_dir.name})...")
                temp_media_dir = temp_dir / "media"
                shutil.copytree(media_dir, temp_media_dir, dirs_exist_ok=True)

            # 3. Creazione archivio compresso .tar.gz
            self.stdout.write(f"- Compressione archivio in {archive_path.name}...")
            with tarfile.open(archive_path, "w:gz") as tar:
                for item in temp_dir.iterdir():
                    tar.add(item, arcname=item.name)

            archive_size_mb = archive_path.stat().st_size / (1024 * 1024)
            self.stdout.write(self.style.SUCCESS(
                f"✓ Archivio creato con successo: {archive_path.name} ({archive_size_mb:.2f} MB)"
            ))

            # 4. Invio Off-Site opzionale (es. Telegram Bot)
            self._send_to_telegram(archive_path, archive_size_mb, timestamp)

            # 5. Rotazione automatica: eliminazione backup più vecchi
            keep_count = options['keep']
            self._rotate_backups(dest_dir, keep_count)

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Errore durante il backup: {str(e)}"))
            raise e
        finally:
            # Pulizia file temporanei di staging
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)

    def _rotate_backups(self, dest_dir: Path, keep: int):
        all_backups = sorted(
            [f for f in dest_dir.glob("3dmage_backup_*.tar.gz")],
            key=lambda x: x.stat().st_mtime
        )
        if len(all_backups) > keep:
            to_remove = all_backups[:-keep]
            self.stdout.write(f"- Rotazione backup: rimozione di {len(to_remove)} file obsoleti...")
            for old_file in to_remove:
                try:
                    old_file.unlink()
                    self.stdout.write(f"  • Rimosso: {old_file.name}")
                except Exception as ex:
                    self.stdout.write(self.style.WARNING(f"  ! Impossibile rimuovere {old_file.name}: {ex}"))

    def _send_to_telegram(self, file_path: Path, size_mb: float, timestamp: str):
        bot_token = os.environ.get("TELEGRAM_BACKUP_BOT_TOKEN", "").strip()
        chat_id = os.environ.get("TELEGRAM_BACKUP_CHAT_ID", "").strip()

        if not bot_token or not chat_id:
            return

        if size_mb > 49.0:
            self.stdout.write(self.style.WARNING("- Archivio > 50MB, skip invio diretto via Telegram Bot API."))
            return

        self.stdout.write("- Invio copia di sicurezza off-site su Telegram...")
        try:
            url = f"https://api.telegram.org/bot{bot_token}/sendDocument"
            boundary = f"----WebKitFormBoundary{int(time.time()*1000)}"
            
            body = bytearray()
            # chat_id field
            body.extend(f"--{boundary}\r\n".encode())
            body.extend(b'Content-Disposition: form-data; name="chat_id"\r\n\r\n')
            body.extend(f"{chat_id}\r\n".encode())

            # caption field
            body.extend(f"--{boundary}\r\n".encode())
            body.extend(b'Content-Disposition: form-data; name="caption"\r\n\r\n')
            body.extend(f"💾 Backup automatico 3DMAGE ({timestamp}) - Dimensione: {size_mb:.2f} MB\r\n".encode())

            # document field
            body.extend(f"--{boundary}\r\n".encode())
            body.extend(f'Content-Disposition: form-data; name="document"; filename="{file_path.name}"\r\n'.encode())
            body.extend(b'Content-Type: application/gzip\r\n\r\n')
            with open(file_path, "rb") as f:
                body.extend(f.read())
            body.extend(b"\r\n")

            body.extend(f"--{boundary}--\r\n".encode())

            req = urllib.request.Request(
                url,
                data=bytes(body),
                headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                if resp.status == 200:
                    self.stdout.write(self.style.SUCCESS("✓ Backup inviato con successo su Telegram."))
                else:
                    self.stdout.write(self.style.WARNING(f"Risposta Telegram: {resp.status}"))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"! Errore invio Telegram: {e}"))
