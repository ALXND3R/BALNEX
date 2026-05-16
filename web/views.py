from django.utils.decorators import method_decorator
from django.views.generic import TemplateView
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.views.decorators.cache import never_cache
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.db.models import Sum
from .models import Evento, Reservacion
from django.contrib.auth.mixins import LoginRequiredMixin

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone

from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.http import urlsafe_base64_decode
from django.utils.encoding import force_bytes
from django.utils.encoding import force_str


@method_decorator(never_cache, name="dispatch")
class VistaPaginaInicio(LoginRequiredMixin, TemplateView):
    template_name = "pagina_de_inicio.html"
    login_url = "/login/"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        eventos = Evento.objects.filter(organizador=self.request.user).order_by("-id")

        for evento in eventos:
            total_reservado = (
                evento.reservaciones.aggregate(total=Sum("numero_personas"))["total"]
                or 0
            )

            disponible = evento.cupo_maximo - total_reservado

            if evento.cupo_maximo > 0:
                porcentaje_ocupado = int((total_reservado / evento.cupo_maximo) * 100)
            else:
                porcentaje_ocupado = 0

            evento.total_reservado = total_reservado
            evento.disponible = disponible
            evento.porcentaje_ocupado = porcentaje_ocupado

        context["eventos"] = eventos

        context["mis_reservaciones"] = (
            Reservacion.objects.filter(usuario=self.request.user)
            .select_related("evento")
            .order_by("evento__fecha_evento")
        )

        return context


class VistaPaginaAcercaDe(TemplateView):
    template_name = "acerca_de.html"


@never_cache
def login_view(request):
    correo = request.GET.get("correo", "")

    if request.method == "POST":
        correo = request.POST.get("correo")
        password = request.POST.get("password")

        try:
            user_obj = User.objects.get(email=correo)
            user = authenticate(request, username=user_obj.username, password=password)
        except User.DoesNotExist:
            user = None

        if user:
            login(request, user)
            return redirect("pagina_de_inicio")
        else:
            return render(
                request, "login.html", {"error": "Datos incorrectos", "correo": correo}
            )

    return render(request, "login.html", {"correo": correo})


@never_cache
def register_view(request):
    if request.method == "POST":
        correo = request.POST.get("correo")
        password = request.POST.get("password")

        try:
            validate_email(correo)
        except ValidationError:
            return render(request, "register.html", {"error": "Correo no válido"})

        if not correo.endswith(("gmail.com", ".mx", ".edu", ".org")):
            return render(request, "register.html", {"error": "Dominio no permitido"})

        if User.objects.filter(email=correo).exists():
            return render(
                request, "register.html", {"error": "El correo ya está registrado"}
            )

        User.objects.create_user(username=correo, email=correo, password=password)
        messages.success(request, "Cuenta creada con exito.")

        url_login = reverse("login")
        return redirect(f"{url_login}?correo={correo}")

    return render(request, "register.html")


def logout_view(request):
    logout(request)
    return redirect("login")


@login_required
def detalle_y_reserva(request, evento_id):
    evento = get_object_or_404(Evento, id=evento_id)

    es_organizador = evento.organizador == request.user

    total_reservado = (
        evento.reservaciones.aggregate(total=Sum("numero_personas"))["total"] or 0
    )

    disponible = evento.cupo_maximo - total_reservado
    esta_lleno = disponible <= 0

    ya_reservo = Reservacion.objects.filter(
        evento=evento, usuario=request.user
    ).exists()

    if request.method == "POST":

        if es_organizador:
            messages.error(
                request, "Tú organizas este evento. No necesitas reservar un lugar."
            )
            return redirect("detalle_y_reserva", evento_id=evento.id)

        nombre_cliente = request.POST.get("nombre_cliente")
        hora_reserva = request.POST.get("hora_reserva")

        try:
            numero_personas = int(request.POST.get("numero_personas", 1))
        except ValueError:
            messages.error(request, "El número de personas no es válido.")
            return redirect("detalle_y_reserva", evento_id=evento.id)

        if numero_personas <= 0:
            messages.error(request, "El número de personas debe ser mayor a 0.")
            return redirect("detalle_y_reserva", evento_id=evento.id)

        if numero_personas > disponible:
            messages.error(
                request,
                f"No hay suficientes lugares disponibles. Solo quedan {disponible}.",
            )
            return redirect("detalle_y_reserva", evento_id=evento.id)

        reservacion_existente = Reservacion.objects.filter(
            evento=evento, usuario=request.user
        ).first()

        if reservacion_existente:
            reservacion_existente.numero_personas += numero_personas
            reservacion_existente.nombre_cliente = nombre_cliente
            reservacion_existente.hora_reserva = hora_reserva
            reservacion_existente.save()

            messages.success(request, "Tu reservación fue actualizada correctamente.")
        else:
            Reservacion.objects.create(
                evento=evento,
                usuario=request.user,
                nombre_cliente=nombre_cliente,
                numero_personas=numero_personas,
                hora_reserva=hora_reserva,
            )

            messages.success(request, "Asistencia confirmada correctamente.")

        return redirect("pagina_de_inicio")

    reservaciones = evento.reservaciones.all().order_by("hora_reserva")

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
        },
    )


