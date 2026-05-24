from decimal import Decimal
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.views.decorators.cache import never_cache
from django.urls import reverse
from .models import (
    ActividadEvento,
    Evento,
    NotificacionInterna,
    Reservacion,
    ServicioExtra,
)
from django.contrib.auth.mixins import LoginRequiredMixin

from django.contrib.auth.decorators import login_required
from django.contrib import messages

from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.http import urlsafe_base64_decode
from django.utils.encoding import force_bytes
from django.utils.encoding import force_str
from .validation import (
    LIMITS,
    InputValidationError,
    clean_decimal,
    clean_email,
    clean_future_date,
    clean_id_list,
    clean_int,
    clean_invite_code,
    clean_optional_password,
    clean_password,
    clean_text,
    clean_time,
    clean_username,
)


LUGARES_EVENTO = [
    "Salón Diamante",
    "Hacienda Balnex",
    "Jardín Las Palmas",
    "Terraza del Mar",
    "Salón Imperial",
    "Quinta Los Olivos",
    "Centro de Convenciones",
    "Salón Vista Alegre",
    "Jardín Bugambilias",
    "Hotel Coral Marina",
]

SERVICIOS_PREDEFINIDOS = [
    ("Comida", "Servicio de alimentos para asistentes"),
    ("Bebidas", "Bebidas durante el evento"),
    ("Estacionamiento", "Acceso a estacionamiento"),
    ("Zona VIP", "Acceso preferente o zona especial"),
    ("Constancia", "Constancia digital o impresa"),
    ("Material incluido", "Material de apoyo para asistentes"),
]


def render_error(request, template_name, context, message, status=200):
    return render(request, template_name, {**context, "error": message}, status=status)


def safe_message_error(request, message, redirect_name, *args, **kwargs):
    messages.error(request, message)
    return redirect(redirect_name, *args, **kwargs)


