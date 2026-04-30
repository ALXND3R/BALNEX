from django.db import transaction
from django.db.models import Sum
from .models import Evento, Reservacion

def calcular_ocupados(evento):

    resultado = evento.reservacion_set.aggregate(total=Sum('numero_personas'))
    return resultado['total'] or 0

def hay_cupo(evento, personas):
    ocupados = calcular_ocupados(evento)
    return (ocupados + personas) <= evento.cupo_maximo

@transaction.atomic
def crear_reservacion(evento_id, nombre, personas):
    if personas <= 0:
        raise ValueError("El número de personas debe ser mayor a 0.")

    try:

        evento = Evento.objects.select_for_update().get(id=evento_id)
    except Evento.DoesNotExist:
        raise ValueError("El evento no existe.")

    if not hay_cupo(evento, personas):
        raise ValueError("El evento está lleno o no tiene cupo suficiente.")

    return Reservacion.objects.create(
        nombre_cliente=nombre,
        numero_personas=personas,
        evento=evento
    )

@transaction.atomic
def editar_reservacion(reservacion_id, personas):
    if personas <= 0:
        raise ValueError("El número de personas debe ser mayor a 0.")

    try:

        r = Reservacion.objects.select_related('evento').get(id=reservacion_id)

        evento = Evento.objects.select_for_update().get(id=r.evento.id)
    except Reservacion.DoesNotExist:
        raise ValueError("La reservación no existe.")

    ocupados_sin_esta_reserva = calcular_ocupados(evento) - r.numero_personas

    if (ocupados_sin_esta_reserva + personas) > evento.cupo_maximo:
        raise ValueError("No hay cupo suficiente para aumentar las personas.")

    r.numero_personas = personas
    r.save()
    return r

def eliminar_reservacion(reservacion_id):
    try:
        r = Reservacion.objects.get(id=reservacion_id)
        r.delete()
    except Reservacion.DoesNotExist:
        raise ValueError("La reservación no existe.")