from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import Room, Invoice, InvoiceItem, UserProfile, BookingRequest, FoodOrder

class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'User Profiles'

class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)

admin.site.unregister(User)
admin.site.register(User, UserAdmin)

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'phone')
    list_filter = ('role',)
    search_fields = ('user__username', 'phone')


class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 1

@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('room_number', 'category', 'price_per_night', 'status')
    list_filter = ('category', 'status')
    search_fields = ('room_number',)

@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('invoice_number', 'customer_name', 'room', 'check_in_date', 'check_out_date', 'grand_total', 'payment_status')
    list_filter = ('payment_status', 'payment_method', 'created_at')
    search_fields = ('invoice_number', 'customer_name', 'customer_email', 'customer_phone')
    inlines = [InvoiceItemInline]
    readonly_fields = ('invoice_number', 'room_charges', 'extra_charges', 'tax_amount', 'grand_total', 'created_at')
    
    fieldsets = (
        ('Customer Info', {
            'fields': ('customer_name', 'customer_email', 'customer_phone')
        }),
        ('Stay Details', {
            'fields': ('room', 'check_in_date', 'check_out_date')
        }),
        ('Financials', {
            'fields': ('room_charges', 'extra_charges', 'discount', 'tax_rate', 'tax_amount', 'grand_total')
        }),
        ('Payment', {
            'fields': ('payment_method', 'payment_status')
        }),
        ('Metadata', {
            'fields': ('invoice_number', 'created_at')
        }),
    )

@admin.register(InvoiceItem)
class InvoiceItemAdmin(admin.ModelAdmin):
    list_display = ('invoice', 'description', 'amount')
    search_fields = ('description', 'invoice__invoice_number')


@admin.register(BookingRequest)
class BookingRequestAdmin(admin.ModelAdmin):
    list_display = ('customer', 'room', 'check_in_date', 'check_out_date', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('customer__username', 'room__room_number')


@admin.register(FoodOrder)
class FoodOrderAdmin(admin.ModelAdmin):
    list_display = ('customer', 'room_number', 'item_name', 'quantity', 'total_price', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('customer__username', 'item_name', 'room_number')

