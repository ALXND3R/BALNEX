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


@method_decorator(never_cache, name="dispatch")
class VistaPaginaInicio(LoginRequiredMixin, TemplateView):
    template_name = "pagina_de_inicio.html"
    login_url = "/login/"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["eventos"] = Evento.objects.filter(
            organizador=self.request.user
        ).order_by("-id")

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

        url_login = reverse("login")
        return redirect(f"{url_login}?correo={correo}")

    return render(request, "register.html")


def logout_view(request):
    logout(request)
    return redirect("login")


def gestion_eventos(request):

    eventos = Evento.objects.all()
    return render(request, "inicio.html", {"eventos": eventos})


@login_required
def detalle_y_reserva(request, evento_id):
    evento = get_object_or_404(Evento, id=evento_id)

    es_organizador = evento.organizador == request.user

    total_reservado = sum(
        reservacion.numero_personas for reservacion in evento.reservaciones.all()
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

        if ya_reservo:
            messages.error(request, "Ya reservaste un lugar en este evento.")
            return redirect("detalle_y_reserva", evento_id=evento.id)

        nombre_cliente = request.POST.get("nombre_cliente")
        numero_personas = int(request.POST.get("numero_personas"))
        hora_reserva = request.POST.get("hora_reserva")

        if numero_personas > disponible:
            messages.error(request, "No hay suficientes lugares disponibles.")
            return redirect("detalle_y_reserva", evento_id=evento.id)

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
    evento = get_object_or_404(
        Evento,
        id=evento_id,
        organizador=request.user
    )

    if request.method == "POST":
        evento.delete()
        messages.success(request, "Evento eliminado correctamente.")
        return redirect("pagina_de_inicio")

    messages.error(request, "No puedes eliminar este evento desde esa solicitud.")
    return redirect("pagina_de_inicio")