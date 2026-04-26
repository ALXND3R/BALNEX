from django.urls import path
from .views import VistaPaginaInicio,VistaPaginaAcercaDe,login_view

urlpatterns = [
    path('', login_view, name='login'),
    path('inicio/', VistaPaginaInicio.as_view(), name='pagina_de_inicio'),
    path('acerca de/',VistaPaginaAcercaDe.as_view(), name='acerca_de'),
]