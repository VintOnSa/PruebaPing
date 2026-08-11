from django.contrib import admin
from django.urls import path
from . import views


urlpatterns = [
    path('', views.cDash, name='Inicio'),
    path('escanear/', views.Escaner, name='Escaner'),
    path('ping/', views.Ping, name='Ping'),
    path("diagnostico/", views.Diagnostico, name="Diagnostico"),
    path("ping-individual/", views.PingIndividual, name="PingIndividual"),
]
