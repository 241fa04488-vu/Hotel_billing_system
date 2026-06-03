from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from .models import Room, Invoice, InvoiceItem, UserProfile
from datetime import date, timedelta

class RoomModelTest(TestCase):
    def setUp(self):
        self.room = Room.objects.create(
            room_number="401",
            category="Suite",
            price_per_night=5000.00,
            status="Available"
        )

    def test_room_creation(self):
        self.assertEqual(self.room.room_number, "401")
        self.assertEqual(self.room.category, "Suite")
        self.assertEqual(self.room.price_per_night, 5000.00)
        self.assertEqual(self.room.status, "Available")

    def test_room_string_representation(self):
        self.assertEqual(str(self.room), "Room 401 (Suite)")


class InvoiceModelTest(TestCase):
    def setUp(self):
        self.room = Room.objects.create(
            room_number="101",
            category="Standard",
            price_per_night=1200.00,
            status="Available"
        )
        self.check_in = date.today()
        self.check_out = date.today() + timedelta(days=3)  # 3 nights

    def test_invoice_creation_and_totals(self):
        invoice = Invoice.objects.create(
            customer_name="John Doe",
            customer_email="john@example.com",
            customer_phone="1234567890",
            room=self.room,
            check_in_date=self.check_in,
            check_out_date=self.check_out,
            discount=200.00,
            tax_rate=12.00,
            payment_method="Cash",
            payment_status="Pending"
        )
        
        # Nights count should be 3
        self.assertEqual(invoice.nights_count, 3)
        
        # Room charges = 3 * 1200 = 3600
        invoice.calculate_totals(save_invoice=True)
        self.assertEqual(invoice.room_charges, 3600.00)
        
        # Subtotal = room_charges (3600) + extra_charges (0) - discount (200) = 3400
        # Tax = 3400 * 12% = 408
        self.assertEqual(invoice.tax_amount, 408.00)
        
        # Grand total = 3400 + 408 = 3808
        self.assertEqual(invoice.grand_total, 3808.00)
        
        # Check custom invoice number format
        self.assertTrue(invoice.invoice_number.startswith("INV-"))

    def test_invoice_with_items_calculation(self):
        invoice = Invoice.objects.create(
            customer_name="Jane Doe",
            room=self.room,
            check_in_date=self.check_in,
            check_out_date=self.check_out,
            discount=0.00,
            tax_rate=10.00,
            payment_method="UPI",
            payment_status="Paid"
        )
        
        # Add Invoice Items
        InvoiceItem.objects.create(invoice=invoice, description="Spa", amount=1500.00)
        InvoiceItem.objects.create(invoice=invoice, description="Dinner", amount=500.00)
        
        # Recalculate and assert
        invoice.refresh_from_db()
        
        # Room charges = 3 * 1200 = 3600
        self.assertEqual(invoice.room_charges, 3600.00)
        # Extra charges = 1500 + 500 = 2000
        self.assertEqual(invoice.extra_charges, 2000.00)
        
        # Subtotal = 3600 + 2000 = 5600
        # Tax = 5600 * 10% = 560
        # Grand total = 5600 + 560 = 6160
        self.assertEqual(invoice.tax_amount, 560.00)
        self.assertEqual(invoice.grand_total, 6160.00)


