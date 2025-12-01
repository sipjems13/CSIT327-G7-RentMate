from django.urls import path
from . import views

urlpatterns = [
    path('', views.home_view, name='home'),
    path('tenant_list/', views.tenant_list_view, name='tenant_list'),
    path('tenant/register/', views.tenant_register, name='tenant_register'),
    path('tenant/edit/<int:tenant_id>/', views.edit_tenant, name='edit_tenant'),
    path('tenant/delete/<int:tenant_id>/', views.delete_tenant, name='delete_tenant'),

    # Tenant Dashboard
    path('tenant-home/', views.tenant_home, name='tenant_home'),
    path('tenant-home/maintenance/', views.tenant_maintenance_add_view, name='tenant_maintenance'),
    path('tenant/payment/', views.tenant_payment, name='tenant_payment'),


    # Tenant Maintenance List/Edit/Delete
    path('tenant/maintenance/list/', views.tenant_maintenance_list_view, name='tenant_maintenance_list'),
    path('tenant/maintenance/edit/<int:request_id>/', views.tenant_maintenance_edit_view, name='tenant_maintenance_edit'),
    path('tenant/maintenance/delete/<int:request_id>/', views.tenant_maintenance_delete_view, name='tenant_maintenance_delete'),

    # Tenant Auth
    path('tenant/login/', views.tenant_login, name='tenant_login'),
    path("tenant/logout/", views.tenant_logout, name="tenant_logout"),
    path('tenant/change-password/', views.tenant_change_password, name='tenant_change_password'),

    #Landlord Tenants List
    path('tenant_list/tenant-profile/<int:tenant_id>/', views.landlord_tenant_profile_view, name='landlord_tenant_profile'),

    # Landlord Maintenance Management
    path('landlord/maintenance-list/', views.landlord_maintenance_list_view, name='landlord_maintenance_list'),
    path('landlord/maintenance-update/<int:request_id>/', views.landlord_maintenance_update_view, name='landlord_maintenance_update'),

    #LandLord Proof of Payments
    path('landlord/payments-list/', views.landlord_payments_list_view, name='landlord_payments_list'),
    path('landlord/payments-update/<int:payment_id>/', views.landlord_payments_update_view, name='landlord_payments_update'),
    path('landlord/payment-approve/<int:payment_id>', views.approve_payment, name='approve_payment'),
]
