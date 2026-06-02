import uuid
from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User

class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('Customer', 'Customer'),
        ('Staff', 'Staff'),
        ('Manager', 'Manager'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='Customer')
    phone = models.CharField(max_length=20, blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} ({self.role})"


class Room(models.Model):
    CATEGORY_CHOICES = [
        ('Standard', 'Standard'),
        ('Deluxe', 'Deluxe'),
        ('Suite', 'Suite'),
    ]
    STATUS_CHOICES = [
        ('Available', 'Available'),
        ('Occupied', 'Occupied'),
        ('Cleaning', 'Cleaning'),
    ]

    room_number = models.CharField(max_length=20, unique=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    price_per_night = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Available')

    def __str__(self):
        return f"Room {self.room_number} ({self.category})"

    class Meta:
        ordering = ['room_number']


class Invoice(models.Model):
    PAYMENT_METHOD_CHOICES = [
        ('Cash', 'Cash'),
        ('Card', 'Card'),
        ('UPI', 'UPI'),
        ('Net Banking', 'Net Banking'),
    ]
    PAYMENT_STATUS_CHOICES = [
        ('Paid', 'Paid'),
        ('Pending', 'Pending'),
    ]

    invoice_number = models.CharField(max_length=50, unique=True, blank=True)
    customer_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='invoices')
    customer_name = models.CharField(max_length=100)
    customer_email = models.EmailField(blank=True, null=True)
    customer_phone = models.CharField(max_length=20, blank=True, null=True)
    room = models.ForeignKey(Room, on_delete=models.SET_NULL, null=True, blank=True)
    check_in_date = models.DateField()
    check_out_date = models.DateField()
    room_charges = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    extra_charges = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=12.00) # Percent
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    grand_total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='Cash')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='Pending')
    verification_photo = models.TextField(blank=True, null=True)
    id_proof = models.FileField(upload_to='id_proofs/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def nights_count(self):
        if self.check_out_date and self.check_in_date:
            diff = (self.check_out_date - self.check_in_date).days
            return max(1, diff)
        return 1

    def calculate_totals(self, save_invoice=False):
        from decimal import Decimal
        # Coerce values to Decimal to prevent float/decimal mismatch TypeErrors
        room_charges = Decimal(str(self.room_charges))
        extra_charges = Decimal(str(self.extra_charges))
        discount = Decimal(str(self.discount))
        tax_rate = Decimal(str(self.tax_rate))

        # 1. Room Charges
        if self.room and room_charges == Decimal('0.00'):
            room_charges = Decimal(str(self.room.price_per_night)) * self.nights_count
            self.room_charges = room_charges

        # 2. Extra Charges from related items
        if self.pk:
            extra_sum = self.items.aggregate(models.Sum('amount'))['amount__sum'] or Decimal('0.00')
            extra_charges = Decimal(str(extra_sum))
            self.extra_charges = extra_charges

        # 3. Tax and Grand Total
        subtotal = (room_charges + extra_charges) - discount
        tax_amount = subtotal * (tax_rate / Decimal('100.00'))
        
        self.tax_amount = tax_amount
        self.grand_total = subtotal + tax_amount

        if save_invoice:
            super().save(update_fields=['room_charges', 'extra_charges', 'tax_amount', 'grand_total'])

    def save(self, *args, **kwargs):
        from decimal import Decimal
        # Generate custom invoice number if not present
        if not self.invoice_number:
            date_str = timezone.now().strftime("%Y%m%d")
            # Get count of invoices today to construct sequential suffix
            today_count = Invoice.objects.filter(created_at__date=timezone.now().date()).count() + 1
            self.invoice_number = f"INV-{date_str}-{today_count:04d}"

        # Coerce fields to Decimal
        room_charges = Decimal(str(self.room_charges))
        extra_charges = Decimal(str(self.extra_charges))
        discount = Decimal(str(self.discount))
        tax_rate = Decimal(str(self.tax_rate))

        # Preliminary totals calculation
        subtotal = (room_charges + extra_charges) - discount
        self.tax_amount = subtotal * (tax_rate / Decimal('100.00'))
        self.grand_total = subtotal + self.tax_amount

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.invoice_number} - {self.customer_name}"

    class Meta:
        ordering = ['-created_at']


class InvoiceItem(models.Model):
    invoice = models.ForeignKey(Invoice, related_name='items', on_delete=models.CASCADE)
    description = models.CharField(max_length=150)
    amount = models.DecimalField(max_digits=10, decimal_places=2)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Recalculate invoice totals when an item is saved
        self.invoice.calculate_totals(save_invoice=True)

    def delete(self, *args, **kwargs):
        invoice = self.invoice
        super().delete(*args, **kwargs)
        # Recalculate invoice totals when an item is deleted
        invoice.calculate_totals(save_invoice=True)

    def __str__(self):
        return f"{self.description} ({self.amount})"


# Signals to automatically create UserProfile when a User is created
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.get_or_create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        instance.profile.save()
    else:
        UserProfile.objects.get_or_create(user=instance)


class BookingRequest(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Rejected', 'Rejected'),
    ]

    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='booking_requests')
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='booking_requests')
    check_in_date = models.DateField()
    check_out_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    num_guests = models.PositiveIntegerField(default=1)
    rejection_reason = models.CharField(max_length=255, blank=True, null=True)
    id_proof = models.FileField(upload_to='id_proofs/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def nights_count(self):
        if self.check_out_date and self.check_in_date:
            diff = (self.check_out_date - self.check_in_date).days
            return max(1, diff)
        return 1

    @property
    def estimated_total(self):
        from decimal import Decimal
        if self.room:
            return Decimal(str(self.room.price_per_night)) * self.nights_count
        return Decimal('0.00')

    def __str__(self):
        return f"{self.customer.username} - Room {self.room.room_number} ({self.status})"

    class Meta:
        ordering = ['-created_at']


class FoodOrder(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Delivered', 'Delivered'),
    ]

    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='food_orders')
    room_number = models.CharField(max_length=20, blank=True, null=True)
    item_name = models.CharField(max_length=100)
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        from decimal import Decimal
        self.total_price = Decimal(str(self.price)) * self.quantity
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.customer.username} - {self.item_name} x{self.quantity}"

    class Meta:
        ordering = ['-created_at']