@login_required
def crear_evento(request):
    lugares = [
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

    if request.method == "POST":
        nombre_evento = request.POST.get("nombre_evento")
        fecha_evento = request.POST.get("fecha_evento")
        cantidad_invitados = request.POST.get("cantidad_invitados")
        lugar = request.POST.get("lugar")
        descripcion = request.POST.get("descripcion")
        servicios = request.POST.getlist("servicios")

        Evento.objects.create(
            organizador=request.user,
            nombre_evento=nombre_evento,
            fecha_evento=fecha_evento,
            cupo_maximo=cantidad_invitados,
            lugar=lugar,
            descripcion=descripcion,
            servicios=", ".join(servicios),
        )

        messages.success(request, "Evento creado correctamente.")
        return redirect("pagina_de_inicio")

    return render(request, "crear_evento.html", {"lugares": lugares})


@login_required(login_url="/login/")
def buscar_evento(request):
    codigo = request.GET.get("codigo", "").strip().upper()

    if not codigo:
        messages.error(request, "Ingresa un código de invitación.")
        return redirect("pagina_de_inicio")

    evento = Evento.objects.filter(codigo_invitacion=codigo).first()

    if evento is None:
        messages.error(request, "No se encontró ningún evento con ese código.")
        return redirect("pagina_de_inicio")

    return redirect("detalle_y_reserva", evento_id=evento.id)


@login_required(login_url="/login/")
def eliminar_evento(request, evento_id):
    evento = get_object_or_404(Evento, id=evento_id, organizador=request.user)

    if request.method == "POST":
        evento.delete()
        messages.success(request, "Evento eliminado correctamente.")
        return redirect("pagina_de_inicio")

    messages.error(request, "No puedes eliminar este evento desde esa solicitud.")
    return redirect("pagina_de_inicio")


@login_required(login_url="/login/")
def cancelar_reservacion(request, reservacion_id):
    reservacion = get_object_or_404(
        Reservacion, id=reservacion_id, usuario=request.user
    )

    if request.method == "POST":
        reservacion.delete()
        messages.success(request, "Reservación cancelada correctamente.")
        return redirect("pagina_de_inicio")

    messages.error(request, "No puedes cancelar esta reservación desde esa solicitud.")
    return redirect("pagina_de_inicio")


@login_required(login_url="/login/")
def editar_reservacion(request, reservacion_id):
    reservacion = get_object_or_404(
        Reservacion.objects.select_related("evento"),
        id=reservacion_id,
        usuario=request.user,
    )

    evento = reservacion.evento
    total_reservado = (
        evento.reservaciones.aggregate(total=Sum("numero_personas"))["total"] or 0
    )
    lugares_disponibles = evento.cupo_maximo - total_reservado
    maximo_editable = lugares_disponibles + reservacion.numero_personas

    if request.method == "POST":
        nombre_cliente = request.POST.get("nombre_cliente", "").strip()
        hora_reserva = request.POST.get("hora_reserva", "").strip()

        try:
            numero_personas = int(request.POST.get("numero_personas", 1))
        except ValueError:
            messages.error(request, "El número de personas no es válido.")
            return redirect("editar_reservacion", reservacion_id=reservacion.id)

        if not nombre_cliente:
            messages.error(request, "El nombre es obligatorio.")
            return redirect("editar_reservacion", reservacion_id=reservacion.id)

        if not hora_reserva:
            messages.error(request, "La hora es obligatoria.")
            return redirect("editar_reservacion", reservacion_id=reservacion.id)

        if numero_personas <= 0:
            messages.error(request, "El número de personas debe ser mayor a 0.")
            return redirect("editar_reservacion", reservacion_id=reservacion.id)

        if numero_personas > maximo_editable:
            messages.error(
                request,
                f"No hay cupo suficiente. Puedes reservar máximo {maximo_editable} personas.",
            )
            return redirect("editar_reservacion", reservacion_id=reservacion.id)

        reservacion.nombre_cliente = nombre_cliente
        reservacion.hora_reserva = hora_reserva
        reservacion.numero_personas = numero_personas
        reservacion.save()

        messages.success(request, "Reservación actualizada correctamente.")
        return redirect("pagina_de_inicio")

    return render(
        request,
        "editar_reservacion.html",
        {
            "reservacion": reservacion,
            "evento": evento,
            "maximo_editable": maximo_editable,
        },
    )


@login_required(login_url="/login/")
def editar_evento(request, evento_id):
    evento = get_object_or_404(Evento, id=evento_id, organizador=request.user)

    lugares = [
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

    total_reservado = (
        evento.reservaciones.aggregate(total=Sum("numero_personas"))["total"] or 0
    )

    servicios_seleccionados = []

    if evento.servicios:
        servicios_seleccionados = [
            servicio.strip() for servicio in evento.servicios.split(",")
        ]

    cupo_minimo = max(total_reservado, 1)

    if request.method == "POST":
        nombre_evento = request.POST.get("nombre_evento", "").strip()
        fecha_evento = request.POST.get("fecha_evento", "").strip()
        cupo_maximo = request.POST.get("cupo_maximo", "").strip()
        lugar = request.POST.get("lugar", "").strip()
        descripcion = request.POST.get("descripcion", "").strip()
        servicios = request.POST.getlist("servicios")

        if not nombre_evento:
            messages.error(request, "El nombre del evento es obligatorio.")
            return redirect("editar_evento", evento_id=evento.id)

        if not fecha_evento:
            messages.error(request, "La fecha del evento es obligatoria.")
            return redirect("editar_evento", evento_id=evento.id)

        try:
            fecha_evento_convertida = timezone.datetime.strptime(
                fecha_evento, "%Y-%m-%d"
            ).date()
        except ValueError:
            messages.error(request, "La fecha del evento no es válida.")
            return redirect("editar_evento", evento_id=evento.id)

        if fecha_evento_convertida < timezone.localdate():
            messages.error(request, "No puedes poner una fecha anterior a la actual.")
            return redirect("editar_evento", evento_id=evento.id)

        if not cupo_maximo:
            messages.error(request, "El cupo máximo es obligatorio.")
            return redirect("editar_evento", evento_id=evento.id)

        try:
            cupo_maximo = int(cupo_maximo)
        except ValueError:
            messages.error(request, "El cupo máximo debe ser un número válido.")
            return redirect("editar_evento", evento_id=evento.id)

        if cupo_maximo <= 0:
            messages.error(request, "El cupo máximo debe ser mayor a 0.")
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

        evento.nombre_evento = nombre_evento
        evento.fecha_evento = fecha_evento_convertida
        evento.cupo_maximo = cupo_maximo
        evento.lugar = lugar
        evento.descripcion = descripcion
        evento.servicios = ", ".join(servicios)
        evento.save()

        messages.success(request, "Evento actualizado correctamente.")
        return redirect("pagina_de_inicio")

    return render(
        request,
        "editar_evento.html",
        {
            "evento": evento,
            "lugares": lugares,
            "total_reservado": total_reservado,
            "servicios_seleccionados": servicios_seleccionados,
            "cupo_minimo": cupo_minimo,
        },
    )


@never_cache
def recuperar_password(request):
    enlace_recuperacion = None
    correo = ""

    if request.method == "POST":
        correo = request.POST.get("correo", "").strip()

        try:
            usuario = User.objects.get(email=correo)

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
        nueva_password = request.POST.get("nueva_password", "").strip()
        confirmar_password = request.POST.get("confirmar_password", "").strip()

        if not nueva_password or not confirmar_password:
            messages.error(request, "Debes llenar ambos campos.")
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

        url_login = reverse("login")
        return redirect(f"{url_login}?correo={usuario.email}")

    return render(
        request,
        "cambiar_password.html",
        {
            "uidb64": uidb64,
            "token": token,
        },
    )
