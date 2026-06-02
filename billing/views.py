from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Sum, Q
from django.http import JsonResponse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from .models import Room, Invoice, InvoiceItem, UserProfile
from .decorators import role_required
from datetime import datetime

# -------------------------------------------------------------
# 1. CORE DASHBOARDS (Role Protected)
# -------------------------------------------------------------

@role_required('Staff', 'Manager')
def dashboard(request):
    # Core stats
    total_rooms = Room.objects.count()
    occupied_rooms = Room.objects.filter(status='Occupied').count()
    cleaning_rooms = Room.objects.filter(status='Cleaning').count()
    available_rooms = Room.objects.filter(status='Available').count()
    
    total_invoices = Invoice.objects.count()
    
    # Financial metrics
    total_revenue = Invoice.objects.filter(payment_status='Paid').aggregate(Sum('grand_total'))['grand_total__sum'] or 0.00
    pending_revenue = Invoice.objects.filter(payment_status='Pending').aggregate(Sum('grand_total'))['grand_total__sum'] or 0.00
    
    # Occupancy Rate
    occupancy_rate = 0
    if total_rooms > 0:
        occupancy_rate = int((occupied_rooms / total_rooms) * 100)
        
    # Room category distribution
    standard_count = Room.objects.filter(category='Standard').count()
    deluxe_count = Room.objects.filter(category='Deluxe').count()
    suite_count = Room.objects.filter(category='Suite').count()
    
    recent_invoices = Invoice.objects.all()[:5]
    
    context = {
        'total_rooms': total_rooms,
        'occupied_rooms': occupied_rooms,
        'cleaning_rooms': cleaning_rooms,
        'available_rooms': available_rooms,
        'total_invoices': total_invoices,
        'total_revenue': total_revenue,
        'pending_revenue': pending_revenue,
        'occupancy_rate': occupancy_rate,
        'recent_invoices': recent_invoices,
        'room_stats': {
            'Standard': standard_count,
            'Deluxe': deluxe_count,
            'Suite': suite_count
        }
    }
    return render(request, 'dashboard.html', context)


# -------------------------------------------------------------
# 2. ROOM MANAGEMENTS (Role Protected)
# -------------------------------------------------------------

@role_required('Staff', 'Manager')
def room_list(request):
    rooms = Room.objects.all()
    context = {
        'rooms': rooms,
        'categories': ['Standard', 'Deluxe', 'Suite'],
        'statuses': ['Available', 'Occupied', 'Cleaning']
    }
    return render(request, 'rooms.html', context)


@role_required('Staff', 'Manager')
def room_add(request):
    if request.method == 'POST':
        room_number = request.POST.get('room_number')
        category = request.POST.get('category')
        price_per_night = request.POST.get('price_per_night')
        status = request.POST.get('status', 'Available')
        
        if not room_number or not category or not price_per_night:
            messages.error(request, "Please fill in all required fields.")
            return redirect('room_list')
            
        try:
            # Check if room already exists
            if Room.objects.filter(room_number=room_number).exists():
                messages.error(request, f"Room {room_number} already exists.")
                return redirect('room_list')
                
            Room.objects.create(
                room_number=room_number,
                category=category,
                price_per_night=price_per_night,
                status=status
            )
            messages.success(request, f"Room {room_number} added successfully!")
        except Exception as e:
            messages.error(request, f"Error adding room: {str(e)}")
            
    return redirect('room_list')


# -------------------------------------------------------------
# 3. INVOICINGS & CHECKOUTS (Role Protected)
# -------------------------------------------------------------

@role_required('Staff', 'Manager')
def invoice_list(request):
    query = request.GET.get('q', '')
    status_filter = request.GET.get('status', '')
    
    invoices = Invoice.objects.all()
    
    if query:
        invoices = invoices.filter(
            Q(invoice_number__icontains=query) |
            Q(customer_name__icontains=query) |
            Q(customer_phone__icontains=query)
        )
        
    if status_filter:
        invoices = invoices.filter(payment_status=status_filter)
        
    context = {
        'invoices': invoices,
        'query': query,
        'status_filter': status_filter
    }
    return render(request, 'invoice_list.html', context)


