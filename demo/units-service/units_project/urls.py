"""Routes de units-service (démo)."""
from django.urls import path

from units_project import views

urlpatterns = [
    path("sante/", views.sante, name="sante"),
    path("demo/commande", views.creer_commande, name="creer_commande"),
    path("demo/erreur", views.erreur, name="erreur"),
    path("demo/calcul", views.calcul, name="calcul"),
]
