from django.urls import path
from . import views
# from django.conf.urls import handler404
from django.conf import settings

urlpatterns=[
    path('', views.load, name='load'),
    path('logout/', views.logout, name='logout'),
    path('admin_logout/', views.admin_logout, name='admin_logout'),

    #Authentication folder
    path('authentication/', views.auth_view, name='auth_view'),
    path('verification/', views.verify, name='verify'),

    #User-dashboard
    path('user/dashboard/', views.userDashboard, name='userDashboard'),
    path("api/transaction-records/", views.api_transaction_records, name="api_transaction_records"),
    path('api/interest-records/', views.get_interest_records, name='get_interest_records'),
    path('user/deposit/', views.deposit, name='deposit'),
    path('user/process_deposit/', views.process_deposit, name='process_deposit'),
    path('user/payment/', views.payment, name='payment'),
    path('user/record/', views.record, name='record'),
    path('user/withdrawal/', views.withdrawal, name='withdrawal'),
    path('user/process_withdrawal/', views.process_withdrawal, name='process_withdrawal'),
    path('user/loan/', views.loan, name='loan'),
    path('user/save-contact-info/', views.save_contact_info, name='save_contact_info'),
    path('user/submit-loan/', views.submit_loan_application, name='submit_loan'),


    #Admin-dashboard
    path('admin-sss/login/', views.admin_auth, name='admin_auth'),
    path('admin-dashboard/login/', views.admin_login, name='admin_login'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin-dashboard/reports/', views.reports, name='reports'),
    path('admin-dashboard/savings/', views.admin_savings_view, name='admin_savings'),
    path('admin-dashboard/activate_interest/<str:saving_id>/', views.activate_interest, name='activate_interest'),
    path('admin-dashboard/loan-approvals/', views.loan_approvals, name='loan_approvals'),
    path('admin-dashboard/approve-loan/', views.approve_loan, name='approve_loan'),
]