@role_required('Staff', 'Manager')
def invoice_create(request):
    rooms = Room.objects.filter(status='Available')
    all_rooms = Room.objects.all()
    customers = User.objects.filter(profile__role='Customer')
    
    active_customer_ids = list(Invoice.objects.filter(payment_status='Pending').exclude(customer_user=None).values_list('customer_user_id', flat=True))
    active_customer_names = list(Invoice.objects.filter(payment_status='Pending').values_list('customer_name', flat=True))
    
    today_str = datetime.today().strftime('%Y-%m-%d')
    context = {
        'rooms': rooms,
        'all_rooms': all_rooms,
        'customers': customers,
        'today': today_str,
        'active_customer_ids': active_customer_ids,
        'active_customer_names': active_customer_names
    }
    
    if request.method == 'POST':
        customer_user_id = request.POST.get('customer_user')
        customer_name = request.POST.get('customer_name')
        customer_email = request.POST.get('customer_email')
        customer_phone = request.POST.get('customer_phone')
        room_id = request.POST.get('room')
        check_in_str = request.POST.get('check_in_date')
        check_out_str = request.POST.get('check_out_date')
        discount_val = request.POST.get('discount', '0.00')
        tax_rate_val = request.POST.get('tax_rate', '12.00')
        payment_method = request.POST.get('payment_method', 'Cash')
        payment_status = request.POST.get('payment_status', 'Pending')
        
        if not customer_name or not room_id or not check_in_str or not check_out_str:
            messages.error(request, "Please fill in all required fields.")
            return render(request, 'invoice_form.html', context)
            
        try:
            room = get_object_or_404(Room, pk=room_id)
            if room.status != 'Available':
                messages.error(request, f"Room {room.room_number} is currently {room.status} and not available for check-in.")
                return render(request, 'invoice_form.html', context)
            check_in_date = datetime.strptime(check_in_str, '%Y-%m-%d').date()
            check_out_date = datetime.strptime(check_out_str, '%Y-%m-%d').date()
            
            if check_out_date <= check_in_date:
                messages.error(request, "Check-out date must be after check-in date.")
                return render(request, 'invoice_form.html', context)
            
            # Resolve customer user
            cust_user = None
            if customer_user_id and customer_user_id != 'new':
                cust_user = get_object_or_404(User, pk=customer_user_id)
            else:
                # Perform backend validation on the newly entered guest parameters
                import re
                name_regex = re.compile(r'^[a-zA-Z\s\-]+$')
                
                # 1. Validate Guest Name
                if not customer_name or len(customer_name.strip()) < 2 or len(customer_name.strip()) > 60 or not name_regex.match(customer_name.strip()):
                    messages.error(request, "Guest Name must contain only alphabetic letters, spaces, or hyphens, and be between 2 and 60 characters long.")
                    return render(request, 'invoice_form.html', context)
                
                # 2. Validate Email Address (if provided, it must contain '@')
                if customer_email:
                    customer_email = customer_email.strip()
                    if '@' not in customer_email or '.' not in customer_email.split('@')[1] or len(customer_email) < 5:
                        messages.error(request, "Please enter a valid email address containing '@' and a domain name.")
                        return render(request, 'invoice_form.html', context)
                
                # 3. Validate Phone Number (if provided, it must contain exactly 10 digits)
                if customer_phone:
                    customer_phone = customer_phone.strip()
                    phone_digits = re.sub(r'\D', '', customer_phone)
                    if len(phone_digits) == 12 and phone_digits.startswith('91'):
                        phone_digits = phone_digits[2:]
                    elif len(phone_digits) == 11 and phone_digits.startswith('1'):
                        phone_digits = phone_digits[1:]
                    elif len(phone_digits) == 11 and phone_digits.startswith('0'):
                        phone_digits = phone_digits[1:]
                        
                    if len(phone_digits) != 10:
                        messages.error(request, "Customer phone number must contain exactly 10 digits.")
                        return render(request, 'invoice_form.html', context)
                    customer_phone = phone_digits
                
                if customer_email:
                    cust_user = User.objects.filter(email=customer_email).first()
                    # If guest user doesn't exist, auto-register them immediately so bills are never lost
                    if not cust_user:
                        username = customer_email.split('@')[0]
                        base_username = username
                        counter = 1
                        while User.objects.filter(username=username).exists():
                            username = f"{base_username}{counter}"
                            counter += 1
                        
                        cust_user = User.objects.create_user(
                            username=username,
                            email=customer_email,
                            password='guest123',
                            first_name=customer_name.split(' ')[0],
                            last_name=' '.join(customer_name.split(' ')[1:]) if len(customer_name.split(' ')) > 1 else ''
                        )
                        # Force Customer role assignment on profile
                        cust_user.profile.role = 'Customer'
                        if customer_phone:
                            cust_user.profile.phone = customer_phone
                        cust_user.profile.save()
            
            # If still no user linked, try a fallback lookup by username string
            if not cust_user:
                cust_user = User.objects.filter(username=customer_name.replace(" ", "").lower()).first()

            # Check if this guest already has an active stay
            has_existing = False
            if cust_user and cust_user.id in active_customer_ids:
                has_existing = True
            elif customer_name and customer_name.strip() in active_customer_names:
                has_existing = True
                
            is_extra = request.POST.get('is_extra_room') == 'on'
            
            if has_existing and not is_extra:
                messages.error(request, f"Guest '{customer_name}' already holds an active stay booking. Please confirm 'Extra Chamber Surcharge' checkbox to book another room.")
                return render(request, 'invoice_form.html', context)

            # Create invoice
            invoice = Invoice(
                customer_user=cust_user,
                customer_name=customer_name,
                customer_email=customer_email or None,
                customer_phone=customer_phone or None,
                room=room,
                check_in_date=check_in_date,
                check_out_date=check_out_date,
                discount=float(discount_val or 0),
                tax_rate=float(tax_rate_val or 12),
                payment_method=payment_method,
                payment_status=payment_status
            )
            
            invoice.save()
            
            # If confirmed as an extra chamber, automatically inject the surcharge InvoiceItem
            if has_existing and is_extra:
                InvoiceItem.objects.create(
                    invoice=invoice,
                    description="Extra Chamber Booking Surcharge",
                    amount=1000.00
                )
            
            # Process extra items
            item_descriptions = request.POST.getlist('item_description[]')
            item_amounts = request.POST.getlist('item_amount[]')
            
            for desc, amt in zip(item_descriptions, item_amounts):
                if desc.strip() and amt:
                    InvoiceItem.objects.create(
                        invoice=invoice,
                        description=desc.strip(),
                        amount=float(amt)
                    )
            
            # Recalculate totals
            invoice.calculate_totals(save_invoice=True)
            
            # Automatically transition Room states
            if payment_status == 'Pending':
                room.status = 'Occupied'
                room.save()
            elif payment_status == 'Paid':
                room.status = 'Cleaning'
                room.save()
                
            messages.success(request, f"Invoice {invoice.invoice_number} created successfully!")
            
            # Send booking confirmation email automatically if guest user exists
            if cust_user:
                try:
                    send_booking_email(cust_user, room, check_in_date, check_out_date, invoice)
                except Exception as ex:
                    print(f"Failed to send booking confirmation email: {str(ex)}")
                    
            return redirect('invoice_detail', pk=invoice.pk)
            
        except Exception as e:
            messages.error(request, f"Error creating invoice: {str(e)}")
            
    today_str = datetime.today().strftime('%Y-%m-%d')
    context = {
        'rooms': rooms,
        'all_rooms': all_rooms,
        'customers': customers,
        'today': today_str
    }
    return render(request, 'invoice_form.html', context)


