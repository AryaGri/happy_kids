# Generated manually for doctor patients (add child by code)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0014_fuzzy_models'),
    ]

    operations = [
        migrations.AddField(
            model_name='cusers',
            name='patients',
            field=models.ManyToManyField(
                blank=True,
                limit_choices_to={'role': 'child'},
                related_name='doctors',
                to='accounts.cusers'
            ),
        ),
    ]
