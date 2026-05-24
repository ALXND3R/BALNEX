# Generated manually for BalNex event management expansion.

import django.db.models.deletion
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("web", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="evento",
            name="categoria",
            field=models.CharField(
                choices=[
                    ("general", "General"),
                    ("conferencia", "Conferencia"),
                    ("taller", "Taller"),
                    ("curso", "Curso"),
                    ("fiesta", "Fiesta"),
                    ("deportivo", "Deportivo"),
                    ("cultural", "Cultural"),
                    ("academico", "Académico"),
                    ("empresarial", "Empresarial"),
                    ("otro", "Otro"),
                ],
                default="general",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="evento",
            name="precio_persona",
            field=models.DecimalField(
                decimal_places=2, default=Decimal("0.00"), max_digits=10
            ),
        ),
        migrations.CreateModel(
            name="ServicioExtra",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("nombre", models.CharField(max_length=80)),
                ("descripcion", models.TextField(blank=True)),
                (
                    "precio",
                    models.DecimalField(
                        decimal_places=2, default=Decimal("0.00"), max_digits=10
                    ),
                ),
                ("activo", models.BooleanField(default=True)),
                (
                    "evento",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="servicios_extra",
                        to="web.evento",
                    ),
                ),
            ],
        ),
        migrations.AddField(
            model_name="reservacion",
            name="estado",
            field=models.CharField(
                choices=[
                    ("pendiente", "Pendiente"),
                    ("confirmada", "Confirmada"),
                    ("pagada", "Pagada"),
                    ("cancelada", "Cancelada"),
                    ("asistio", "Asistió"),
                    ("no_asistio", "No asistió"),
                ],
                default="pendiente",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="reservacion",
            name="servicios_extra",
            field=models.ManyToManyField(
                blank=True,
                related_name="reservaciones",
                to="web.servicioextra",
            ),
        ),
        migrations.CreateModel(
            name="ActividadEvento",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("mensaje", models.CharField(max_length=255)),
                ("fecha", models.DateTimeField(auto_now_add=True)),
                (
                    "evento",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="historial",
                        to="web.evento",
                    ),
                ),
                (
                    "usuario",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="actividades_eventos",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-fecha"],
            },
        ),
        migrations.CreateModel(
            name="NotificacionInterna",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("mensaje", models.CharField(max_length=255)),
                ("fecha", models.DateTimeField(auto_now_add=True)),
                ("leida", models.BooleanField(default=False)),
                ("enlace", models.CharField(blank=True, max_length=255)),
                (
                    "usuario",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="notificaciones",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-fecha"],
            },
        ),
    ]
