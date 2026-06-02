import os
import django

# Set the settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hotel_billing.settings')
django.setup()

from django.contrib.auth.models import User
from billing.models import UserProfile, Invoice, Room
from datetime import date, timedelta

def seed_users():
    users_data = [
        {
            "username": "customer",
            "password": "customer123",
            "email": "customer@domain.com",
            "first_name": "Alice",
            "last_name": "Smith",
            "role": "Customer"
        },
        {
            "username": "staff",
            "password": "staff123",
            "email": "staff@domain.com",
            "first_name": "Bob",
            "last_name": "Miller",
            "role": "Staff"
        },
        {
            "username": "manager",
            "password": "manager123",
            "email": "manager@domain.com",
            "first_name": "Charlie",
            "last_name": "Davis",
            "role": "Manager"
        }
    ]

    print("Seeding users and profiles...")
    for data in users_data:
        # Check if user already exists
        user, created = User.objects.get_or_create(
            username=data["username"],
            defaults={
                "email": data["email"],
                "first_name": data["first_name"],
                "last_name": data["last_name"]
            }
        )
        if created:
            user.set_password(data["password"])
            user.save()
            print(f"Created User: {user.username}")
        else:
            print(f"User {user.username} already exists")

        # Set role in profile (should be auto-created by signal, but let's double-check/assign)
        profile, p_created = UserProfile.objects.get_or_create(user=user)
        profile.role = data["role"]
        profile.save()
        print(f"Mapped {user.username} role to -> {profile.role}")

    # Connect some existing mock invoices to the customer for immediate testing!
    print("Linking guest bookings to customer portal...")
    customer_user = User.objects.get(username="customer")
    
    # Let's see if we have invoices in the database
    invoices = Invoice.objects.all()
    if invoices.exists():
        for invoice in invoices:
            invoice.customer_user = customer_user
            invoice.customer_email = customer_user.email
            invoice.customer_name = f"{customer_user.first_name} {customer_user.last_name}"
            invoice.save()
        print(f"Successfully linked {invoices.count()} invoices to '{customer_user.username}' portal.")
    else:
        # Create a mock invoice for the customer if none exist
        room = Room.objects.first()
        if room:
            invoice = Invoice.objects.create(
                customer_user=customer_user,
                customer_name=f"{customer_user.first_name} {customer_user.last_name}",
                customer_email=customer_user.email,
                room=room,
                check_in_date=date.today(),
                check_out_date=date.today() + timedelta(days=2),
                payment_status="Paid",
                payment_method="UPI",
                discount=0
            )
            print(f"Created a mock billing receipt {invoice.invoice_number} for customer portal.")

    # Pre-seed Booking Requests and Food Orders
    from billing.models import BookingRequest, FoodOrder
    print("Pre-seeding booking requests and room orders...")
    
    room_101 = Room.objects.filter(room_number="101").first()
    room_202 = Room.objects.filter(room_number="202").first()
    
    if room_101:
        # 1. Approved Booking Request
        BookingRequest.objects.get_or_create(
            customer=customer_user,
            room=room_101,
            check_in_date=date.today() + timedelta(days=1),
            check_out_date=date.today() + timedelta(days=4),
            status='Approved'
        )
        # 2. Food Order
        FoodOrder.objects.get_or_create(
            customer=customer_user,
            room_number=room_101.room_number,
            item_name="Classic Club Sandwich",
            defaults={
                "price": 350.00,
                "quantity": 2,
                "status": "Pending"
            }
        )
        
    if room_202:
        # 3. Rejected Booking Request
        BookingRequest.objects.get_or_create(
            customer=customer_user,
            room=room_202,
            check_in_date=date.today() - timedelta(days=2),
            check_out_date=date.today(),
            defaults={
                "status": "Rejected",
                "rejection_reason": "Check-in date cannot be in the past."
            }
        )

    print("Successfully seeded role accounts, requests, and dining logs!")

if __name__ == '__main__':
    seed_users()