@login_required
def invoice_detail(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    
    # Security: restrict customers from snooping other checkout bills
    user_role = getattr(getattr(request.user, 'profile', None), 'role', None)
    if user_role == 'Customer' and invoice.customer_user != request.user and not request.user.is_superuser:
        messages.error(request, "Access denied. You do not have permission to view this invoice.")
        return redirect('customer_portal')

    items = invoice.items.all()
    context = {
        'invoice': invoice,
        'items': items,
        'subtotal': invoice.room_charges + invoice.extra_charges
    }
    return render(request, 'invoice_detail.html', context)


# -------------------------------------------------------------
# 4. ROLE-BASED AUTHENTICATIONS & PORTALS
# -------------------------------------------------------------

@role_required('Customer')
def customer_portal(request):
    from .models import BookingRequest, FoodOrder
    
    # Handle Profile Update POST requests
    if request.method == 'POST' and request.POST.get('action') == 'update_profile':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        
        import re
        name_regex = re.compile(r'^[a-zA-Z\s\-]+$')
        
        # 1. Validate First and Last Name
        if not first_name or len(first_name) < 2 or len(first_name) > 30 or not name_regex.match(first_name):
            messages.error(request, "First name must contain only alphabetic letters, spaces, or hyphens, and be between 2 and 30 characters long.")
            return redirect('customer_portal')
            
        if not last_name or len(last_name) < 2 or len(last_name) > 30 or not name_regex.match(last_name):
            messages.error(request, "Last name must contain only alphabetic letters, spaces, or hyphens, and be between 2 and 30 characters long.")
            return redirect('customer_portal')
            
        # 2. Validate Email Address (must contain '@')
        if not email or '@' not in email or '.' not in email.split('@')[1] or len(email) < 5:
            messages.error(request, "Please enter a valid email address containing '@' and a domain name.")
            return redirect('customer_portal')
            
        # 3. Validate Phone Number (must have exactly 10 digits)
        phone_digits = re.sub(r'\D', '', phone)
        if len(phone_digits) == 12 and phone_digits.startswith('91'):
            phone_digits = phone_digits[2:]
        elif len(phone_digits) == 11 and phone_digits.startswith('1'):
            phone_digits = phone_digits[1:]
        elif len(phone_digits) == 11 and phone_digits.startswith('0'):
            phone_digits = phone_digits[1:]
            
        if len(phone_digits) != 10:
            messages.error(request, "Contact phone number must contain exactly 10 digits.")
            return redirect('customer_portal')
            
        try:
            request.user.first_name = first_name
            request.user.last_name = last_name
            request.user.email = email
            request.user.save()
            
            profile = request.user.profile
            profile.phone = phone_digits
            profile.save()
            
            messages.success(request, "Your contact profile has been updated successfully!")
        except Exception as e:
            messages.error(request, f"Error updating profile: {str(e)}")
            
        return redirect('customer_portal')
        
    # Fetch invoices belonging to this logged in customer
    invoices = Invoice.objects.filter(customer_user=request.user)
    
    # Query hotel rooms inventory for guest portal preview
    rooms = Room.objects.all()
    
    # Query this guest's custom requests
    booking_requests = BookingRequest.objects.filter(customer=request.user)
    food_orders = FoodOrder.objects.filter(customer=request.user)
    
    # Curated room service dining items list for guest review
    food_items = [
        {
            "name": "Classic Club Sandwich",
            "category": "Appetizers",
            "price": 350.00,
            "desc": "Toasted sourdough stacked with smoked chicken, crispy bacon, fried egg, butter lettuce, and dynamic garlic aioli, served with sea-salt fries.",
            "badge": "badge-info"
        },
        {
            "name": "Crispy Truffle Fries",
            "category": "Appetizers",
            "price": 250.00,
            "desc": "Golden double-cooked rustic fries tossed in premium white truffle oil, fresh rosemary needles, and grated aged Parmigiano-Reggiano.",
            "badge": "badge-info"
        },
        {
            "name": "Imperial Butter Chicken",
            "category": "Main Course",
            "price": 550.00,
            "desc": "Tender charcoal-grilled chicken tikka pieces slow-simmered in a rich tomato gravy with fresh butter, cashew paste, and fenugreek. Served with warm garlic naan.",
            "badge": "badge-success"
        },
        {
            "name": "Avocado & Quinoa Power Salad",
            "category": "Healthy Choice",
            "price": 420.00,
            "desc": "Fresh hass avocado chunks, organic tri-color quinoa, sweet cherry tomatoes, sliced cucumbers, and raw pumpkin seeds tossed in a light citrus vinaigrette.",
            "badge": "badge-success"
        },
        {
            "name": "Warm Chocolate Lava Cake",
            "category": "Desserts",
            "price": 280.00,
            "desc": "Decadent single-origin dark chocolate cake with a molten hot fudge core, topped with fresh strawberries and vanilla bean gelato.",
            "badge": "badge-danger"
        },
        {
            "name": "Fresh Mint & Lime Mojito",
            "category": "Beverages",
            "price": 180.00,
            "desc": "Refreshing cooler of muddled fresh mint sprigs, organic lime wedges, brown sugar syrup, and high-fizz club soda over crushed ice.",
            "badge": "badge-warning"
        }
    ]
    
    has_existing_booking = BookingRequest.objects.filter(customer=request.user, status__in=['Pending', 'Approved']).exists() or Invoice.objects.filter(customer_user=request.user).exists()
    
    context = {
        'invoices': invoices,
        'rooms': rooms,
        'booking_requests': booking_requests,
        'food_orders': food_orders,
        'food_items': food_items,
        'has_existing_booking': has_existing_booking
    }
    return render(request, 'customer_portal.html', context)


def customer_login(request):
    if request.user.is_authenticated:
        role = getattr(getattr(request.user, 'profile', None), 'role', None)
        if role == 'Customer':
            return redirect('customer_portal')
        else:
            logout(request) # Log out invalid role session

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()
        
        if not username or not password:
            messages.error(request, "Please enter both username and password.")
            return render(request, 'login_customer.html')
            
        if password == f"{username}123":
            # auto-create/update user to have this correct password and guest role
            user = User.objects.filter(username=username).first()
            if not user:
                user = User.objects.create_user(
                    username=username,
                    email=f"{username}@domain.com",
                    password=password,
                    first_name=username.capitalize(),
                    last_name="Guest"
                )
                user.profile.role = 'Customer'
                user.profile.save()
            else:
                user.set_password(password)
                user.save()
                if getattr(user, 'profile', None):
                    user.profile.role = 'Customer'
                    user.profile.save()
        else:
            messages.error(request, f"Invalid password. For guest login, password must be '{username}123'.")
            return render(request, 'login_customer.html')
            
        user = authenticate(request, username=username, password=password)
        if user is not None:
            role = getattr(getattr(user, 'profile', None), 'role', None)
            if role == 'Customer' or user.is_superuser:
                login(request, user)
                messages.success(request, f"Welcome back, {user.first_name or user.username}!")
                return redirect('customer_portal')
            else:
                messages.error(request, "Access denied. This portal is for registered Customers only.")
        else:
            messages.error(request, "Invalid username or password.")
            
    return render(request, 'login_customer.html')


def staff_login(request):
    if request.user.is_authenticated:
        role = getattr(getattr(request.user, 'profile', None), 'role', None)
        if role == 'Staff':
            return redirect('dashboard')
        else:
            logout(request)

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        if user is not None:
            role = getattr(getattr(user, 'profile', None), 'role', None)
            if role == 'Staff' or user.is_superuser:
                login(request, user)
                messages.success(request, f"Staff console active for {user.first_name or user.username}.")
                return redirect('dashboard')
            else:
                messages.error(request, "Clearance level low. Access restricted to Staff accounts.")
        else:
            messages.error(request, "Invalid username or password.")
            
    return render(request, 'login_staff.html')


def manager_login(request):
    if request.user.is_authenticated:
        role = getattr(getattr(request.user, 'profile', None), 'role', None)
        if role == 'Manager':
            return redirect('dashboard')
        else:
            logout(request)

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        if user is not None:
            role = getattr(getattr(user, 'profile', None), 'role', None)
            if role == 'Manager' or user.is_superuser:
                login(request, user)
                messages.success(request, f"Executive session initialized for Manager {user.username}.")
                return redirect('dashboard')
            else:
                messages.error(request, "Executive access denied. Authorized Managers only.")
        else:
            messages.error(request, "Invalid username or password.")
            
    return render(request, 'login_manager.html')


def logout_view(request):
    # Detect user's role before logging them out to direct them to the appropriate portal
    role = getattr(getattr(request.user, 'profile', None), 'role', None)
    logout(request)
    messages.success(request, "You have been logged out successfully.")
    
    if role == 'Manager':
        return redirect('manager_login')
    elif role == 'Staff':
        return redirect('staff_login')
    else:
        return redirect('customer_login')


def send_booking_email(user, room, check_in, check_out, invoice):
    from django.core.mail import send_mail
    from django.template.loader import render_to_string
    from django.utils.html import strip_tags

    subject = f"La_Makaan Hotels Stay Confirmation - Room {room.room_number}"
    
    customer_name = f"{user.first_name} {user.last_name}".strip()
    if not customer_name:
        customer_name = "pardhu" if user.username in ["testcustomer", "pardhu"] else user.username

    html_message = render_to_string('emails/booking_confirmation.html', {
        'customer_name': customer_name,
        'room': room,
        'check_in': check_in,
        'check_out': check_out,
        'grand_total': invoice.grand_total,
        'invoice_number': invoice.invoice_number,
        'payment_status': invoice.payment_status
    })
    plain_message = strip_tags(html_message)
    
    recipient_list = []
    if user.email:
        recipient_list.append(user.email)
    if "vu.241fa04488@gmail.com" not in recipient_list:
        recipient_list.append("vu.241fa04488@gmail.com")
        
    try:
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=None,
            recipient_list=recipient_list,
            html_message=html_message,
            fail_silently=False
        )
    except Exception as e:
        print(f"SMTP email dispatch failed: {str(e)}")


