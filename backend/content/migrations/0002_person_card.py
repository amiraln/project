import django.core.validators
from django.db import migrations, models


def split_full_name(apps, schema_editor):
    """«Фамилия Имя Отчество» → три поля; отчество может быть из двух слов («Ерлан қызы»)."""
    Person = apps.get_model('content', 'Person')
    for person in Person.objects.all():
        parts = person.full_name.split()
        person.last_name = parts[0] if parts else ''
        person.first_name = parts[1] if len(parts) > 1 else ''
        person.middle_name = ' '.join(parts[2:])
        person.save(update_fields=['last_name', 'first_name', 'middle_name'])


def join_full_name(apps, schema_editor):
    Person = apps.get_model('content', 'Person')
    for person in Person.objects.all():
        person.full_name = ' '.join(filter(None, [person.last_name, person.first_name, person.middle_name]))
        person.save(update_fields=['full_name'])


class Migration(migrations.Migration):

    dependencies = [
        ('content', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='person',
            name='last_name',
            field=models.CharField(default='', max_length=100, verbose_name='Фамилия'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='person',
            name='first_name',
            field=models.CharField(default='', max_length=100, verbose_name='Имя'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='person',
            name='middle_name',
            field=models.CharField(blank=True, max_length=100, verbose_name='Отчество'),
        ),
        migrations.RunPython(split_full_name, join_full_name),
        migrations.RemoveField(
            model_name='person',
            name='full_name',
        ),
        migrations.AlterField(
            model_name='person',
            name='education_kk',
            field=models.CharField(blank=True, help_text='Где получено образование, например: КазНПУ им. Абая, 2012', max_length=500, verbose_name='Учебное заведение (қаз.)'),
        ),
        migrations.AlterField(
            model_name='person',
            name='education_ru',
            field=models.CharField(blank=True, help_text='Где получено образование, например: КазНПУ им. Абая, 2012', max_length=500, verbose_name='Учебное заведение (рус.)'),
        ),
        migrations.AddField(
            model_name='person',
            name='specialty_kk',
            field=models.CharField(blank=True, max_length=255, verbose_name='Специальность (қаз.)'),
        ),
        migrations.AddField(
            model_name='person',
            name='specialty_ru',
            field=models.CharField(blank=True, max_length=255, verbose_name='Специальность (рус.)'),
        ),
        migrations.AddField(
            model_name='person',
            name='retraining_date',
            field=models.DateField(blank=True, null=True, verbose_name='Дата сертификата'),
        ),
        migrations.AddField(
            model_name='person',
            name='retraining_place_kk',
            field=models.CharField(blank=True, max_length=255, verbose_name='Где пройдена (қаз.)'),
        ),
        migrations.AddField(
            model_name='person',
            name='retraining_place_ru',
            field=models.CharField(blank=True, max_length=255, verbose_name='Где пройдена (рус.)'),
        ),
        migrations.AlterField(
            model_name='person',
            name='qualification_kk',
            field=models.CharField(blank=True, help_text='Название квалификации, например: педагог-модератор', max_length=255, verbose_name='Квалификация (қаз.)'),
        ),
        migrations.AlterField(
            model_name='person',
            name='qualification_ru',
            field=models.CharField(blank=True, help_text='Название квалификации, например: педагог-модератор', max_length=255, verbose_name='Квалификация (рус.)'),
        ),
        migrations.AddField(
            model_name='person',
            name='qualification_year',
            field=models.PositiveSmallIntegerField(blank=True, null=True, validators=[django.core.validators.MinValueValidator(1950)], verbose_name='Год присвоения квалификации'),
        ),
        migrations.AlterField(
            model_name='person',
            name='experience_years',
            field=models.PositiveSmallIntegerField(blank=True, null=True, verbose_name='Общий педагогический стаж, лет'),
        ),
        migrations.AddField(
            model_name='person',
            name='position_experience_years',
            field=models.PositiveSmallIntegerField(blank=True, null=True, verbose_name='Стаж по занимаемой должности, лет'),
        ),
    ]
