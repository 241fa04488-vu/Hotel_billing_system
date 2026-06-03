import os
import django

# Set the settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hotel_billing.settings')
django.setup()

from django.contrib.auth.models import User
from billing.models import UserProfile, Room

def seed_users():
    users_data = [
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

        # Set role in profile
        profile, p_created = UserProfile.objects.get_or_create(user=user)
        profile.role = data["role"]
        profile.save()
        print(f"Mapped {user.username} role to -> {profile.role}")

    print("Successfully seeded role accounts!")

if __name__ == '__main__':
    seed_users()