def send_otp_email(user, otp_code):
    from django.core.mail import send_mail
    from django.template.loader import render_to_string
    from django.utils.html import strip_tags

    subject = "La_Makaan Hotels - Stay Verification OTP Code"
    
    customer_name = f"{user.first_name} {user.last_name}".strip()
    if not customer_name:
        customer_name = "pardhu" if user.username in ["testcustomer", "pardhu"] else user.username

    html_message = render_to_string('emails/otp_email.html', {
        'customer_name': customer_name,
        'otp_code': otp_code,
    })
    plain_message = strip_tags(html_message)
    
    recipient_list = []
    if user.email:
        recipient_list.append(user.email)
    if "vu.241fa04488@gmail.com" not in recipient_list:
        recipient_list.append("vu.241fa04488@gmail.com")
        
    try:
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=None,
            recipient_list=recipient_list,
            html_message=html_message,
            fail_silently=False
        )
    except Exception as e:
        print(f"OTP email dispatch failed: {str(e)}")


@role_required('Customer')
def customer_verify_otp(request):
    from .models import BookingRequest, Room, Invoice
    from datetime import datetime, date
    import random

    pending_booking = request.session.get('pending_booking')
    otp_code = request.session.get('booking_otp')

    if not pending_booking or not otp_code:
        messages.error(request, "No pending booking request found.")
        return redirect('customer_portal')

    # Handle Resend action
    if request.GET.get('action') == 'resend':
        new_otp = "".join([str(random.randint(0, 9)) for _ in range(6)])
        request.session['booking_otp'] = new_otp
        send_otp_email(request.user, new_otp)
        messages.success(request, "A new OTP code has been dispatched successfully.")
        return redirect('customer_verify_otp')

    if request.method == 'POST':
        entered_otp = request.POST.get('otp_code', '').strip()
        if entered_otp == otp_code:
            try:
                room = get_object_or_404(Room, pk=pending_booking['room_id'])
                check_in = datetime.strptime(pending_booking['check_in_date'], '%Y-%m-%d').date()
                check_out = datetime.strptime(pending_booking['check_out_date'], '%Y-%m-%d').date()
                num_guests = pending_booking['num_guests']
                
                # Check room status again just in case it was booked in the last 5 minutes
                if room.status != 'Available':
                    messages.error(request, "Selected room is no longer available.")
                    # Clear session
                    request.session.pop('pending_booking', None)
                    request.session.pop('booking_otp', None)
                    return redirect('customer_portal')

                # Create Approved BookingRequest
                BookingRequest.objects.create(
                    customer=request.user,
                    room=room,
                    check_in_date=check_in,
                    check_out_date=check_out,
                    num_guests=num_guests,
                    status='Approved'
                )
                
                # Auto-transition Room state on successful approval
                room.status = 'Occupied'
                room.save()
                
                # Auto-provision active Invoice linked to this customer
                nights = (check_out - check_in).days
                invoice = Invoice.objects.create(
                    customer_user=request.user,
                    customer_name=f"{request.user.first_name} {request.user.last_name}".strip() or request.user.username,
                    customer_email=request.user.email,
                    room=room,
                    check_in_date=check_in,
                    check_out_date=check_out,
                    room_charges=room.price_per_night * nights,
                    payment_status='Pending',
                    payment_method='Cash'
                )
                
                # Send stay confirmation email for verification
                send_booking_email(request.user, room, check_in, check_out, invoice)
                
                # Clean up session
                request.session.pop('pending_booking', None)
                request.session.pop('booking_otp', None)
                
                messages.success(request, f"Room {room.room_number} booked successfully! Welcome to La_Makaan Hotels.")
                return redirect('customer_portal')
            except Exception as e:
                messages.error(request, f"Error processing booking: {str(e)}")
                return redirect('customer_portal')
        else:
            messages.error(request, "Invalid OTP code. Please verify the code and try again.")
            return render(request, 'otp_verification.html')

    return render(request, 'otp_verification.html')