class ViewsTest(TestCase):
    def setUp(self):
        self.room = Room.objects.create(
            room_number="101",
            category="Standard",
            price_per_night=1200.00,
            status="Available"
        )
        # Create a test staff user
        self.staff_user = User.objects.create_user(username="teststaff", password="password123")
        self.staff_user.profile.role = 'Staff'
        self.staff_user.profile.save()

    def test_anonymous_redirect(self):
        # Anonymous users should be redirected to staff login
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse('staff_login')))

    def test_dashboard_view_authorized(self):
        self.client.login(username="teststaff", password="password123")
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'dashboard.html')

    def test_room_list_view_authorized(self):
        self.client.login(username="teststaff", password="password123")
        response = self.client.get(reverse('room_list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'rooms.html')

    def test_invoice_list_view_authorized(self):
        self.client.login(username="teststaff", password="password123")
        response = self.client.get(reverse('invoice_list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'invoice_list.html')

    def test_invoice_create_view_get_authorized(self):
        self.client.login(username="teststaff", password="password123")
        response = self.client.get(reverse('invoice_create'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'invoice_form.html')

    def test_invoice_create_post_auto_register(self):
        from decimal import Decimal
        self.client.login(username="teststaff", password="password123")
        post_data = {
            'customer_user': 'new',
            'customer_name': 'Diana Prince',
            'customer_email': 'diana@amazon.com',
            'customer_phone': '9876543210',
            'room': self.room.pk,
            'check_in_date': str(date.today()),
            'check_out_date': str(date.today() + timedelta(days=2)),
            'discount': '100.00',
            'tax_rate': '12.00',
            'payment_method': 'Card',
            'payment_status': 'Paid'
        }
        response = self.client.post(reverse('invoice_create'), post_data)
        # Should redirect to details view on success
        self.assertEqual(response.status_code, 302)
        
        # Verify Customer user account auto-registered
        self.assertTrue(User.objects.filter(email='diana@amazon.com').exists())
        diana_user = User.objects.get(email='diana@amazon.com')
        self.assertEqual(diana_user.profile.role, 'Customer')
        self.assertEqual(diana_user.profile.phone, '9876543210')
        
        # Verify invoice is linked correctly and saved persistently
        invoice = Invoice.objects.filter(customer_user=diana_user).first()
        self.assertIsNotNone(invoice)
        self.assertEqual(invoice.customer_name, 'Diana Prince')
        
        # Charges = 2 nights @ 1200 = 2400. Less 100 discount = 2300. Plus 12% tax = 2576.00
        self.assertEqual(invoice.grand_total, Decimal('2576.00'))

    def test_invoice_pay_authorized(self):
        # Create a pending invoice
        invoice = Invoice.objects.create(
            customer_name="Bruce Wayne",
            room=self.room,
            check_in_date=date.today(),
            check_out_date=date.today() + timedelta(days=2),
            payment_status="Pending"
        )
        # Set room status to Occupied initially for stay
        self.room.status = "Occupied"
        self.room.save()
        
        self.client.login(username="teststaff", password="password123")
        response = self.client.get(reverse('invoice_pay', args=[invoice.pk]))
        # Should redirect to invoice detail page
        self.assertEqual(response.status_code, 302)
        
        # Verify invoice is marked as Paid and room is in Cleaning
        invoice.refresh_from_db()
        self.assertEqual(invoice.payment_status, "Paid")
        self.room.refresh_from_db()
        self.assertEqual(self.room.status, "Cleaning")

    def test_invoice_pay_unauthorized(self):
        # Create a pending invoice
        invoice = Invoice.objects.create(
            customer_name="Bruce Wayne",
            room=self.room,
            check_in_date=date.today(),
            check_out_date=date.today() + timedelta(days=2),
            payment_status="Pending"
        )
        
        # Log in as a customer (unauthorized for staff ledger pay action)
        customer_user = User.objects.create_user(username="tempcustomer", password="password123")
        customer_user.profile.role = 'Customer'
        customer_user.profile.save()
        
        self.client.login(username="tempcustomer", password="password123")
        response = self.client.get(reverse('invoice_pay', args=[invoice.pk]))
        # Lacking Staff role clearance, should redirect and log user out
        self.assertEqual(response.status_code, 302)
        invoice.refresh_from_db()
        self.assertEqual(invoice.payment_status, "Pending")

    def test_invoice_pay_post_card(self):
        invoice = Invoice.objects.create(
            customer_name="Bruce Wayne",
            room=self.room,
            check_in_date=date.today(),
            check_out_date=date.today() + timedelta(days=2),
            payment_status="Pending"
        )
        self.client.login(username="teststaff", password="password123")
        post_data = {
            'payment_method': 'Card',
            'card_name': 'Bruce Wayne',
            'card_number': '1111222233334444',
            'card_expiry': '12/28',
            'card_cvv': '123'
        }
        response = self.client.post(reverse('invoice_pay', args=[invoice.pk]), post_data)
        self.assertEqual(response.status_code, 302)
        invoice.refresh_from_db()
        self.assertEqual(invoice.payment_status, "Paid")
        self.assertEqual(invoice.payment_method, "Card")

    def test_invoice_pay_post_upi(self):
        invoice = Invoice.objects.create(
            customer_name="Bruce Wayne",
            room=self.room,
            check_in_date=date.today(),
            check_out_date=date.today() + timedelta(days=2),
            payment_status="Pending"
        )
        self.client.login(username="teststaff", password="password123")
        post_data = {
            'payment_method': 'UPI'
        }
        response = self.client.post(reverse('invoice_pay', args=[invoice.pk]), post_data)
        self.assertEqual(response.status_code, 302)
        invoice.refresh_from_db()
        self.assertEqual(invoice.payment_status, "Paid")
        self.assertEqual(invoice.payment_method, "UPI")


class RoleAuthorizationTest(TestCase):
    def setUp(self):
        self.customer_user = User.objects.create_user(username="testcustomer", password="password123")
        self.customer_user.profile.role = 'Customer'
        self.customer_user.profile.save()
        
        self.manager_user = User.objects.create_user(username="testmanager", password="password123")
        self.manager_user.profile.role = 'Manager'
        self.manager_user.profile.save()

    def test_customer_cannot_access_staff_dashboard(self):
        self.client.login(username="testcustomer", password="password123")
        response = self.client.get(reverse('dashboard'))
        # Should redirect due to lacking Staff role clearance
        self.assertEqual(response.status_code, 302)
        
    def test_customer_portal_authorized(self):
        self.client.login(username="testcustomer", password="password123")
        response = self.client.get(reverse('customer_portal'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'customer_portal.html')


class BookingAuditTest(TestCase):
    def setUp(self):
        self.room = Room.objects.create(
            room_number="505",
            category="Suite",
            price_per_night=5000.00,
            status="Available"
        )
        self.customer = User.objects.create_user(username="testcustomer", password="password123")
        self.customer.profile.role = 'Customer'
        self.customer.profile.phone = '9876543210'
        self.customer.profile.save()

    def test_rejection_past_date(self):
        from datetime import date, timedelta
        from billing.models import BookingRequest
        self.client.login(username="testcustomer", password="password123")
        
        post_data = {
            'room': self.room.pk,
            'check_in_date': str(date.today() - timedelta(days=2)),
            'check_out_date': str(date.today() + timedelta(days=1))
        }
        response = self.client.post(reverse('customer_book_room'), post_data)
        self.assertEqual(response.status_code, 302)
        
        booking = BookingRequest.objects.filter(customer=self.customer).first()
        self.assertIsNotNone(booking)
        self.assertEqual(booking.status, 'Rejected')
        self.assertEqual(booking.rejection_reason, "Check-in date cannot be in the past.")

    def test_rejection_invalid_duration(self):
        from datetime import date, timedelta
        from billing.models import BookingRequest
        self.client.login(username="testcustomer", password="password123")
        
        post_data = {
            'room': self.room.pk,
            'check_in_date': str(date.today()),
            'check_out_date': str(date.today() + timedelta(days=32))
        }
        response = self.client.post(reverse('customer_book_room'), post_data)
        self.assertEqual(response.status_code, 302)
        
        booking = BookingRequest.objects.filter(customer=self.customer).first()
        self.assertEqual(booking.status, 'Rejected')
        self.assertEqual(booking.rejection_reason, "Stay duration exceeds maximum limit of 30 nights.")

    def test_rejection_room_occupied(self):
        from datetime import date, timedelta
        from billing.models import BookingRequest
        self.client.login(username="testcustomer", password="password123")
        
        self.room.status = 'Occupied'
        self.room.save()
        
        post_data = {
            'room': self.room.pk,
            'check_in_date': str(date.today()),
            'check_out_date': str(date.today() + timedelta(days=2))
        }
        response = self.client.post(reverse('customer_book_room'), post_data)
        self.assertEqual(response.status_code, 302)
        
        booking = BookingRequest.objects.filter(customer=self.customer).first()
        self.assertEqual(booking.status, 'Rejected')
        self.assertEqual(booking.rejection_reason, "Selected room is currently occupied or under maintenance.")

    def test_successful_approval(self):
        from decimal import Decimal
        from datetime import date, timedelta
        from billing.models import BookingRequest, Invoice
        self.client.login(username="testcustomer", password="password123")
        
        post_data = {
            'room': self.room.pk,
            'check_in_date': str(date.today()),
            'check_out_date': str(date.today() + timedelta(days=3))
        }
        response = self.client.post(reverse('customer_book_room'), post_data)
        self.assertEqual(response.status_code, 302)
        
        booking = BookingRequest.objects.filter(customer=self.customer).first()
        self.assertIsNotNone(booking)
        self.assertEqual(booking.status, 'Approved')
        
        self.room.refresh_from_db()
        self.assertEqual(self.room.status, 'Occupied')
        
        invoice = Invoice.objects.filter(customer_user=self.customer).first()
        self.assertIsNotNone(invoice)
        # Price is (3 nights * 5000) = 15000. Under default tax 12% total is 16800.00
        self.assertEqual(invoice.room_charges, Decimal('15000.00'))
        self.assertEqual(invoice.grand_total, Decimal('16800.00'))

    def test_rejection_missing_phone(self):
        from datetime import date, timedelta
        from billing.models import BookingRequest
        
        # Remove phone number to trigger phone verification check
        self.customer.profile.phone = ""
        self.customer.profile.save()
        
        self.client.login(username="testcustomer", password="password123")
        
        post_data = {
            'room': self.room.pk,
            'check_in_date': str(date.today()),
            'check_out_date': str(date.today() + timedelta(days=2))
        }
        response = self.client.post(reverse('customer_book_room'), post_data)
        self.assertEqual(response.status_code, 302)
        
        booking = BookingRequest.objects.filter(customer=self.customer).first()
        self.assertIsNotNone(booking)
        self.assertEqual(booking.status, 'Rejected')
        self.assertEqual(booking.rejection_reason, "A valid phone number is required on your profile to confirm booking.")

    def test_rejection_exceeds_capacity(self):
        from datetime import date, timedelta
        from billing.models import BookingRequest
        self.client.login(username="testcustomer", password="password123")
        
        # self.room category is Suite (max capacity 5). Let's request 6 guests.
        post_data = {
            'room': self.room.pk,
            'check_in_date': str(date.today()),
            'check_out_date': str(date.today() + timedelta(days=2)),
            'num_guests': 6
        }
        response = self.client.post(reverse('customer_book_room'), post_data)
        self.assertEqual(response.status_code, 302)
        
        booking = BookingRequest.objects.filter(customer=self.customer).first()
        self.assertIsNotNone(booking)
        self.assertEqual(booking.status, 'Rejected')
        self.assertEqual(booking.rejection_reason, "Number of guests (6) exceeds the Suite Room maximum capacity of 5 guests.")

    def test_rejection_overlapping_booking(self):
        from datetime import date, timedelta
        from billing.models import BookingRequest
        
        # Seed an APPROVED booking request for self.room
        BookingRequest.objects.create(
            customer=self.customer,
            room=self.room,
            check_in_date=date.today(),
            check_out_date=date.today() + timedelta(days=3),
            num_guests=2,
            status='Approved'
        )
        
        # Create a second user to avoid spam audit rejection
        other_user = User.objects.create_user(username="testcustomer2", password="password123")
        other_user.profile.role = 'Customer'
        other_user.profile.phone = '1234567890'
        other_user.profile.save()
        
        self.client.login(username="testcustomer2", password="password123")
        
        # Attempt booking that overlaps (e.g. check-in on day 2, checkout on day 4)
        post_data = {
            'room': self.room.pk,
            'check_in_date': str(date.today() + timedelta(days=2)),
            'check_out_date': str(date.today() + timedelta(days=4)),
            'num_guests': 2
        }
        response = self.client.post(reverse('customer_book_room'), post_data)
        self.assertEqual(response.status_code, 302)
        
        booking = BookingRequest.objects.filter(customer=other_user).first()
        self.assertIsNotNone(booking)
        self.assertEqual(booking.status, 'Rejected')
        self.assertEqual(booking.rejection_reason, "Selected room is already booked for these dates.")

    def test_manager_cannot_see_check_in_options(self):
        # Create a manager user
        manager_user = User.objects.create_user(username="testmanager", password="password123")
        manager_user.profile.role = 'Manager'
        manager_user.profile.save()
        
        self.client.login(username="testmanager", password="password123")
        
        # Load rooms inventory page
        response = self.client.get(reverse('room_list'))
        self.assertEqual(response.status_code, 200)
        
        # Verify check-in link is not visible
        self.assertNotContains(response, "?room_id=")
        self.assertNotContains(response, "Check-in")

    def test_invoice_print_otp_flow(self):
        from django.core import mail
        from billing.models import Invoice
        
        # Seed an invoice in Paid status
        invoice = Invoice.objects.create(
            customer_user=self.customer,
            customer_name="Test Customer Receipt",
            customer_email="testcustomer@example.com",
            room=self.room,
            check_in_date=date.today(),
            check_out_date=date.today() + timedelta(days=3),
            room_charges=15000.00,
            payment_status="Paid",
            payment_method="UPI"
        )
        
        # Log in
        self.client.login(username="testcustomer", password="password123")
        
        # 1. Trigger Print OTP
        response = self.client.post(reverse('invoice_send_print_otp', args=[invoice.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'success')
        
        # Verify OTP generated in session
        session = self.client.session
        self.assertIn('print_otp', session)
        otp_code = session['print_otp']
        self.assertEqual(len(otp_code), 6)
        
        # Verify OTP email was sent to customer and CC'd to admin
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("testcustomer@example.com", mail.outbox[0].to)
        self.assertIn("vu.241fa04488@gmail.com", mail.outbox[0].to)
        self.assertIn("Receipt Print Authorization Code", mail.outbox[0].subject)
        
        # 2. Verify with wrong OTP code
        response = self.client.post(reverse('invoice_verify_print_otp', args=[invoice.pk]), {'otp_code': '999999'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'error')
        
        # 3. Verify with correct OTP code
        response = self.client.post(reverse('invoice_verify_print_otp', args=[invoice.pk]), {'otp_code': otp_code})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'success')
        
        # 4. Access invoice print view
        response = self.client.get(reverse('invoice_print_view', args=[invoice.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'invoice_print.html')


class CancellationAndValidationTest(TestCase):
    def setUp(self):
        self.room = Room.objects.create(
            room_number="909",
            category="Suite",
            price_per_night=4000.00,
            status="Available"
        )
        self.staff_user = User.objects.create_user(username="teststaff", password="password123")
        self.staff_user.profile.role = 'Staff'
        self.staff_user.profile.save()

        self.customer = User.objects.create_user(username="testcustomer", password="password123")
        self.customer.profile.role = 'Customer'
        self.customer.profile.phone = '9876543210'
        self.customer.profile.save()

    def test_invoice_create_rejects_occupied_room(self):
        # Set room status to Occupied
        self.room.status = 'Occupied'
        self.room.save()

        self.client.login(username="teststaff", password="password123")
        post_data = {
            'customer_user': 'new',
            'customer_name': 'Test Guest',
            'customer_email': 'guest@test.com',
            'customer_phone': '9876543210',
            'room': self.room.pk,
            'check_in_date': str(date.today()),
            'check_out_date': str(date.today() + timedelta(days=2)),
            'discount': '0.00',
            'tax_rate': '12.00',
            'payment_method': 'Cash',
            'payment_status': 'Pending'
        }
        response = self.client.post(reverse('invoice_create'), post_data)
        # Validation error keeps it on page with status 200 rather than redirecting
        self.assertEqual(response.status_code, 200)
        
        # Verify no invoice was created for this room
        self.assertEqual(Invoice.objects.filter(room=self.room).count(), 0)

    def test_customer_cancel_booking(self):
        from billing.models import BookingRequest
        
        # Setup room as Occupied (as if booked)
        self.room.status = 'Occupied'
        self.room.save()

        # Seed approved request
        req = BookingRequest.objects.create(
            customer=self.customer,
            room=self.room,
            check_in_date=date.today(),
            check_out_date=date.today() + timedelta(days=2),
            status='Approved'
        )

        # Seed pending Invoice
        invoice = Invoice.objects.create(
            customer_user=self.customer,
            customer_name="Test Customer",
            room=self.room,
            check_in_date=date.today(),
            check_out_date=date.today() + timedelta(days=2),
            room_charges=8000.00,
            payment_status='Pending'
        )

        self.client.login(username="testcustomer", password="password123")
        response = self.client.post(reverse('customer_cancel_booking', args=[invoice.pk]))
        # Should redirect back to customer portal
        self.assertEqual(response.status_code, 302)

        # Verify Room is set to Available
        self.room.refresh_from_db()
        self.assertEqual(self.room.status, 'Available')

        # Verify Invoice and BookingRequest are deleted
        self.assertEqual(Invoice.objects.filter(pk=invoice.pk).count(), 0)
        self.assertEqual(BookingRequest.objects.filter(pk=req.pk).count(), 0)

    def test_customer_cancel_request(self):
        from billing.models import BookingRequest

        # Setup room as Occupied (as if booked)
        self.room.status = 'Occupied'
        self.room.save()

        # Seed approved request
        req = BookingRequest.objects.create(
            customer=self.customer,
            room=self.room,
            check_in_date=date.today(),
            check_out_date=date.today() + timedelta(days=2),
            status='Approved'
        )

        # Seed pending Invoice
        invoice = Invoice.objects.create(
            customer_user=self.customer,
            customer_name="Test Customer",
            room=self.room,
            check_in_date=date.today(),
            check_out_date=date.today() + timedelta(days=2),
            room_charges=8000.00,
            payment_status='Pending'
        )

        self.client.login(username="testcustomer", password="password123")
        response = self.client.post(reverse('customer_cancel_request', args=[req.pk]))
        # Should redirect back to customer portal
        self.assertEqual(response.status_code, 302)

        # Verify Room is set to Available
        self.room.refresh_from_db()
        self.assertEqual(self.room.status, 'Available')

        # Verify Invoice and BookingRequest are deleted
        self.assertEqual(Invoice.objects.filter(pk=invoice.pk).count(), 0)
        self.assertEqual(BookingRequest.objects.filter(pk=req.pk).count(), 0)

    def test_staff_delete_invoice(self):
        # Seed an invoice
        invoice = Invoice.objects.create(
            customer_name="Test Customer Staff Delete",
            room=self.room,
            check_in_date=date.today(),
            check_out_date=date.today() + timedelta(days=2),
            room_charges=8000.00,
            payment_status='Pending'
        )
        self.room.status = 'Occupied'
        self.room.save()

        # Log in as Staff
        self.client.login(username="teststaff", password="password123")
        response = self.client.post(reverse('invoice_delete', args=[invoice.pk]))
        self.assertEqual(response.status_code, 302)

        # Verify Room is set to Available
        self.room.refresh_from_db()
        self.assertEqual(self.room.status, 'Available')

        # Verify Invoice is deleted
        self.assertEqual(Invoice.objects.filter(pk=invoice.pk).count(), 0)

    def test_payment_verification_photo_capture(self):
        # Seed a pending invoice
        invoice = Invoice.objects.create(
            customer_name="Test Customer Capture",
            room=self.room,
            check_in_date=date.today(),
            check_out_date=date.today() + timedelta(days=2),
            room_charges=8000.00,
            payment_status='Pending'
        )

        self.client.login(username="teststaff", password="password123")
        post_data = {
            'payment_method': 'UPI',
            'verification_photo': 'data:image/jpeg;base64,mockphotostringdata'
        }
        response = self.client.post(reverse('invoice_pay', args=[invoice.pk]), post_data)
        self.assertEqual(response.status_code, 302)

        # Verify payment is paid and photo is saved
        invoice.refresh_from_db()
        self.assertEqual(invoice.payment_status, "Paid")
        self.assertEqual(invoice.payment_method, "UPI")
        self.assertEqual(invoice.verification_photo, "data:image/jpeg;base64,mockphotostringdata")

    def test_customer_profile_update_validation_valid(self):
        self.client.login(username="testcustomer", password="password123")
        post_data = {
            'action': 'update_profile',
            'first_name': 'ValidName',
            'last_name': 'LastName',
            'email': 'valid@example.com',
            'phone': '9876543210'
        }
        response = self.client.post(reverse('customer_portal'), post_data)
        self.assertEqual(response.status_code, 302)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.first_name, 'ValidName')
        self.customer.profile.refresh_from_db()
        self.assertEqual(self.customer.profile.phone, '9876543210')

    def test_customer_profile_update_validation_invalid_name(self):
        self.client.login(username="testcustomer", password="password123")
        # Invalid first name containing digits
        post_data = {
            'action': 'update_profile',
            'first_name': 'Invalid123',
            'last_name': 'LastName',
            'email': 'valid@example.com',
            'phone': '9876543210'
        }
        response = self.client.post(reverse('customer_portal'), post_data)
        self.assertEqual(response.status_code, 302)
        # Check that customer was NOT updated
        self.customer.refresh_from_db()
        self.assertNotEqual(self.customer.first_name, 'Invalid123')

    def test_customer_profile_update_validation_invalid_email(self):
        self.client.login(username="testcustomer", password="password123")
        # Email missing @ character
        post_data = {
            'action': 'update_profile',
            'first_name': 'Valid',
            'last_name': 'LastName',
            'email': 'invalid-email-no-at.com',
            'phone': '9876543210'
        }
        response = self.client.post(reverse('customer_portal'), post_data)
        self.assertEqual(response.status_code, 302)
        self.customer.refresh_from_db()
        self.assertNotEqual(self.customer.email, 'invalid-email-no-at.com')

    def test_customer_profile_update_validation_invalid_phone(self):
        self.client.login(username="testcustomer", password="password123")
        # Phone too short
        post_data = {
            'action': 'update_profile',
            'first_name': 'Valid',
            'last_name': 'LastName',
            'email': 'valid@example.com',
            'phone': '12345'
        }
        response = self.client.post(reverse('customer_portal'), post_data)
        self.assertEqual(response.status_code, 302)
        self.customer.profile.refresh_from_db()
        self.assertNotEqual(self.customer.profile.phone, '12345')

    def test_invoice_create_validation_invalid_guest_name(self):
        self.client.login(username="teststaff", password="password123")
        post_data = {
            'customer_user': 'new',
            'customer_name': 'Guest123',
            'customer_email': 'guest@example.com',
            'customer_phone': '9876543210',
            'room': self.room.pk,
            'check_in_date': date.today().strftime('%Y-%m-%d'),
            'check_out_date': (date.today() + timedelta(days=2)).strftime('%Y-%m-%d'),
            'discount': '0.00',
            'tax_rate': '12.00',
            'payment_method': 'Cash',
            'payment_status': 'Pending'
        }
        response = self.client.post(reverse('invoice_create'), post_data)
        # Should render the form with error instead of redirecting
        self.assertEqual(response.status_code, 200)

    def test_invoice_create_validation_invalid_guest_phone(self):
        self.client.login(username="teststaff", password="password123")
        post_data = {
            'customer_user': 'new',
            'customer_name': 'Valid Guest Name',
            'customer_email': 'guest@example.com',
            'customer_phone': '123',  # Too short
            'room': self.room.pk,
            'check_in_date': date.today().strftime('%Y-%m-%d'),
            'check_out_date': (date.today() + timedelta(days=2)).strftime('%Y-%m-%d'),
            'discount': '0.00',
            'tax_rate': '12.00',
            'payment_method': 'Cash',
            'payment_status': 'Pending'
        }
        response = self.client.post(reverse('invoice_create'), post_data)
        self.assertEqual(response.status_code, 200)

    def test_staff_double_booking_rejection_and_surcharge(self):
        # 1. Create first stay invoice for customer (making them hold an active check-in)
        Invoice.objects.create(
            customer_user=self.customer,
            customer_name="Test Customer",
            room=self.room,
            check_in_date=date.today(),
            check_out_date=date.today() + timedelta(days=2),
            room_charges=8000.00,
            payment_status='Pending'
        )
        self.room.status = 'Occupied'
        self.room.save()
        
        # Log in as Staff
        self.client.login(username="teststaff", password="password123")
        
        # Setup second room
        second_room = Room.objects.create(
            room_number="202",
            category="Deluxe",
            price_per_night=3000.00,
            status="Available"
        )
        
        # 2. Try placing check-in for second room WITHOUT confirming extra room surcharge
        second_post_no_extra = {
            'customer_user': self.customer.pk,
            'customer_name': 'Test Customer',
            'customer_email': 'customer@example.com',
            'customer_phone': '9876543210',
            'room': second_room.pk,
            'check_in_date': date.today().strftime('%Y-%m-%d'),
            'check_out_date': (date.today() + timedelta(days=2)).strftime('%Y-%m-%d'),
            'discount': '0.00',
            'tax_rate': '12.00',
            'payment_method': 'Cash',
            'payment_status': 'Pending'
        }
        response = self.client.post(reverse('invoice_create'), second_post_no_extra)
        # Should reject and render form (returns 200) instead of redirecting
        self.assertEqual(response.status_code, 200)
        
        # Assert no second invoice created
        self.assertEqual(Invoice.objects.filter(room=second_room).count(), 0)
        
        # 3. Place check-in for second room WITH confirming extra room surcharge
        second_post_with_extra = {
            'customer_user': self.customer.pk,
            'customer_name': 'Test Customer',
            'customer_email': 'customer@example.com',
            'customer_phone': '9876543210',
            'room': second_room.pk,
            'check_in_date': date.today().strftime('%Y-%m-%d'),
            'check_out_date': (date.today() + timedelta(days=2)).strftime('%Y-%m-%d'),
            'discount': '0.00',
            'tax_rate': '12.00',
            'payment_method': 'Cash',
            'payment_status': 'Pending',
            'is_extra_room': 'on'
        }
        response = self.client.post(reverse('invoice_create'), second_post_with_extra)
        # Should successfully create and redirect
        self.assertEqual(response.status_code, 302)
        
        # Assert invoice has the surcharge InvoiceItem
        invoice = Invoice.objects.filter(customer_user=self.customer, room=second_room).first()
        self.assertIsNotNone(invoice)
        
        surcharge_item = invoice.items.filter(description="Extra Chamber Booking Surcharge").first()
        self.assertIsNotNone(surcharge_item)
        self.assertEqual(surcharge_item.amount, 1000.00)
        
        # Room charges = 2 nights * 3000 = 6000
        # Extra charges = 1000
        # Subtotal = 7000. Tax = 7000 * 12% = 840. Total = 7840
        self.assertEqual(invoice.grand_total, 7840.00)

    def test_customer_double_booking_rejection_and_surcharge(self):
        from billing.models import BookingRequest
        # 1. Create first stay booking/invoice for customer (making them hold an active check-in)
        BookingRequest.objects.create(
            customer=self.customer,
            room=self.room,
            check_in_date=date.today(),
            check_out_date=date.today() + timedelta(days=2),
            status='Approved'
        )
        Invoice.objects.create(
            customer_user=self.customer,
            customer_name="Test Customer",
            room=self.room,
            check_in_date=date.today(),
            check_out_date=date.today() + timedelta(days=2),
            room_charges=8000.00,
            payment_status='Pending'
        )
        self.room.status = 'Occupied'
        self.room.save()

        # Log in as Customer
        self.client.login(username="testcustomer", password="password123")

        # Setup second room
        second_room = Room.objects.create(
            room_number="910",
            category="Standard",
            price_per_night=2000.00,
            status="Available"
        )

        # 2. Try placing booking request for second room WITHOUT confirming extra room surcharge
        post_data_no_extra = {
            'room': second_room.pk,
            'check_in_date': date.today().strftime('%Y-%m-%d'),
            'check_out_date': (date.today() + timedelta(days=2)).strftime('%Y-%m-%d'),
            'num_guests': 1
        }
        response = self.client.post(reverse('customer_book_room'), post_data_no_extra)
        # Should redirect back to customer portal
        self.assertEqual(response.status_code, 302)

        # Assert a rejected booking request was created, and no invoice was created for second room
        latest_request = BookingRequest.objects.filter(room=second_room).first()
        self.assertIsNotNone(latest_request)
        self.assertEqual(latest_request.status, 'Rejected')
        self.assertIn("Active stay booking already exists", latest_request.rejection_reason)
        self.assertEqual(Invoice.objects.filter(room=second_room).count(), 0)

        # 3. Place booking request for second room WITH confirming extra room surcharge
        post_data_with_extra = {
            'room': second_room.pk,
            'check_in_date': date.today().strftime('%Y-%m-%d'),
            'check_out_date': (date.today() + timedelta(days=2)).strftime('%Y-%m-%d'),
            'num_guests': 1,
            'is_extra_room': 'on'
        }
        response = self.client.post(reverse('customer_book_room'), post_data_with_extra)
        # Should redirect back to customer portal
        self.assertEqual(response.status_code, 302)

        # Assert an approved booking request was created
        approved_request = BookingRequest.objects.filter(room=second_room, status='Approved').first()
        self.assertIsNotNone(approved_request)

        # Assert second room is now Occupied
        second_room.refresh_from_db()
        self.assertEqual(second_room.status, 'Occupied')

        # Assert invoice is created for second room with the surcharge InvoiceItem
        invoice = Invoice.objects.filter(customer_user=self.customer, room=second_room).first()
        self.assertIsNotNone(invoice)

        surcharge_item = invoice.items.filter(description="Extra Chamber Booking Surcharge").first()
        self.assertIsNotNone(surcharge_item)
        self.assertEqual(surcharge_item.amount, 1000.00)

        # Room charges = 2 nights * 2000 = 4000
        # Extra charges = 1000
        # Subtotal = 5000. Tax = 5000 * 12% = 600. Total = 5600
        self.assertEqual(invoice.grand_total, 5600.00)

    def test_customer_login_localStorage_restore(self):
        # Post to customer login form with username, password, email, and phone
        post_data = {
            'username': 'newguest',
            'password': 'newguest123',
            'email': 'savedemail@example.com',
            'phone': '9876543210'
        }
        # First login will auto-register the customer
        response = self.client.post(reverse('customer_login'), post_data)
        self.assertEqual(response.status_code, 302)
        
        # Verify customer was created with the correct email and phone
        user = User.objects.filter(username='newguest').first()
        self.assertIsNotNone(user)
        self.assertEqual(user.email, 'savedemail@example.com')
        self.assertEqual(user.profile.phone, '9876543210')
        
        # Now, modify the database values to simulate a database wipe/reset
        user.email = 'placeholder@example.com'
        user.profile.phone = '0000000000'
        user.save()
        user.profile.save()
        
        # Log out to clear session credentials
        self.client.logout()
        
        # Logging in again with the email and phone posted should restore them in the database!
        response = self.client.post(reverse('customer_login'), post_data)
        self.assertEqual(response.status_code, 302)
        
        user.refresh_from_db()
        user.profile.refresh_from_db()
        self.assertEqual(user.email, 'savedemail@example.com')
        self.assertEqual(user.profile.phone, '9876543210')





