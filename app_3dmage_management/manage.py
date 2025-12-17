
#!/usr/bin/env python
import os
import sys

def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project_3dmage.settings')
    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv)

ifif __name__ == '__main__':
