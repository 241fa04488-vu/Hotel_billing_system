"""
WSGI config for hotel_billing project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import os
import django
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hotel_billing.settings')

# 🚀 Automated Production Database Startup Routine
# This ensures migrations and database seeding run automatically when Gunicorn starts.
django.setup()

from django.core.management import call_command
print("Booting System: Applying database migrations...")
try:
    call_command('migrate', interactive=False)
    print("Migrations applied successfully!")
except Exception as e:
    print(f"Error running migrations: {e}")

try:
    from seed_rooms import seed_rooms
    from seed_users import seed_users
    print("Verifying default rooms database...")
    seed_rooms()
    print("Verifying default accounts database...")
    seed_users()
    print("Database seeding verification completed successfully!")
except Exception as e:
    print(f"Error seeding database: {e}")

application = get_wsgi_application()
