from django.views.generic import TemplateView
from django.shortcuts import render, redirect

class VistaPaginaInicio(TemplateView):
    template_name = "pagina_de_inicio.html"

class VistaPaginaAcercaDe(TemplateView):
    template_name = "acerca_de.html"

def login_view(request):
    error = ""

    if request.method == "POST":
        correo = request.POST.get("correo")
        password = request.POST.get("password")

        if correo == "prueba@gmail.com" and password == "1234567":
            return redirect('pagina_de_inicio')
        else:
            error = "Datos incorrectos"

    return render(request, "login.html", {"error": error})