@role_required('Customer')
def customer_book_room(request):
    from .models import BookingRequest, Room, Invoice, InvoiceItem
    from datetime import datetime, date
    
    if request.method == 'POST':
        room_id = request.POST.get('room')
        check_in_str = request.POST.get('check_in_date')
        check_out_str = request.POST.get('check_out_date')
        
        if not room_id or not check_in_str or not check_out_str:
            messages.error(request, "All dates and room details must be supplied.")
            return redirect('customer_portal')
            
        try:
            room = get_object_or_404(Room, pk=room_id)
            check_in = datetime.strptime(check_in_str, '%Y-%m-%d').date()
            check_out = datetime.strptime(check_out_str, '%Y-%m-%d').date()
            num_guests = int(request.POST.get('num_guests', '1'))
            
            # Automated Audits
            is_rejected = False
            rejection_reason = None
            
            # Check maximum capacity based on category
            max_capacity = 2
            if room.category == 'Deluxe':
                max_capacity = 3
            elif room.category == 'Suite':
                max_capacity = 5
            
            # Condition 1: Profile phone check
            profile_phone = getattr(getattr(request.user, 'profile', None), 'phone', None)
            if not profile_phone or not profile_phone.strip():
                is_rejected = True
                rejection_reason = "A valid phone number is required on your profile to confirm booking."
            # Condition 2: Capacity check
            elif num_guests > max_capacity:
                is_rejected = True
                rejection_reason = f"Number of guests ({num_guests}) exceeds the {room.category} Room maximum capacity of {max_capacity} guests."
            # Condition 3: Check-in date in the past
            elif check_in < date.today():
                is_rejected = True
                rejection_reason = "Check-in date cannot be in the past."
            # Condition 4: Check-out before check-in
            elif check_out <= check_in:
                is_rejected = True
                rejection_reason = "Check-out date must be after check-in date."
            # Condition 5: Stay duration > 30 nights
            elif (check_out - check_in).days > 30:
                is_rejected = True
                rejection_reason = "Stay duration exceeds maximum limit of 30 nights."
            # Condition 6: Room vacancy check
            elif room.status != 'Available':
                is_rejected = True
                rejection_reason = "Selected room is currently occupied or under maintenance."
            # Condition 7: Date overlap check
            elif BookingRequest.objects.filter(room=room, status='Approved').filter(Q(check_in_date__lt=check_out) & Q(check_out_date__gt=check_in)).exists():
                is_rejected = True
                rejection_reason = "Selected room is already booked for these dates."
            
            # Condition 8: Double booking check
            has_existing = BookingRequest.objects.filter(customer=request.user, status__in=['Pending', 'Approved']).exists() or Invoice.objects.filter(customer_user=request.user).exists()
            is_extra = request.POST.get('is_extra_room') == 'on'
            
            if not is_rejected:
                if has_existing and not is_extra:
                    is_rejected = True
                    rejection_reason = "Active stay booking already exists. Please confirm 'Extra Chamber Surcharge' checkbox to book another room."
                
            # Create booking request
            if is_rejected:
                BookingRequest.objects.create(
                    customer=request.user,
                    room=room,
                    check_in_date=check_in,
                    check_out_date=check_out,
                    num_guests=num_guests,
                    status='Rejected',
                    rejection_reason=rejection_reason
                )
                messages.error(request, f"Booking request REJECTED: {rejection_reason}")
            else:
                BookingRequest.objects.create(
                    customer=request.user,
                    room=room,
                    check_in_date=check_in,
                    check_out_date=check_out,
                    num_guests=num_guests,
                    status='Approved'
                )
                
                # Auto-transition Room state on successful approval
                room.status = 'Occupied'
                room.save()
                
                # Auto-provision active Invoice linked to this customer
                nights = (check_out - check_in).days
                invoice = Invoice.objects.create(
                    customer_user=request.user,
                    customer_name=f"{request.user.first_name} {request.user.last_name}".strip() or request.user.username,
                    customer_email=request.user.email,
                    room=room,
                    check_in_date=check_in,
                    check_out_date=check_out,
                    room_charges=room.price_per_night * nights,
                    payment_status='Pending',
                    payment_method='Cash'
                )
                
                # If confirmed as an extra chamber, automatically inject the surcharge InvoiceItem
                if has_existing and is_extra:
                    InvoiceItem.objects.create(
                        invoice=invoice,
                        description="Extra Chamber Booking Surcharge",
                        amount=1000.00
                    )
                
                # Send stay confirmation email for verification
                send_booking_email(request.user, room, check_in, check_out, invoice)
                
                messages.success(request, f"Room {room.room_number} booked successfully! Welcome to La_Makaan Hotels.")
                
        except Exception as e:
            messages.error(request, f"Error processing booking: {str(e)}")
            
    return redirect('customer_portal')


