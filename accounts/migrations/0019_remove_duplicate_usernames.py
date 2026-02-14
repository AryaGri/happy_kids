# Удаление дубликатов username перед добавлением unique constraint
# Выполняется в отдельной миграции, т.к. PostgreSQL не позволяет ALTER TABLE
# в той же транзакции после изменения данных

from django.db import migrations


def remove_duplicate_usernames(apps, schema_editor):
    CUsers = apps.get_model('accounts', 'CUsers')
    seen = set()
    for user in CUsers.objects.order_by('id'):
        if user.username in seen:
            user.delete()
        else:
            seen.add(user.username)


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0018_populate_diagnoses'),
    ]

    operations = [
        migrations.RunPython(remove_duplicate_usernames, migrations.RunPython.noop),
    ]
