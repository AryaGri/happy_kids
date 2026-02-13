# Generated migration - создание администратора admin1/123456

from django.db import migrations
from django.contrib.auth.hashers import make_password
from datetime import date


def create_admin(apps, schema_editor):
    CUsers = apps.get_model('accounts', 'CUsers')
    if not CUsers.objects.filter(username='admin1').exists():
        CUsers.objects.create(
            username='admin1',
            name='Администратор',
            date_of_b=date(1990, 1, 1),
            role='admin',
            password=make_password('123456'),
            is_auth=True,
        )
        CUsers.objects.create(
            username='admin1',
            name='Администратор',
            date_of_b=date(1990, 1, 1),
            role='admin',
            password=make_password('123456'),
            is_auth=True,
        )


def reverse_create_admin(apps, schema_editor):
    CUsers = apps.get_model('accounts', 'CUsers')
    CUsers.objects.filter(username='admin1').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0015_add_doctor_patients'),
    ]

    operations = [
        migrations.RunPython(create_admin, reverse_create_admin),
    ]