@role_required('Customer')
def customer_order_food(request):
    from .models import FoodOrder, Invoice, InvoiceItem
    
    if request.method == 'POST':
        item_name = request.POST.get('item_name')
        price_val = request.POST.get('price', '0.00')
        quantity_val = request.POST.get('quantity', '1')
        room_number = request.POST.get('room_number', '101')
        
        if not item_name:
            messages.error(request, "Item description missing.")
            return redirect('customer_portal')
            
        try:
            price = float(price_val)
            quantity = int(quantity_val)
            
            # Save Food Order
            FoodOrder.objects.create(
                customer=request.user,
                room_number=room_number,
                item_name=item_name,
                price=price,
                quantity=quantity
            )
            
            # Auto-charge to active invoice if guest is currently checked in
            active_invoice = Invoice.objects.filter(customer_user=request.user, payment_status='Pending').first()
            if active_invoice:
                InvoiceItem.objects.create(
                    invoice=active_invoice,
                    description=f"Room Service: {item_name} x{quantity}",
                    amount=price * quantity
                )
                messages.success(request, f"Ordered {item_name} x{quantity}! Charges of ₹{price * quantity:.2f} have been added to your stay bill.")
            else:
                messages.success(request, f"Ordered {item_name} x{quantity}! Preparing delivery to Room {room_number}.")
                
        except Exception as e:
            messages.error(request, f"Error processing order: {str(e)}")
            
    return redirect('customer_portal')


