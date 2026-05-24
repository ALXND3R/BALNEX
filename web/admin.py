from django.contrib import admin
from .models import (
    ActividadEvento,
    Evento,
    NotificacionInterna,
    Reservacion,
    ServicioExtra,
)


@admin.register(Evento)
class EventoAdmin(admin.ModelAdmin):
    list_display = (
        "nombre_evento",
        "organizador",
        "categoria",
        "fecha_evento",
        "cupo_maximo",
        "precio_persona",
        "activo",
    )
    search_fields = ("nombre_evento", "codigo_invitacion", "lugar")
    list_filter = ("activo", "categoria", "fecha_evento")


@admin.register(Reservacion)
class ReservacionAdmin(admin.ModelAdmin):
    list_display = ("nombre_cliente", "evento", "usuario", "numero_personas", "estado")
    list_filter = ("estado", "evento")
    search_fields = ("nombre_cliente", "evento__nombre_evento", "usuario__username")


@admin.register(ServicioExtra)
class ServicioExtraAdmin(admin.ModelAdmin):
    list_display = ("nombre", "evento", "precio", "activo")
    list_filter = ("activo", "evento")


@admin.register(ActividadEvento)
class ActividadEventoAdmin(admin.ModelAdmin):
    list_display = ("evento", "usuario", "mensaje", "fecha")
    list_filter = ("evento", "fecha")


@admin.register(NotificacionInterna)
class NotificacionInternaAdmin(admin.ModelAdmin):
    list_display = ("usuario", "mensaje", "leida", "fecha")
    list_filter = ("leida", "fecha")
