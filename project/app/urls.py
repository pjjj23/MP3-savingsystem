from django.urls import path
from . import views
# from django.conf.urls import handler404
from django.conf import settings

urlpatterns=[
    path('', views.load, name='load'),

    #Authentication folder
    path('authentication/', views.auth, name='auth'),
    path('verification/', views.verify, name='verify'),

    #User-dashboard
    path('user/dashboard/', views.userDashboard, name='userDashboard')
]