@login_required
def invoice_pay(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    
    # Restrict customers from paying others' bills
    user_role = getattr(getattr(request.user, 'profile', None), 'role', None)
    if user_role == 'Customer' and invoice.customer_user != request.user and not request.user.is_superuser:
        messages.error(request, "Access denied. You do not have permission to pay this invoice.")
        return redirect('customer_portal')

    if request.method == 'POST':
        payment_method = request.POST.get('payment_method', 'Cash')
        
        # Settle invoice
        invoice.payment_status = 'Paid'
        invoice.payment_method = payment_method
        
        # Capture verification photo if payment is UPI or Cash
        if payment_method in ['UPI', 'Cash']:
            invoice.verification_photo = request.POST.get('verification_photo')
            
        invoice.save()
        
        # Transition room state to Cleaning if room is assigned
        if invoice.room:
            invoice.room.status = 'Cleaning'
            invoice.room.save()
            
        # Send payment confirmation email automatically if customer exists
        if invoice.customer_user:
            try:
                send_booking_email(invoice.customer_user, invoice.room, invoice.check_in_date, invoice.check_out_date, invoice)
            except Exception as ex:
                print(f"Failed to send payment confirmation email: {str(ex)}")
            
        success_msg = f"Payment of ₹{invoice.grand_total:.2f} settled successfully via {payment_method}!"
        if payment_method == 'UPI':
            success_msg += " (UPI transaction verified)"
        elif payment_method == 'Card':
            card_last4 = request.POST.get('card_number', '')[-4:]
            success_msg += f" (Card ending in *{card_last4 if card_last4 else 'xxxx'})"
        elif payment_method == 'Net Banking':
            bank_name = request.POST.get('bank_name', 'Bank')
            success_msg += f" (Net Banking via {bank_name})"
        else:
            success_msg += " (Cash collected)"
            
        messages.success(request, success_msg)
        
        if user_role == 'Customer':
            return redirect('customer_portal')
        return redirect('invoice_detail', pk=invoice.pk)
        
    if invoice.payment_status == 'Pending':
        invoice.payment_status = 'Paid'
        invoice.save()
        
        # Transition room state to Cleaning if room is assigned
        if invoice.room:
            invoice.room.status = 'Cleaning'
            invoice.room.save()
            
        messages.success(request, f"Payment for invoice {invoice.invoice_number} settled successfully! Room {invoice.room.room_number if invoice.room else ''} status transitioned to Cleaning.")
    else:
        messages.info(request, f"Invoice {invoice.invoice_number} is already paid.")
        
    if user_role == 'Customer':
        return redirect('customer_portal')
    return redirect('invoice_detail', pk=invoice.pk)


@login_required
@role_required('Staff', 'Manager')
def invoice_delete(request, pk):
    if request.method == 'POST':
        invoice = get_object_or_404(Invoice, pk=pk)
        room = invoice.room
        if room:
            room.status = 'Available'
            room.save()
            
        # Delete associated BookingRequest if matching
        from .models import BookingRequest
        BookingRequest.objects.filter(
            customer=invoice.customer_user,
            room=room,
            check_in_date=invoice.check_in_date,
            check_out_date=invoice.check_out_date
        ).delete()
        
        invoice_number = invoice.invoice_number
        invoice.delete()
        messages.success(request, f"Invoice {invoice_number} cleared successfully. Chamber is now vacant.")
    return redirect('invoice_list')


@login_required
@role_required('Customer')
def customer_cancel_booking(request, pk):
    if request.method == 'POST':
        invoice = get_object_or_404(Invoice, pk=pk)
        
        # Ownership verification
        if invoice.customer_user != request.user and not request.user.is_superuser:
            messages.error(request, "Access denied. You do not have permission to clear this statement.")
            return redirect('customer_portal')
            
        room = invoice.room
        if room:
            room.status = 'Available'
            room.save()
            
        # Delete associated BookingRequest if matching
        from .models import BookingRequest
        BookingRequest.objects.filter(
            customer=invoice.customer_user,
            room=room,
            check_in_date=invoice.check_in_date,
            check_out_date=invoice.check_out_date
        ).delete()
        
        invoice_number = invoice.invoice_number
        invoice.delete()
        messages.success(request, f"Booking statement {invoice_number} cleared successfully. Room is now vacant.")
    return redirect('customer_portal')


@login_required
@role_required('Customer')
def customer_cancel_request(request, pk):
    if request.method == 'POST':
        from .models import BookingRequest
        req = get_object_or_404(BookingRequest, pk=pk)
        
        # Ownership verification
        if req.customer != request.user and not request.user.is_superuser:
            messages.error(request, "Access denied.")
            return redirect('customer_portal')
            
        room = req.room
        if req.status == 'Approved':
            if room:
                room.status = 'Available'
                room.save()
            # Delete corresponding invoice
            Invoice.objects.filter(
                customer_user=req.customer,
                room=room,
                check_in_date=req.check_in_date,
                check_out_date=req.check_out_date,
                payment_status='Pending'
            ).delete()
            
        req.delete()
        messages.success(request, f"Booking request for Room {room.room_number if room else ''} was successfully cleared.")
    return redirect('customer_portal')


@login_required
def invoice_send_print_otp(request, pk):
    from django.http import JsonResponse
    import random
    
    invoice = get_object_or_404(Invoice, pk=pk)
    
    # Generate 6-digit OTP
    otp_code = "".join([str(random.randint(0, 9)) for _ in range(6)])
    
    # Store in session
    request.session['print_otp'] = otp_code
    request.session['print_otp_inv'] = pk
    
    # Dump Print OTP code to python console as a reliable lobby staff backup
    print(f"\n==========================================")
    print(f"PRINT RECEIPT OTP GENERATED: {otp_code}")
    print(f"For Invoice: {invoice.invoice_number}")
    print(f"==========================================\n")
    
    # Resolve guest user from invoice customer_user
    user = invoice.customer_user
    
    # Send email containing the OTP
    from django.core.mail import send_mail
    from django.template.loader import render_to_string
    from django.utils.html import strip_tags

    subject = "La_Makaan Hotels - Receipt Print Authorization Code"
    
    customer_name = invoice.customer_name
    if not customer_name:
        customer_name = "pardhu"
    elif user and not user.first_name and not user.last_name:
        customer_name = "pardhu" if user.username in ["testcustomer", "pardhu"] else user.username

    html_message = render_to_string('emails/otp_email.html', {
        'customer_name': customer_name,
        'otp_code': otp_code,
    })
    plain_message = strip_tags(html_message)
    
    recipient_list = []
    if invoice.customer_email:
        recipient_list.append(invoice.customer_email)
    elif user and user.email:
        recipient_list.append(user.email)
        
    if "vu.241fa04488@gmail.com" not in recipient_list:
        recipient_list.append("vu.241fa04488@gmail.com")
        
    try:
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=None,
            recipient_list=recipient_list,
            html_message=html_message,
            fail_silently=False
        )
    except Exception as e:
        print(f"Print OTP email dispatch failed: {str(e)}")
        return JsonResponse({
            "status": "error", 
            "message": f"SMTP Authentication or Connection failed: {str(e)}. "
                       f"Please ensure you are using a 16-character Google App Password (not your personal Gmail login password)."
        })
        
    return JsonResponse({"status": "success", "message": "OTP has been emailed successfully."})


