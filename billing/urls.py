from django.urls import path
from . import views

urlpatterns = [
    # Core Dashboards
    path('', views.dashboard, name='dashboard'),
    path('customer/portal/', views.customer_portal, name='customer_portal'),
    
    # Authentications
    path('login/customer/', views.customer_login, name='customer_login'),
    path('login/staff/', views.staff_login, name='staff_login'),
    path('login/manager/', views.manager_login, name='manager_login'),
    path('logout/', views.logout_view, name='logout_view'),
    
    # Customer Actions
    path('customer/book-room/', views.customer_book_room, name='customer_book_room'),
    path('customer/order-food/', views.customer_order_food, name='customer_order_food'),
    path('customer/orders/<int:pk>/status/', views.customer_order_status, name='customer_order_status'),
    path('customer/verify-otp/', views.customer_verify_otp, name='customer_verify_otp'),
    
    # Rooms & Inventories
    path('rooms/', views.room_list, name='room_list'),
    path('rooms/add/', views.room_add, name='room_add'),
    path('rooms/<int:pk>/release/', views.room_release, name='room_release'),
    
    # Invoices & Ledgers
    path('invoices/', views.invoice_list, name='invoice_list'),
    path('invoices/create/', views.invoice_create, name='invoice_create'),
    path('invoices/<int:pk>/', views.invoice_detail, name='invoice_detail'),
    path('invoices/<int:pk>/pay/', views.invoice_pay, name='invoice_pay'),
    path('invoices/<int:pk>/delete/', views.invoice_delete, name='invoice_delete'),
    path('invoices/<int:pk>/send-print-otp/', views.invoice_send_print_otp, name='invoice_send_print_otp'),
    path('invoices/<int:pk>/verify-print-otp/', views.invoice_verify_print_otp, name='invoice_verify_print_otp'),
    path('invoices/<int:pk>/print/', views.invoice_print_view, name='invoice_print_view'),
    path('customer/invoices/<int:pk>/cancel/', views.customer_cancel_booking, name='customer_cancel_booking'),
    path('customer/requests/<int:pk>/cancel/', views.customer_cancel_request, name='customer_cancel_request'),
]
