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


@method_decorator(never_cache, name="dispatch")
class VistaPaginaInicio(LoginRequiredMixin, TemplateView):
    template_name = "pagina_de_inicio.html"
    login_url = "/login/"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["eventos"] = Evento.objects.filter(usuario=self.request.user).order_by(
            "-id"
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

        if not correo.endswith((".com", ".mx", ".edu", ".org")):
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


from django.utils import timezone


def detalle_y_reserva(request, id_evento):
    evento = get_object_or_404(Evento, pk=id_evento)

    asistentes = (
        Reservacion.objects.filter(evento=evento).aggregate(Sum("numero_personas"))[
            "numero_personas__sum"
        ]
        or 0
    )
    disponible = evento.cupo_maximo - asistentes
    ganancias = asistentes * 1500
    esta_lleno = disponible <= 0

    if request.method == "POST":
        nombre = request.POST.get("nombre_cliente")
        personas = int(request.POST.get("numero_personas", 0))
        hora_seleccionada = request.POST.get("hora_reserva")

        if 0 < personas <= disponible and hora_seleccionada:
            try:
                Reservacion.objects.create(
                    evento=evento,
                    nombre_cliente=nombre,
                    numero_personas=personas,
                    hora=hora_seleccionada,
                )
                messages.success(
                    request, f"¡Reserva confirmada para las {hora_seleccionada}!"
                )
            except Exception as e:
                messages.error(request, "Hubo un error al procesar tu reserva.")
        else:
            messages.error(request, "Datos inválidos o cupo insuficiente.")

        return redirect("detalle_y_reserva", id_evento=evento.id_evento)

    return render(
        request,
        "inicio.html",
        {
            "evento": evento,
            "disponible": disponible,
            "ganancias": ganancias,
            "esta_lleno": esta_lleno,
        },
    )


@login_required(login_url="/login/")
def crear_evento(request):

    lugares_disponibles = [
        "Salón Diamante",
        "Jardín Principal",
        "Terraza VIP",
        "Hacienda Balnex",
    ]

    if request.method == "POST":

        nombre = request.POST.get("nombre_evento")
        fecha = request.POST.get("fecha_evento")
        invitados = request.POST.get("cantidad_invitados")

        lugar_seleccionado = request.POST.get("lugar")
        descripcion = request.POST.get("descripcion")

        servicios_lista = request.POST.getlist("servicios")
        servicios_str = ", ".join(servicios_lista)

        Evento.objects.create(
            usuario=request.user,
            nombre_evento=nombre,
            fecha_evento=fecha,
            cupo_maximo=invitados,
            servicios=servicios_str,
            lugar=lugar_seleccionado,
            descripcion=descripcion,
        )

        messages.success(
            request, "¡Tu evento se ha configurado y guardado exitosamente!"
        )
        return redirect("pagina_de_inicio")

    contexto = {"lugares": lugares_disponibles}

    return render(request, "crear_evento.html", contexto)
