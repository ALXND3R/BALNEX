from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("web", "0002_evento_finanzas_servicios_notificaciones"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="reservacion",
            constraint=models.UniqueConstraint(
                condition=~models.Q(("estado", "cancelada")),
                fields=("evento", "usuario"),
                name="reservacion_activa_unica_por_usuario_evento",
            ),
        ),
    ]