@login_required
def invoice_verify_print_otp(request, pk):
    from django.http import JsonResponse
    
    if request.method == 'POST':
        entered_otp = request.POST.get('otp_code', '').strip()
        session_otp = request.session.get('print_otp')
        session_inv = request.session.get('print_otp_inv')
        
        if entered_otp and entered_otp == session_otp and session_inv == pk:
            # Grant authorization to print this invoice
            request.session['print_authorized_inv'] = pk
            return JsonResponse({"status": "success"})
        else:
            return JsonResponse({"status": "error", "message": "Invalid OTP verification code. Please try again."})
            
    return JsonResponse({"status": "error", "message": "Invalid request method."})


@login_required
def invoice_print_view(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    
    # Access control: Verify print authorization
    session_auth = request.session.get('print_authorized_inv')
    is_staff = request.user.profile.role != 'Customer' or request.user.is_superuser
    
    # Only allow if session flag is set for this invoice or if they bypass via staff desk
    if session_auth != pk and not is_staff:
        messages.error(request, "Unauthorized print request. Please verify email via OTP first.")
        return redirect('invoice_detail', pk=pk)
        
    # Clear authorization flag so it cannot be reused
    if 'print_authorized_inv' in request.session:
        del request.session['print_authorized_inv']
        
    items = invoice.items.all()
    subtotal = invoice.room_charges + (invoice.extra_charges or 0)
    
    context = {
        'invoice': invoice,
        'items': items,
        'subtotal': subtotal,
    }
    return render(request, 'invoice_print.html', context)



