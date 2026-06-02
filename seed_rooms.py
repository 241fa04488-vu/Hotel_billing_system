import os
import django

# Set the settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hotel_billing.settings')
django.setup()

from billing.models import Room

def seed_rooms():
    rooms_data = [
        {"room_number": "101", "category": "Standard", "price_per_night": 1200.00, "status": "Available"},
        {"room_number": "102", "category": "Standard", "price_per_night": 1200.00, "status": "Available"},
        {"room_number": "103", "category": "Standard", "price_per_night": 1200.00, "status": "Cleaning"},
        {"room_number": "104", "category": "Standard", "price_per_night": 1200.00, "status": "Available"},
        {"room_number": "201", "category": "Deluxe", "price_per_night": 2500.00, "status": "Available"},
        {"room_number": "202", "category": "Deluxe", "price_per_night": 2500.00, "status": "Occupied"},
        {"room_number": "203", "category": "Deluxe", "price_per_night": 2500.00, "status": "Available"},
        {"room_number": "204", "category": "Deluxe", "price_per_night": 2500.00, "status": "Cleaning"},
        {"room_number": "301", "category": "Suite", "price_per_night": 5000.00, "status": "Available"},
        {"room_number": "302", "category": "Suite", "price_per_night": 5000.00, "status": "Occupied"},
        {"room_number": "303", "category": "Suite", "price_per_night": 5000.00, "status": "Available"},
    ]

    print("Seeding rooms...")
    created_count = 0
    for data in rooms_data:
        room, created = Room.objects.get_or_create(
            room_number=data["room_number"],
            defaults={
                "category": data["category"],
                "price_per_night": data["price_per_night"],
                "status": data["status"]
            }
        )
        if created:
            created_count += 1
            print(f"Created Room {room.room_number}")
        else:
            print(f"Room {room.room_number} already exists")
    
    print(f"Successfully seeded {created_count} new rooms!")

if __name__ == '__main__':
    seed_rooms()