def campo_servicio(nombre):
    return (
        nombre.lower()
        .replace(" ", "_")
        .replace("/", "_")
        .replace("á", "a")
        .replace("é", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ú", "u")
    )


def servicios_predefinidos_con_campo():
    return [
        {
            "nombre": nombre,
            "descripcion": descripcion,
            "campo": campo_servicio(nombre),
        }
        for nombre, descripcion in SERVICIOS_PREDEFINIDOS
    ]


def registrar_actividad(evento, usuario, mensaje):
    ActividadEvento.objects.create(evento=evento, usuario=usuario, mensaje=mensaje)


def crear_notificacion(usuario, mensaje, enlace=""):
    NotificacionInterna.objects.create(usuario=usuario, mensaje=mensaje, enlace=enlace)


def notificaciones_no_leidas(usuario):
    if not usuario.is_authenticated:
        return 0

    return usuario.notificaciones.filter(leida=False).count()


def revisar_notificacion_ocupacion(evento):
    if not evento.alcanzo_ocupacion(80):
        return

    mensaje = f"Tu evento {evento.nombre_evento} llegó al 80% de ocupación."
    ya_existe = NotificacionInterna.objects.filter(
        usuario=evento.organizador,
        mensaje=mensaje,
    ).exists()

    if not ya_existe:
        crear_notificacion(
            evento.organizador,
            mensaje,
            reverse("estadisticas_evento", kwargs={"evento_id": evento.id}),
        )


def resumen_evento(evento):
    total_reservado = evento.lugares_reservados()
    disponible = evento.lugares_disponibles()
    porcentaje_ocupado = evento.porcentaje_ocupacion()

    evento.total_reservado = total_reservado
    evento.disponible = disponible
    evento.porcentaje_ocupado = porcentaje_ocupado
    evento.total_esperado = evento.total_ingresos_esperados()
    evento.total_pagado = evento.total_ingresos_confirmados()
    evento.total_pendiente = evento.total_pendiente_cobrar()
    evento.reservaciones_pagadas_total = evento.reservaciones_pagadas()
    evento.reservaciones_pendientes_total = evento.reservaciones_pendientes()
    return evento


@method_decorator(never_cache, name="dispatch")
class VistaPaginaInicio(LoginRequiredMixin, TemplateView):
    template_name = "pagina_de_inicio.html"
    login_url = "/login/"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        try:
            categoria = clean_text(
                self.request.GET.get("categoria", ""),
                "La categoría",
                20,
            )
        except InputValidationError:
            categoria = ""
        eventos = Evento.objects.filter(
            organizador=self.request.user,
            activo=True,
        ).order_by("-id")

        if categoria and categoria in dict(Evento.CATEGORIAS):
            eventos = eventos.filter(categoria=categoria)
        elif categoria:
            categoria = ""

        context["eventos"] = [resumen_evento(evento) for evento in eventos]
        context["categorias"] = Evento.CATEGORIAS
        context["categoria_actual"] = categoria
        context["notificaciones_no_leidas"] = notificaciones_no_leidas(
            self.request.user
        )

        context["mis_reservaciones"] = (
            Reservacion.objects.filter(usuario=self.request.user)
            .exclude(estado=Reservacion.ESTADO_CANCELADA)
            .select_related("evento")
            .prefetch_related("servicios_extra")
            .order_by("evento__fecha_evento")
        )

        return context


class VistaPaginaAcercaDe(TemplateView):
    template_name = "acerca_de.html"


@never_cache
def login_view(request):
    username = ""

    if request.method == "POST":
        try:
            username = clean_text(
                request.POST.get("username"),
                "El usuario",
                LIMITS["username"],
                required=True,
                min_length=3,
            )
            password = clean_optional_password(request.POST.get("password"))
        except InputValidationError as exc:
            return render_error(
                request,
                "login.html",
                {"username": username},
                str(exc),
            )

        user = authenticate(request, username=username, password=password)

        if user:
            login(request, user)
            return redirect("pagina_de_inicio")

        return render(
            request,
            "login.html",
            {
                "error": "Usuario o contraseña incorrectos.",
                "username": username,
            },
        )

    return render(request, "login.html", {"username": username})


@never_cache
def register_view(request):
    if request.method == "POST":
        username = (request.POST.get("username") or "").strip()
        correo = (request.POST.get("correo") or "").strip().lower()
        contexto = {"username": username[: LIMITS["username"]], "correo": correo[: LIMITS["email"]]}

        try:
            username = clean_username(username)
            correo = clean_email(correo)
            password = clean_password(request.POST.get("password"))
            confirmar_password = clean_password(
                request.POST.get("confirmar_password"),
                "La confirmación de contraseña",
            )
            contexto = {"username": username, "correo": correo}
        except InputValidationError as exc:
            return render_error(request, "register.html", contexto, str(exc))

        if password != confirmar_password:
            return render_error(request, "register.html", contexto, "Las contraseñas no coinciden.")

        if not correo.endswith(("gmail.com", ".mx", ".edu", ".org")):
            return render_error(request, "register.html", contexto, "Dominio no permitido.")

        if User.objects.filter(username__iexact=username).exists():
            return render_error(request, "register.html", contexto, "El usuario ya está registrado.")

        if User.objects.filter(email__iexact=correo).exists():
            return render_error(request, "register.html", contexto, "El correo ya está registrado.")

        User.objects.create_user(username=username, email=correo, password=password)
        messages.success(request, "Cuenta creada con éxito. Inicia sesión con tu usuario.")

        return redirect("login")

    return render(request, "register.html")


def logout_view(request):
    logout(request)
    return redirect("login")


@login_required
def detalle_y_reserva(request, evento_id):
    evento = (
        Evento.objects.prefetch_related("servicios_extra", "historial")
        .filter(id=evento_id)
        .first()
    )

    if evento is None:
        messages.error(request, "El evento que intentas abrir no existe o ya no está disponible.")
        return redirect("pagina_de_inicio")

    es_organizador = evento.organizador == request.user
    eventos_permitidos = request.session.get("eventos_permitidos", [])

    total_reservado = evento.lugares_reservados()
    disponible = evento.lugares_disponibles()
    esta_lleno = disponible <= 0

    ya_reservo = Reservacion.objects.filter(
        evento=evento, usuario=request.user
    ).exclude(
        estado=Reservacion.ESTADO_CANCELADA
    ).exists()

    tiene_permiso_detalle = es_organizador or ya_reservo or evento.id in eventos_permitidos

    if not evento.activo:
        if request.method == "POST":
            messages.error(request, "Este evento fue cancelado y ya no acepta reservaciones.")
            return redirect("detalle_y_reserva", evento_id=evento.id)

        if not tiene_permiso_detalle:
            messages.error(request, "Este evento fue cancelado y ya no acepta reservaciones.")
            return redirect("pagina_de_inicio")

    if not tiene_permiso_detalle:
        messages.error(request, "Busca el evento con su código de invitación para verlo.")
        return redirect("pagina_de_inicio")

    if request.method == "POST":

        if es_organizador:
            messages.error(
                request, "Tú organizas este evento. No necesitas reservar un lugar."
            )
            return redirect("detalle_y_reserva", evento_id=evento.id)

        if ya_reservo:
            messages.error(
                request,
                "Ya tienes una reservación activa para este evento. Puedes editarla desde tu panel.",
            )
            return redirect("detalle_y_reserva", evento_id=evento.id)

        try:
            nombre_cliente = clean_text(
                request.POST.get("nombre_cliente"),
                "El nombre",
                100,
                required=True,
                min_length=2,
            )
            hora_reserva = clean_time(request.POST.get("hora_reserva"))
            numero_personas = clean_int(
                request.POST.get("numero_personas"),
                "El número de personas",
                min_value=1,
                max_value=Reservacion.MAX_PERSONAS_POR_RESERVACION,
            )
            servicios_ids = clean_id_list(
                request.POST.getlist("servicios_extra"),
                "Servicios extras",
            )
        except InputValidationError as exc:
            messages.error(request, str(exc))
            return redirect("detalle_y_reserva", evento_id=evento.id)

        if numero_personas > Reservacion.MAX_PERSONAS_POR_RESERVACION:
            messages.error(
                request,
                f"Solo puedes reservar máximo {Reservacion.MAX_PERSONAS_POR_RESERVACION} personas por reservación.",
            )
            return redirect("detalle_y_reserva", evento_id=evento.id)

        if numero_personas > disponible:
            messages.error(
                request,
                f"No hay suficientes lugares disponibles. Solo quedan {disponible}.",
            )
            return redirect("detalle_y_reserva", evento_id=evento.id)

        servicios_extra = ServicioExtra.objects.filter(
            id__in=servicios_ids, evento=evento, activo=True
        )

        reservacion = Reservacion.objects.create(
            evento=evento,
            usuario=request.user,
            nombre_cliente=nombre_cliente,
            numero_personas=numero_personas,
            hora_reserva=hora_reserva,
            estado=Reservacion.ESTADO_PENDIENTE,
        )
        reservacion.servicios_extra.set(servicios_extra)

        registrar_actividad(
            evento,
            request.user,
            f"Reservación creada para {numero_personas} persona(s).",
        )
        crear_notificacion(
            evento.organizador,
            f"{request.user.username} reservó {numero_personas} lugar(es) en {evento.nombre_evento}.",
            reverse("detalle_y_reserva", kwargs={"evento_id": evento.id}),
        )
        revisar_notificacion_ocupacion(evento)

        messages.success(
            request,
            f"Asistencia confirmada. Total de la reservación: ${reservacion.total_reservacion():.2f}.",
        )

        return redirect("pagina_de_inicio")

    reservaciones = []
    historial = []
    if es_organizador:
        reservaciones = (
            evento.reservaciones.select_related("usuario")
            .prefetch_related("servicios_extra")
            .order_by("hora_reserva")
        )
        historial = evento.historial.select_related("usuario")[:15]
    servicios_activos = evento.servicios_extra.filter(activo=True).order_by("nombre")
    max_personas_permitidas = min(
        disponible, Reservacion.MAX_PERSONAS_POR_RESERVACION
    )

    return render(
        request,
        "detalle_evento.html",
        {
            "evento": evento,
            "es_organizador": es_organizador,
            "total_reservado": total_reservado,
            "disponible": disponible,
            "esta_lleno": esta_lleno,
            "ya_reservo": ya_reservo,
            "reservaciones": reservaciones,
            "historial": historial,
            "servicios_activos": servicios_activos,
            "estados_reservacion": Reservacion.ESTADOS,
            "max_personas_reservacion": Reservacion.MAX_PERSONAS_POR_RESERVACION,
            "max_personas_permitidas": max_personas_permitidas,
            "notificaciones_no_leidas": notificaciones_no_leidas(request.user),
        },
    )


@login_required
def crear_evento(request):
    if request.method == "POST":
        try:
            nombre_evento = clean_text(
                request.POST.get("nombre_evento"),
                "El nombre del evento",
                LIMITS["event_name"],
                required=True,
                min_length=3,
            )
            fecha_evento = clean_future_date(request.POST.get("fecha_evento"))
            cantidad_invitados = clean_int(
                request.POST.get("cantidad_invitados"),
                "La cantidad de invitados",
                min_value=1,
                max_value=LIMITS["people"],
            )
            lugar = clean_text(
                request.POST.get("lugar"),
                "El lugar",
                LIMITS["place"],
                required=True,
            )
            categoria = clean_text(
                request.POST.get("categoria") or Evento.CATEGORIA_GENERAL,
                "La categoría",
                20,
                required=True,
            )
            precio_persona = clean_decimal(
                request.POST.get("precio_persona"),
                "El precio por persona",
            )
            descripcion = clean_text(
                request.POST.get("descripcion"),
                "La descripción",
                LIMITS["description"],
            )
            servicios = [
                clean_text(servicio, "El servicio", 50)
                for servicio in request.POST.getlist("servicios")[:20]
            ]
            servicios_extra = request.POST.getlist("servicios_extra")[:20]
            nombre_servicio_personalizado = clean_text(
                request.POST.get("nombre_servicio_personalizado"),
                "El nombre del servicio personalizado",
                LIMITS["service_name"],
            )
            descripcion_servicio_personalizado = clean_text(
                request.POST.get("descripcion_servicio_personalizado"),
                "La descripción del servicio personalizado",
                LIMITS["service_description"],
            )
            precio_servicio_personalizado = clean_decimal(
                request.POST.get("precio_servicio_personalizado"),
                "El precio del servicio personalizado",
            )
        except InputValidationError as exc:
            return safe_message_error(request, str(exc), "crear_evento")

        if categoria not in dict(Evento.CATEGORIAS):
            return safe_message_error(request, "Selecciona una categoría válida.", "crear_evento")

        if lugar not in LUGARES_EVENTO:
            return safe_message_error(request, "Selecciona un lugar válido.", "crear_evento")

        evento = Evento.objects.create(
            organizador=request.user,
            nombre_evento=nombre_evento,
            fecha_evento=fecha_evento,
            cupo_maximo=cantidad_invitados,
            lugar=lugar,
            categoria=categoria,
            precio_persona=precio_persona,
            descripcion=descripcion,
            servicios=", ".join(servicios),
        )

        for nombre, descripcion_servicio in SERVICIOS_PREDEFINIDOS:
            if nombre in servicios_extra:
                try:
                    precio = clean_decimal(
                        request.POST.get(f"precio_servicio_{campo_servicio(nombre)}"),
                        f"El precio de {nombre}",
                    )
                except InputValidationError as exc:
                    return safe_message_error(request, str(exc), "crear_evento")
                ServicioExtra.objects.create(
                    evento=evento,
                    nombre=nombre,
                    descripcion=descripcion_servicio,
                    precio=precio,
                    activo=True,
                )
                registrar_actividad(
                    evento, request.user, f"Servicio agregado: {nombre}."
                )

        if nombre_servicio_personalizado:
            ServicioExtra.objects.create(
                evento=evento,
                nombre=nombre_servicio_personalizado,
                descripcion=descripcion_servicio_personalizado,
                precio=precio_servicio_personalizado,
                activo=True,
            )
            registrar_actividad(
                evento,
                request.user,
                f"Servicio agregado: {nombre_servicio_personalizado}.",
            )

        registrar_actividad(evento, request.user, "Evento creado.")
        messages.success(request, "Evento creado correctamente.")
        return redirect("pagina_de_inicio")

    return render(
        request,
        "crear_evento.html",
        {
            "lugares": LUGARES_EVENTO,
            "categorias": Evento.CATEGORIAS,
            "servicios_predefinidos": servicios_predefinidos_con_campo(),
        },
    )


@login_required(login_url="/login/")
def buscar_evento(request):
    try:
        codigo = clean_invite_code(request.GET.get("codigo"))
    except InputValidationError as exc:
        messages.error(request, str(exc))
        return redirect("pagina_de_inicio")

    evento = Evento.objects.filter(codigo_invitacion=codigo).first()

    if evento is None:
        messages.error(request, "No se encontró ningún evento con ese código.")
        return redirect("pagina_de_inicio")

    eventos_permitidos = request.session.get("eventos_permitidos", [])
    if evento.id not in eventos_permitidos:
        eventos_permitidos.append(evento.id)
        request.session["eventos_permitidos"] = eventos_permitidos

    return redirect("detalle_y_reserva", evento_id=evento.id)


@login_required(login_url="/login/")
def eliminar_evento(request, evento_id):
    evento = get_object_or_404(Evento, id=evento_id, organizador=request.user)

    if request.method == "POST":
        if not evento.activo:
            messages.info(request, "Este evento ya estaba cancelado.")
            return redirect("pagina_de_inicio")

        evento.activo = False
        evento.save(update_fields=["activo"])
        registrar_actividad(evento, request.user, "Evento cancelado.")

        for reservacion in evento.reservaciones.exclude(
            estado=Reservacion.ESTADO_CANCELADA
        ).select_related("usuario"):
            crear_notificacion(
                reservacion.usuario,
                f"El evento {evento.nombre_evento} fue cancelado.",
                reverse("detalle_y_reserva", kwargs={"evento_id": evento.id}),
            )

        messages.success(request, "Evento cancelado correctamente. Se conserva el historial y sus reservaciones.")
        return redirect("pagina_de_inicio")

    messages.error(request, "No puedes cancelar este evento desde esa solicitud.")
    return redirect("pagina_de_inicio")


@login_required(login_url="/login/")
def cancelar_reservacion(request, reservacion_id):
    reservacion = get_object_or_404(
        Reservacion.objects.select_related("evento"),
        id=reservacion_id,
        usuario=request.user,
    )

    if request.method == "POST":
        reservacion.estado = Reservacion.ESTADO_CANCELADA
        reservacion.save(update_fields=["estado"])
        registrar_actividad(
            reservacion.evento,
            request.user,
            f"Reservación cancelada por {reservacion.nombre_cliente}.",
        )
        crear_notificacion(
            reservacion.evento.organizador,
            f"{request.user.username} canceló su reservación en {reservacion.evento.nombre_evento}.",
            reverse("detalle_y_reserva", kwargs={"evento_id": reservacion.evento.id}),
        )
        messages.success(request, "Reservación cancelada correctamente.")
        return redirect("pagina_de_inicio")

    messages.error(request, "No puedes cancelar esta reservación desde esa solicitud.")
    return redirect("pagina_de_inicio")


@login_required(login_url="/login/")
def editar_reservacion(request, reservacion_id):
    reservacion = get_object_or_404(
        Reservacion.objects.select_related("evento").prefetch_related("servicios_extra"),
        id=reservacion_id,
        usuario=request.user,
    )

    if reservacion.esta_cancelada():
        messages.error(request, "No puedes editar una reservación cancelada.")
        return redirect("pagina_de_inicio")

    evento = reservacion.evento

    if not evento.activo:
        messages.error(request, "No puedes editar una reservación de un evento cancelado.")
        return redirect("detalle_y_reserva", evento_id=evento.id)

    total_reservado = evento.lugares_reservados()
    lugares_disponibles = evento.cupo_maximo - total_reservado
    maximo_editable = min(
        lugares_disponibles + reservacion.numero_personas,
        Reservacion.MAX_PERSONAS_POR_RESERVACION,
    )

    if request.method == "POST":
        try:
            nombre_cliente = clean_text(
                request.POST.get("nombre_cliente"),
                "El nombre",
                100,
                required=True,
                min_length=2,
            )
            hora_reserva = clean_time(request.POST.get("hora_reserva"))
            numero_personas = clean_int(
                request.POST.get("numero_personas"),
                "El número de personas",
                min_value=1,
                max_value=maximo_editable,
            )
            servicios_ids = clean_id_list(
                request.POST.getlist("servicios_extra"),
                "Servicios extras",
            )
        except InputValidationError as exc:
            messages.error(request, str(exc))
            return redirect("editar_reservacion", reservacion_id=reservacion.id)

        if numero_personas > maximo_editable:
            messages.error(
                request,
                f"No hay cupo suficiente. Puedes reservar máximo {maximo_editable} personas.",
            )
            return redirect("editar_reservacion", reservacion_id=reservacion.id)

        servicios_extra = ServicioExtra.objects.filter(
            id__in=servicios_ids, evento=evento, activo=True
        )

        reservacion.nombre_cliente = nombre_cliente
        reservacion.hora_reserva = hora_reserva
        reservacion.numero_personas = numero_personas
        reservacion.save()
        reservacion.servicios_extra.set(servicios_extra)

        registrar_actividad(
            evento,
            request.user,
            f"Reservación editada para {numero_personas} persona(s).",
        )
        messages.success(request, "Reservación actualizada correctamente.")
        return redirect("pagina_de_inicio")

    servicios_activos = evento.servicios_extra.filter(activo=True).order_by("nombre")
    servicios_seleccionados = set(reservacion.servicios_extra.values_list("id", flat=True))

    return render(
        request,
        "editar_reservacion.html",
        {
            "reservacion": reservacion,
            "evento": evento,
            "maximo_editable": maximo_editable,
            "servicios_activos": servicios_activos,
            "servicios_seleccionados": servicios_seleccionados,
        },
    )


@login_required(login_url="/login/")
def editar_evento(request, evento_id):
    evento = get_object_or_404(Evento, id=evento_id, organizador=request.user)

    if not evento.activo:
        messages.error(request, "No puedes editar un evento cancelado.")
        return redirect("detalle_y_reserva", evento_id=evento.id)

    lugares = LUGARES_EVENTO
    total_reservado = evento.lugares_reservados()

    servicios_seleccionados = []

    if evento.servicios:
        servicios_seleccionados = [
            servicio.strip() for servicio in evento.servicios.split(",")
        ]

    cupo_minimo = max(total_reservado, 1)

    if request.method == "POST":
        try:
            nombre_evento = clean_text(
                request.POST.get("nombre_evento"),
                "El nombre del evento",
                LIMITS["event_name"],
                required=True,
                min_length=3,
            )
            fecha_evento_convertida = clean_future_date(request.POST.get("fecha_evento"))
            cupo_maximo = clean_int(
                request.POST.get("cupo_maximo"),
                "El cupo máximo",
                min_value=cupo_minimo,
                max_value=LIMITS["people"],
            )
            lugar = clean_text(
                request.POST.get("lugar"),
                "El lugar",
                LIMITS["place"],
                required=True,
            )
            categoria = clean_text(
                request.POST.get("categoria", Evento.CATEGORIA_GENERAL),
                "La categoría",
                20,
                required=True,
            )
            precio_persona = clean_decimal(
                request.POST.get("precio_persona"),
                "El precio por persona",
            )
            descripcion = clean_text(
                request.POST.get("descripcion"),
                "La descripción",
                LIMITS["description"],
            )
            servicios = [
                clean_text(servicio, "El servicio", 50)
                for servicio in request.POST.getlist("servicios")[:20]
            ]
            servicios_extra = request.POST.getlist("servicios_extra")[:20]
            nombre_servicio_personalizado = clean_text(
                request.POST.get("nombre_servicio_personalizado"),
                "El nombre del servicio personalizado",
                LIMITS["service_name"],
            )
            descripcion_servicio_personalizado = clean_text(
                request.POST.get("descripcion_servicio_personalizado"),
                "La descripción del servicio personalizado",
                LIMITS["service_description"],
            )
            precio_servicio_personalizado = clean_decimal(
                request.POST.get("precio_servicio_personalizado"),
                "El precio del servicio personalizado",
            )
        except InputValidationError as exc:
            messages.error(request, str(exc))
            return redirect("editar_evento", evento_id=evento.id)

        if cupo_maximo < total_reservado:
            messages.error(
                request,
                f"No puedes poner un cupo menor a los lugares ya reservados. Actualmente hay {total_reservado} lugares ocupados.",
            )
            return redirect("editar_evento", evento_id=evento.id)

        if cupo_maximo > 1000:
            messages.error(request, "El cupo máximo no puede ser mayor a 1000.")
            return redirect("editar_evento", evento_id=evento.id)

        if lugar not in lugares:
            messages.error(request, "Selecciona un lugar válido.")
            return redirect("editar_evento", evento_id=evento.id)

        if categoria not in dict(Evento.CATEGORIAS):
            messages.error(request, "Selecciona una categoría válida.")
            return redirect("editar_evento", evento_id=evento.id)

        evento.nombre_evento = nombre_evento
        evento.fecha_evento = fecha_evento_convertida
        evento.cupo_maximo = cupo_maximo
        evento.lugar = lugar
        evento.categoria = categoria
        evento.precio_persona = precio_persona
        evento.descripcion = descripcion
        evento.servicios = ", ".join(servicios)
        evento.save()

        for servicio in servicios_predefinidos_con_campo():
            nombre = servicio["nombre"]
            activo = nombre in servicios_extra
            try:
                precio = clean_decimal(
                    request.POST.get(f"precio_servicio_{servicio['campo']}"),
                    f"El precio de {nombre}",
                )
            except InputValidationError as exc:
                messages.error(request, str(exc))
                return redirect("editar_evento", evento_id=evento.id)
            servicio_obj, creado = ServicioExtra.objects.get_or_create(
                evento=evento,
                nombre=nombre,
                defaults={
                    "descripcion": servicio["descripcion"],
                    "precio": precio,
                    "activo": activo,
                },
            )

            if not creado:
                antes_activo = servicio_obj.activo
                servicio_obj.descripcion = servicio["descripcion"]
                servicio_obj.precio = precio
                servicio_obj.activo = activo
                servicio_obj.save()

                if activo and not antes_activo:
                    registrar_actividad(evento, request.user, f"Servicio agregado: {nombre}.")
                elif antes_activo and not activo:
                    registrar_actividad(evento, request.user, f"Servicio eliminado: {nombre}.")
            elif activo:
                registrar_actividad(evento, request.user, f"Servicio agregado: {nombre}.")

        nombres_predefinidos = [nombre for nombre, _ in SERVICIOS_PREDEFINIDOS]
        for servicio_obj in evento.servicios_extra.exclude(nombre__in=nombres_predefinidos):
            antes_activo = servicio_obj.activo
            servicio_obj.activo = (
                request.POST.get(f"servicio_personalizado_activo_{servicio_obj.id}")
                == "on"
            )
            try:
                servicio_obj.descripcion = clean_text(
                    request.POST.get(
                        f"servicio_personalizado_descripcion_{servicio_obj.id}"
                    ),
                    "La descripción del servicio personalizado",
                    LIMITS["service_description"],
                )
                servicio_obj.precio = clean_decimal(
                    request.POST.get(
                        f"servicio_personalizado_precio_{servicio_obj.id}"
                    ),
                    f"El precio de {servicio_obj.nombre}",
                )
            except InputValidationError as exc:
                messages.error(request, str(exc))
                return redirect("editar_evento", evento_id=evento.id)
            servicio_obj.save()

            if servicio_obj.activo and not antes_activo:
                registrar_actividad(
                    evento, request.user, f"Servicio agregado: {servicio_obj.nombre}."
                )
            elif antes_activo and not servicio_obj.activo:
                registrar_actividad(
                    evento, request.user, f"Servicio eliminado: {servicio_obj.nombre}."
                )

        if nombre_servicio_personalizado:
            ServicioExtra.objects.create(
                evento=evento,
                nombre=nombre_servicio_personalizado,
                descripcion=descripcion_servicio_personalizado,
                precio=precio_servicio_personalizado,
                activo=True,
            )
            registrar_actividad(
                evento,
                request.user,
                f"Servicio agregado: {nombre_servicio_personalizado}.",
            )

        registrar_actividad(evento, request.user, "Evento editado.")
        messages.success(request, "Evento actualizado correctamente.")
        return redirect("pagina_de_inicio")

    servicios_extra_actuales = {
        servicio.nombre: servicio for servicio in evento.servicios_extra.all()
    }
    nombres_predefinidos = [nombre for nombre, _ in SERVICIOS_PREDEFINIDOS]
    servicios_extra_personalizados = evento.servicios_extra.exclude(
        nombre__in=nombres_predefinidos
    ).order_by("nombre")
    servicios_extra_form = []

    for servicio in servicios_predefinidos_con_campo():
        existente = servicios_extra_actuales.get(servicio["nombre"])
        servicios_extra_form.append(
            {
                **servicio,
                "activo": existente.activo if existente else False,
                "precio": existente.precio if existente else Decimal("0.00"),
            }
        )

    return render(
        request,
        "editar_evento.html",
        {
            "evento": evento,
            "lugares": lugares,
            "categorias": Evento.CATEGORIAS,
            "total_reservado": total_reservado,
            "servicios_seleccionados": servicios_seleccionados,
            "servicios_extra_form": servicios_extra_form,
            "servicios_extra_personalizados": servicios_extra_personalizados,
            "cupo_minimo": cupo_minimo,
        },
    )


@login_required(login_url="/login/")
def estadisticas_evento(request, evento_id):
    evento = get_object_or_404(Evento, id=evento_id, organizador=request.user)
    evento = resumen_evento(evento)

    return render(
        request,
        "estadisticas_evento.html",
        {
            "evento": evento,
            "total_reservaciones": evento.total_reservaciones(),
            "total_asistentes": evento.total_asistentes(),
            "total_ingresos_esperados": evento.total_ingresos_esperados(),
            "total_ingresos_confirmados": evento.total_ingresos_confirmados(),
            "total_pendiente_cobrar": evento.total_pendiente_cobrar(),
            "reservaciones_pagadas": evento.reservaciones_pagadas(),
            "reservaciones_pendientes": evento.reservaciones_pendientes(),
            "historial": evento.historial.select_related("usuario")[:20],
            "notificaciones_no_leidas": notificaciones_no_leidas(request.user),
        },
    )


@login_required(login_url="/login/")
def actualizar_estado_reservacion(request, reservacion_id):
    reservacion = get_object_or_404(
        Reservacion.objects.select_related("evento", "usuario"),
        id=reservacion_id,
        evento__organizador=request.user,
    )
    evento = reservacion.evento

    if request.method != "POST":
        messages.error(request, "No puedes cambiar el estado desde esa solicitud.")
        return redirect("detalle_y_reserva", evento_id=evento.id)

    try:
        nuevo_estado = clean_text(request.POST.get("estado"), "El estado", 20, required=True)
    except InputValidationError as exc:
        messages.error(request, str(exc))
        return redirect("detalle_y_reserva", evento_id=evento.id)
    estados_validos = dict(Reservacion.ESTADOS)

    if nuevo_estado not in estados_validos:
        messages.error(request, "Selecciona un estado válido.")
        return redirect("detalle_y_reserva", evento_id=evento.id)

    estado_anterior = reservacion.estado
    reservacion.estado = nuevo_estado
    reservacion.save(update_fields=["estado"])

    mensaje_estado = estados_validos[nuevo_estado].lower()
    registrar_actividad(
        evento,
        request.user,
        f"Reservación de {reservacion.nombre_cliente} marcada como {mensaje_estado}.",
    )

    if nuevo_estado == Reservacion.ESTADO_PAGADA:
        crear_notificacion(
            reservacion.usuario,
            f"Tu pago para {evento.nombre_evento} fue confirmado.",
            reverse("detalle_y_reserva", kwargs={"evento_id": evento.id}),
        )
        registrar_actividad(
            evento,
            request.user,
            f"Reservación marcada como pagada: {reservacion.nombre_cliente}.",
        )

    if nuevo_estado == Reservacion.ESTADO_ASISTIO:
        registrar_actividad(
            evento,
            request.user,
            f"Reservación marcada como asistió: {reservacion.nombre_cliente}.",
        )

    if nuevo_estado == Reservacion.ESTADO_CANCELADA and estado_anterior != nuevo_estado:
        crear_notificacion(
            reservacion.usuario,
            f"Tu reservación para {evento.nombre_evento} fue marcada como cancelada.",
            reverse("detalle_y_reserva", kwargs={"evento_id": evento.id}),
        )

    revisar_notificacion_ocupacion(evento)
    messages.success(request, "Estado de reservación actualizado.")
    return redirect("detalle_y_reserva", evento_id=evento.id)


@login_required(login_url="/login/")
def notificaciones(request):
    return render(
        request,
        "notificaciones.html",
        {
            "notificaciones": request.user.notificaciones.all(),
            "notificaciones_no_leidas": notificaciones_no_leidas(request.user),
        },
    )


@login_required(login_url="/login/")
def marcar_notificacion_leida(request, notificacion_id):
    notificacion = get_object_or_404(
        NotificacionInterna, id=notificacion_id, usuario=request.user
    )

    if request.method == "POST":
        notificacion.marcar_leida()
        if notificacion.enlace:
            return redirect(notificacion.enlace)

    return redirect("notificaciones")


@login_required(login_url="/login/")
def marcar_todas_notificaciones_leidas(request):
    if request.method == "POST":
        request.user.notificaciones.filter(leida=False).update(leida=True)

    return redirect("notificaciones")


@never_cache
def recuperar_password(request):
    enlace_recuperacion = None
    correo = ""

    if request.method == "POST":
        try:
            correo = clean_email(request.POST.get("correo"))
        except InputValidationError as exc:
            messages.error(request, str(exc))
            return render(
                request,
                "recuperar_password.html",
                {"correo": correo[: LIMITS["email"]], "enlace_recuperacion": enlace_recuperacion},
            )

        try:
            usuario = User.objects.get(email__iexact=correo)

            uid = urlsafe_base64_encode(force_bytes(usuario.pk))
            token = default_token_generator.make_token(usuario)

            enlace_recuperacion = reverse(
                "cambiar_password", kwargs={"uidb64": uid, "token": token}
            )

        except User.DoesNotExist:
            messages.error(request, "No existe una cuenta registrada con ese correo.")

    return render(
        request,
        "recuperar_password.html",
        {"correo": correo, "enlace_recuperacion": enlace_recuperacion},
    )


@never_cache
def cambiar_password(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        usuario = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        usuario = None

    if usuario is None or not default_token_generator.check_token(usuario, token):
        messages.error(request, "El enlace no es válido o ya fue utilizado.")
        return redirect("recuperar_password")

    if request.method == "POST":
        try:
            nueva_password = clean_password(
                request.POST.get("nueva_password"),
                "La nueva contraseña",
            )
            confirmar_password = clean_password(
                request.POST.get("confirmar_password"),
                "La confirmación de contraseña",
            )
        except InputValidationError as exc:
            messages.error(request, str(exc))
            return redirect("cambiar_password", uidb64=uidb64, token=token)

        if nueva_password != confirmar_password:
            messages.error(request, "Las contraseñas no coinciden.")
            return redirect("cambiar_password", uidb64=uidb64, token=token)

        usuario.set_password(nueva_password)
        usuario.save()

        messages.success(
            request,
            "Tu contraseña se cambió correctamente. Ahora puedes iniciar sesión.",
        )

        return redirect("login")

    return render(
        request,
        "cambiar_password.html",
        {
            "uidb64": uidb64,
            "token": token,
        },
    )
