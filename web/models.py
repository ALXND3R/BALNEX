import uuid
from decimal import Decimal
from django.db import models
from django.contrib.auth.models import User


def generar_codigo_unico():
    return uuid.uuid4().hex[:8].upper()


class Evento(models.Model):
    CATEGORIA_GENERAL = "general"
    CATEGORIA_CONFERENCIA = "conferencia"
    CATEGORIA_TALLER = "taller"
    CATEGORIA_CURSO = "curso"
    CATEGORIA_FIESTA = "fiesta"
    CATEGORIA_DEPORTIVO = "deportivo"
    CATEGORIA_CULTURAL = "cultural"
    CATEGORIA_ACADEMICO = "academico"
    CATEGORIA_EMPRESARIAL = "empresarial"
    CATEGORIA_OTRO = "otro"

    CATEGORIAS = [
        (CATEGORIA_GENERAL, "General"),
        (CATEGORIA_CONFERENCIA, "Conferencia"),
        (CATEGORIA_TALLER, "Taller"),
        (CATEGORIA_CURSO, "Curso"),
        (CATEGORIA_FIESTA, "Fiesta"),
        (CATEGORIA_DEPORTIVO, "Deportivo"),
        (CATEGORIA_CULTURAL, "Cultural"),
        (CATEGORIA_ACADEMICO, "Académico"),
        (CATEGORIA_EMPRESARIAL, "Empresarial"),
        (CATEGORIA_OTRO, "Otro"),
    ]

    organizador = models.ForeignKey(User, on_delete=models.CASCADE)
    nombre_evento = models.CharField(max_length=100)
    lugar = models.CharField(max_length=150)
    fecha_evento = models.DateField()
    cupo_maximo = models.PositiveIntegerField()
    precio_persona = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    categoria = models.CharField(
        max_length=20, choices=CATEGORIAS, default=CATEGORIA_GENERAL
    )
    servicios = models.TextField(blank=True, null=True)
    descripcion = models.TextField(blank=True, null=True)
    codigo_invitacion = models.CharField(
        max_length=20, unique=True, default=generar_codigo_unico
    )
    activo = models.BooleanField(default=True)

    def reservaciones_activas(self):
        return self.reservaciones.exclude(estado=Reservacion.ESTADO_CANCELADA)

    def lugares_reservados(self):
        return (
            self.reservaciones_activas().aggregate(total=models.Sum("numero_personas"))[
                "total"
            ]
            or 0
        )

    def lugares_disponibles(self):
        return max(self.cupo_maximo - self.lugares_reservados(), 0)

    def porcentaje_ocupacion(self):
        if self.cupo_maximo <= 0:
            return 0

        return min(int((self.lugares_reservados() / self.cupo_maximo) * 100), 100)

    def total_reservaciones(self):
        return self.reservaciones_activas().count()

    def total_asistentes(self):
        return (
            self.reservaciones.filter(estado=Reservacion.ESTADO_ASISTIO).aggregate(
                total=models.Sum("numero_personas")
            )["total"]
            or 0
        )

    def total_ingresos_esperados(self):
        return sum(
            (reservacion.total_reservacion() for reservacion in self.reservaciones_activas()),
            Decimal("0.00"),
        )

    def total_ingresos_confirmados(self):
        return sum(
            (
                reservacion.total_reservacion()
                for reservacion in self.reservaciones.filter(
                    estado__in=[
                        Reservacion.ESTADO_PAGADA,
                        Reservacion.ESTADO_ASISTIO,
                    ]
                )
            ),
            Decimal("0.00"),
        )

    def total_pendiente_cobrar(self):
        return max(
            self.total_ingresos_esperados() - self.total_ingresos_confirmados(),
            Decimal("0.00"),
        )

    def reservaciones_pagadas(self):
        return self.reservaciones.filter(
            estado__in=[Reservacion.ESTADO_PAGADA, Reservacion.ESTADO_ASISTIO]
        ).count()

    def reservaciones_pendientes(self):
        return (
            self.reservaciones_activas()
            .exclude(estado__in=[Reservacion.ESTADO_PAGADA, Reservacion.ESTADO_ASISTIO])
            .count()
        )

    def alcanzo_ocupacion(self, porcentaje):
        return self.porcentaje_ocupacion() >= porcentaje

    def __str__(self):
        return self.nombre_evento


class ServicioExtra(models.Model):
    evento = models.ForeignKey(
        Evento, on_delete=models.CASCADE, related_name="servicios_extra"
    )
    nombre = models.CharField(max_length=80)
    descripcion = models.TextField(blank=True)
    precio = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    activo = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.nombre} - {self.evento.nombre_evento}"


class Reservacion(models.Model):
    ESTADO_PENDIENTE = "pendiente"
    ESTADO_CONFIRMADA = "confirmada"
    ESTADO_PAGADA = "pagada"
    ESTADO_CANCELADA = "cancelada"
    ESTADO_ASISTIO = "asistio"
    ESTADO_NO_ASISTIO = "no_asistio"

    ESTADOS = [
        (ESTADO_PENDIENTE, "Pendiente"),
        (ESTADO_CONFIRMADA, "Confirmada"),
        (ESTADO_PAGADA, "Pagada"),
        (ESTADO_CANCELADA, "Cancelada"),
        (ESTADO_ASISTIO, "Asistió"),
        (ESTADO_NO_ASISTIO, "No asistió"),
    ]

    MAX_PERSONAS_POR_RESERVACION = 10

    evento = models.ForeignKey(
        Evento, on_delete=models.CASCADE, related_name="reservaciones"
    )
    usuario = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="reservaciones"
    )
    nombre_cliente = models.CharField(max_length=100)
    hora_reserva = models.TimeField()
    numero_personas = models.PositiveIntegerField()
    estado = models.CharField(
        max_length=20, choices=ESTADOS, default=ESTADO_PENDIENTE
    )
    servicios_extra = models.ManyToManyField(
        ServicioExtra, blank=True, related_name="reservaciones"
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["evento", "usuario"],
                condition=~models.Q(estado="cancelada"),
                name="reservacion_activa_unica_por_usuario_evento",
            )
        ]

    def esta_cancelada(self):
        return self.estado == self.ESTADO_CANCELADA

    def cuenta_para_cupo(self):
        return not self.esta_cancelada()

    def subtotal_personas(self):
        return self.evento.precio_persona * self.numero_personas

    def total_servicios(self):
        return sum(
            (servicio.precio for servicio in self.servicios_extra.all()), Decimal("0.00")
        )

    def total_reservacion(self):
        if self.esta_cancelada():
            return Decimal("0.00")

        return self.subtotal_personas() + self.total_servicios()

    def __str__(self):
        return f"{self.nombre_cliente} - {self.evento.nombre_evento}"


class ActividadEvento(models.Model):
    evento = models.ForeignKey(
        Evento, on_delete=models.CASCADE, related_name="historial"
    )
    usuario = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="actividades_eventos",
    )
    mensaje = models.CharField(max_length=255)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha"]

    def __str__(self):
        return self.mensaje


class NotificacionInterna(models.Model):
    usuario = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="notificaciones"
    )
    mensaje = models.CharField(max_length=255)
    fecha = models.DateTimeField(auto_now_add=True)
    leida = models.BooleanField(default=False)
    enlace = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-fecha"]

    def marcar_leida(self):
        self.leida = True
        self.save(update_fields=["leida"])

    def __str__(self):
        return self.mensaje
