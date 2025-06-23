from django.shortcuts import render, redirect
from django.template.loader import get_template
from django.http import HttpResponse
from django.http import HttpRequest
from django.conf import settings
import requests
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from .firebase import db, auth_instance
from django.http import JsonResponse 
import json
from django.core.mail import send_mail
import random
from datetime import datetime, date, timedelta

code = random.randint(100000, 999999)
# Create your views here.
def load(request):
    template = get_template('index.html')  # this will raise an error if not found
    return HttpResponse(template.render({}, request))

@csrf_exempt
def auth_view(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            action_type = data.get('type')

            if action_type == 'register':
                first_name = data.get('first_name')
                last_name = data.get('last_name')
                email = data.get('email')
                password = data.get('password')

                try:
                    # Create user in Firebase Authentication
                    user = auth_instance.create_user_with_email_and_password(email, password)

                    # Get current date in YYYY-MM-DD format
                    date_joined = datetime.now().strftime('%Y-%m-%d')

                    # Save user info in Realtime Database
                    db.child("userRegistrations").push({
                        'first_name': first_name,
                        'last_name': last_name,
                        'email': email,
                        'balance': 0,
                        'total_interest': 0,
                        'date_joined': date_joined,
                    })

                    return JsonResponse({'success': True, 'message': 'Registration successful'})

                except Exception as e:
                    return JsonResponse({'success': False, 'message': f'Firebase error: {str(e)}'}, status=400)

            elif action_type == 'login':
                email = data.get('email')
                password = data.get('password')

                try:
                    # Authenticate with Firebase Authentication
                    user = auth_instance.sign_in_with_email_and_password(email, password)

                    # Generate OTP and send email
                    otp_code = random.randint(100000, 999999)

                    # Save OTP in Firebase
                    email_key = email.replace('.', '_').replace('@', '_at_')
                    db.child("userVerificationCodes").child(email_key).set({'otp': otp_code})

                    # Store email in session
                    request.session['email'] = email

                    # Send OTP email
                    send_mail(
                        'Your Login OTP Code',
                        f'Your one-time login code is: {otp_code}',
                        'no-reply@yourdomain.com',
                        [email],
                        fail_silently=False,
                    )

                    return JsonResponse({'success': True, 'message': 'Login successful, OTP sent. Please check spam messages also.', 'otp': otp_code})

                except Exception as e:
                    print(f"Firebase login error: {e}")
                    return JsonResponse({'success': False, 'message': 'Invalid email or password'}, status=401)

            else:
                return JsonResponse({'success': False, 'message': 'Unknown action'}, status=400)

        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'message': 'Invalid JSON'}, status=400)

    return render(request, 'authentication/auth.html')


def format_email_key(email):
    # This must match how you saved the OTP
    return email.replace('.', '_').replace('@', '_at_')

@csrf_exempt
def verify(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            email = data.get('email') or request.session.get('email')
            code = data.get('code')

            if not email or not code:
                return JsonResponse({'success': False, 'message': 'Missing email or code'}, status=400)

            email_key = email.replace('.', '_').replace('@', '_at_')

            # Get OTP data from Firebase
            otp_data = db.child("userVerificationCodes").child(email_key).get()
            if not otp_data.val():
                return JsonResponse({'success': False, 'message': 'OTP not found'}, status=404)

            otp_value = otp_data.val().get('otp')

            if str(otp_value) == str(code):
                # OTP is valid, remove it from DB
                db.child("userVerificationCodes").child(email_key).remove()

                # Fetch user data from registrations
                users = db.child("userRegistrations").get()
                for user in users.each():
                    user_data = user.val()
                    if user_data.get('email') == email:
                        # Store user info in session
                        request.session['first_name'] = user_data.get('first_name')
                        request.session['last_name'] = user_data.get('last_name')
                        request.session['email'] = email
                        request.session['date_joined'] = user_data.get('date_joined')
                        request.session['balance'] = user_data.get('balance')
                        request.session['total_interest'] = user_data.get('total_interest')
                        break

                return JsonResponse({'success': True, 'message': 'Verification successful', 'redirect': '/user/dashboard/'})

            else:
                return JsonResponse({'success': False, 'message': 'Invalid code'}, status=401)

        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)

    return render(request, 'authentication/verify.html')

def get_interest_records(request):
    email = request.session.get('email')
    if not email:
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    savings = db.child("savings").get()
    interest_data = []

    if savings.each():
        for item in savings.each():
            data = item.val()
            if data.get("user_id") == email:
                interest_data.append({
                    'date': data.get("date_saved"),
                    'amount': float(data.get("interest_shown", 0)),
                    'rate': '0.8%',
                    'status': data.get("status")
                })

    # Sort by date descending
    interest_data.sort(key=lambda x: datetime.strptime(x["date"], "%Y-%m-%d"), reverse=True)

    return JsonResponse(interest_data, safe=False)

def userDashboard(request):
    email = request.session.get('email')   
    first_name = request.session.get('first_name')
    last_name = request.session.get('last_name')
    date_joined = request.session.get('date_joined')

    if not email:
        return redirect('auth_view')

    # Fetch updated balance and total interest from Firebase
    user_data = None
    all_users = db.child("userRegistrations").get()
    if all_users.each():
        for user in all_users.each():
            if user.val().get("email") == email:
                user_data = user.val()
                break

    balance = user_data.get("balance", 0) if user_data else 0
    total_interest = user_data.get("total_interest", 0) if user_data else 0
    today = date.today().strftime('%B %d, %Y')

    # Interest Records and Deposit Count
    interest_records = []
    deposit_count = 0
    savings = db.child("savings").get()
    if savings.each():
        for item in savings.each():
            data = item.val()
            if data.get("user_id") == email:
                deposit_count += 1
                interest_records.append({
                    "date": data.get("date_saved"),
                    "amount": data.get("interest_shown", 0),
                    "rate": "0.8%",
                    "status": "Earned" if data.get("interest_shown", 0) > 0 else "Pending"
                })

    # Withdrawal Count
    withdrawal_count = 0
    withdrawals = db.child("withdrawals").get()
    if withdrawals.each():
        for item in withdrawals.each():
            if item.val().get("user_id") == email:
                withdrawal_count += 1

    # Loan Count
    loan_count = 0
    loans = db.child("loan_applications").get()
    if loans.each():
        for item in loans.each():
            if item.val().get("user_id") == email:
                loan_count += 1

    context = {
        'email': email,
        'first_name': first_name,
        'last_name': last_name,
        'date_joined': date_joined,
        'balance': balance,
        'total_interest': total_interest,
        'today': today,
        'interest_records': interest_records,
        'deposit_count': deposit_count,
        'withdrawal_count': withdrawal_count,
        'loan_count': loan_count,
    }
    return render(request, 'user-dashboard/index.html', context)


def deposit(request):
    email = request.session.get('email')   
    first_name = request.session.get('first_name')
    last_name = request.session.get('last_name')
    date_joined = request.session.get('date_joined')

    if not email:
        return redirect('auth_view')

    # Get current balance and interest
    users = db.child("userRegistrations").get()
    balance = 0
    total_interest = 0

    for user in users.each():
        user_data = user.val()
        if user_data.get('email') == email:
            balance = float(user_data.get('balance', 0))
            total_interest = float(user_data.get('total_interest', 0))
            break

    # Calculate total deposits this month
    now = datetime.now()
    month_key = now.strftime('%Y-%m')
    total_deposit_this_month = 0

    savings = db.child("savings").get()
    if savings.each():
        for entry in savings.each():
            data = entry.val()
            if data.get('user_id') == email and data.get('month_key') == month_key:
                total_deposit_this_month += float(data.get('amount', 0))

    context = {
        'email': email,
        'first_name': first_name,
        'last_name': last_name,
        'date_joined': date_joined,
        'balance': balance,
        'total_interest': total_interest,
        'monthly_deposit': total_deposit_this_month,
    }

    return render(request, 'user-dashboard/deposit.html', context)

@csrf_exempt
def process_deposit(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            email = request.session.get('email')
            amount = float(data.get('amount'))
            method = data.get('method')
            reference = data.get('reference')
            purpose = data.get('purpose')
            notes = data.get('notes')

            if not email or amount < 100:
                return JsonResponse({'success': False, 'message': 'Minimum deposit is ₱100'}, status=400)

            today = datetime.now()
            date_str = today.strftime('%Y-%m-%d')
            month_key = today.strftime('%Y-%m')

            # Estimated interest shown to user (not actual)
            interest_estimate = round(amount * 0.008, 2)  # 0.8% as per client request

            # Save deposit entry with status = "waiting"
            db.child('savings').push({
                'user_id': email,
                'amount': amount,
                'date_saved': date_str,
                'month_key': month_key,
                'payment_method': method,
                'reference_number': reference,
                'purpose': purpose,
                'notes': notes,
                'interest_shown': interest_estimate,
                'interest_real': 0.0,
                'status': "waiting"  # <- important: admin will later set to "active"
            })

            # Update balance (we assume deposited amount is immediately available)
            users = db.child("userRegistrations").get()
            for user in users.each():
                user_key = user.key()
                user_data = user.val()
                if user_data.get('email') == email:
                    current_balance = float(user_data.get('balance', 0))
                    new_balance = current_balance + amount
                    db.child("userRegistrations").child(user_key).update({
                        'balance': new_balance
                    })
                    break

            return JsonResponse({'success': True, 'message': 'Deposit successful', 'new_balance': new_balance})

        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)

    return JsonResponse({'success': False, 'message': 'Invalid request'}, status=405)

def payment(request):
    email = request.session.get('email')   
    first_name = request.session.get('first_name')
    last_name = request.session.get('last_name')
    date_joined = request.session.get('date_joined')
    balance = request.session.get('balance')
    total_interest = request.session.get('total_interest')

    if not email:
        # If no session exists, redirect to login or show an error
        return redirect('auth_view')  # Replace 'auth_view' with your login page's URL name

    # Optionally, you can pass the email to the template
    context = {
        'email': email,
        'first_name': first_name,
        'last_name': last_name,
        'date_joined': date_joined,
        'balance': balance,
        'total_interest': total_interest,
    }
    return render(request, 'user-dashboard/payment.html', context)

def record(request):
    email = request.session.get('email')   
    first_name = request.session.get('first_name')
    last_name = request.session.get('last_name')
    date_joined = request.session.get('date_joined')
    balance = request.session.get('balance')
    total_interest = request.session.get('total_interest')

    if not email:
        # If no session exists, redirect to login or show an error
        return redirect('auth_view')  # Replace 'auth_view' with your login page's URL name

    # Optionally, you can pass the email to the template
    context = {
        'email': email,
        'first_name': first_name,
        'last_name': last_name,
        'date_joined': date_joined,
        'balance': balance,
        'total_interest': total_interest,
    }
    return render(request, 'user-dashboard/record.html', context)

def check_withdrawals_and_notify():
    withdrawals = db.child("withdrawals").get()

    if not withdrawals.each():
        return

    for item in withdrawals.each():
        withdrawal = item.val()
        key = item.key()

        # Already processed?
        if withdrawal.get("status") != "pending":
            continue

        # Parse date
        try:
            date_requested = datetime.strptime(withdrawal["date_requested"], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            try:
                date_requested = datetime.strptime(withdrawal["date_requested"], "%Y-%m-%d")
            except Exception:
                continue

        if datetime.now() - date_requested >= timedelta(hours=24):
            user_email = withdrawal.get("user_id")

            # Update status
            db.child("withdrawals").child(key).update({
                "status": "ready"
            })

            # Send email
            try:
                send_mail(
                    'Withdrawal Ready',
                    'Your withdrawal request is now ready. You may proceed to receive the funds.',
                    'no-reply@yourdomain.com',
                    [user_email],
                    fail_silently=False
                )
            except Exception as e:
                print(f"Email send failed: {str(e)}")

def withdrawal(request):
    check_withdrawals_and_notify()
    email = request.session.get('email')   
    first_name = request.session.get('first_name')
    last_name = request.session.get('last_name')
    date_joined = request.session.get('date_joined')

    if not email:
        return redirect('auth_view')

    # Get current balance and interest
    users = db.child("userRegistrations").get()
    balance = 0
    total_interest = 0

    for user in users.each():
        user_data = user.val()
        if user_data.get('email') == email:
            balance = user_data.get('balance', 0)
            total_interest = user_data.get('total_interest', 0)
            break

    # Get withdrawal history
    all_withdrawals = db.child("withdrawals").get()
    withdrawal_history = []

    if all_withdrawals.each():
        for entry in all_withdrawals.each():
            data = entry.val()
            if data.get("user_id") == email:
                withdrawal_history.append({
                    "amount": data.get("amount"),
                    "status": data.get("status"),
                    "method": data.get("method"),
                    "reason": data.get("reason"),
                    "date_requested": data.get("date_requested")
                })

    # Sort by latest date first
    withdrawal_history.sort(key=lambda x: datetime.strptime(x["date_requested"], "%Y-%m-%d %H:%M:%S"), reverse=True)

    context = {
        'email': email,
        'first_name': first_name,
        'last_name': last_name,
        'date_joined': date_joined,
        'balance': balance,
        'total_interest': total_interest,
        'withdrawal_history': withdrawal_history,
    }

    return render(request, 'user-dashboard/withdrawal.html', context)

@csrf_exempt
def process_withdrawal(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            email = request.session.get('email')
            amount = float(data.get('amount'))
            method = data.get('method')
            reason = data.get('reason')
            description = data.get('description')

            if not email:
                return JsonResponse({'success': False, 'message': 'Session expired, please log in again'}, status=403)

            if amount < 100:
                return JsonResponse({'success': False, 'message': 'Minimum withdrawal amount is ₱100'}, status=400)

            # Get current balance from userRegistrations
            users = db.child("userRegistrations").get()
            user_key = None
            balance = 0

            for user in users.each():
                user_data = user.val()
                if user_data.get('email') == email:
                    balance = float(user_data.get('balance', 0))
                    user_key = user.key()
                    break

            if user_key is None:
                return JsonResponse({'success': False, 'message': 'User not found'}, status=404)

            if balance - amount < 100:
                return JsonResponse({
                    'success': False,
                    'message': 'You must maintain at least ₱100 in your balance after withdrawal'
                }, status=400)

            # Do not deduct yet — just record as pending
            db.child("withdrawals").push({
                'user_id': email,
                'amount': amount,
                'method': method,
                'reason': reason,
                'description': description,
                'status': 'pending',
                'date_requested': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })

            return JsonResponse({
                'success': True,
                'message': 'Withdrawal request submitted. Please wait 24 hours for processing.'
            })

        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)

    return JsonResponse({'success': False, 'message': 'Invalid request method'}, status=405)


def loan(request):
    email = request.session.get('email')   
    first_name = request.session.get('first_name')
    last_name = request.session.get('last_name')
    date_joined = request.session.get('date_joined')
    balance = request.session.get('balance')
    total_interest = request.session.get('total_interest')
    full_name = first_name + " " + last_name

    phone = ''
    birthday = ''

    # Fetch existing data if available
    users = db.child("userRegistrations").get()
    for user in users.each():
        data = user.val()
        if data.get('email') == email:
            phone = data.get('phone', '')
            birthday = data.get('birthday', '')
            break

    context = {
        'email': email,
        'first_name': first_name,
        'last_name': last_name,
        'date_joined': date_joined,
        'balance': balance,
        'total_interest': total_interest,
        'full_name': full_name,
        'phone': phone,
        'birthday': birthday,
    }
    return render(request, 'user-dashboard/loan.html', context)

@csrf_exempt
def save_contact_info(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            email = request.session.get('email')
            phone = data.get('phone')
            birthday = data.get('birthday')

            # Validation
            year = int(birthday.split("-")[0])
            if year < 1900 or year > 2020:
                return JsonResponse({'success': False, 'message': 'Invalid birthday year'}, status=400)

            users = db.child("userRegistrations").get()
            for user in users.each():
                user_data = user.val()
                if user_data.get("email") == email:
                    db.child("userRegistrations").child(user.key()).update({
                        "phone": phone,
                        "birthday": birthday
                    })
                    break

            return JsonResponse({'success': True, 'message': 'Contact info saved'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)

    return JsonResponse({'success': False, 'message': 'Invalid method'}, status=405)


@csrf_exempt
def submit_loan_application(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)

            email = request.session.get('email')
            if not email:
                return JsonResponse({'success': False, 'message': 'Not authenticated'}, status=403)

            loan_type = data.get('loan_type')
            loan_amount = float(data.get('loan_amount'))
            loan_term = int(data.get('loan_term'))
            purpose = data.get('purpose', '')

            full_name = data.get('full_name')
            phone = data.get('phone')
            birthday = data.get('birthday')

            if not all([loan_type, loan_amount, loan_term, full_name, phone, birthday]):
                return JsonResponse({'success': False, 'message': 'Missing required fields'}, status=400)

            # Store to Firebase
            db.child("loan_applications").push({
                'user_id': email,
                'loan_type': loan_type,
                'amount': loan_amount,
                'term_months': loan_term,
                'purpose': purpose,
                'full_name': full_name,
                'phone': phone,
                'birthday': birthday,
                'status': 'pending',
                'date_applied': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })

            return JsonResponse({'success': True, 'message': 'Loan application submitted successfully'})

        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)

    return JsonResponse({'success': False, 'message': 'Invalid method'}, status=405)

def logout(request):
    request.session.flush()   
    return redirect('auth_view')


# admin

@csrf_exempt
def admin_login(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            email = data.get('email')
            password = data.get('password')

            if not email or not password:
                return JsonResponse({'success': False, 'message': 'Email and password are required'})

            # Step 1: Authenticate against Firebase Auth
            try:
                user = auth_instance.sign_in_with_email_and_password(email, password)
            except Exception:
                return JsonResponse({'success': False, 'message': 'Invalid email or password'})

            # Step 2: Check if the email matches the admin node directly
            admin_data = db.child("admin").get().val()

            if not admin_data:
                return JsonResponse({'success': False, 'message': 'Admin data not found in database'})

            if admin_data.get("email") != email or admin_data.get("role") != "admin":
                return JsonResponse({'success': False, 'message': 'Access denied. Not authorized as admin.'})

            # Success
            request.session['admin_email'] = email
            request.session['admin_role'] = 'admin'

            return JsonResponse({'success': True})

        except Exception as e:
            return JsonResponse({'success': False, 'message': f'Error: {str(e)}'}, status=500)

    return JsonResponse({'success': False, 'message': 'Invalid request method'}, status=405)


def admin_auth(request):
    return render(request, 'authentication/admin-auth.html')

def admin_dashboard(request):
    from decimal import Decimal

    today = date.today().strftime('%B %d, %Y')  

    users = db.child("userRegistrations").get()
    loans = db.child("loan_applications").get()

    total_users = 0
    pending_loans = 0
    total_savings = Decimal('0.00')

    if users.each():
        total_users = len(users.each())
        for user in users.each():
            user_data = user.val()
            balance = user_data.get("balance", 0)
            try:
                total_savings += Decimal(str(balance))
            except:
                pass  # skip if balance is not a number

    if loans.each():
        for loan in loans.each():
            loan_data = loan.val()
            if loan_data.get("status") == "pending":
                pending_loans += 1

    context = {
        'today': today,
        'total_users': total_users,
        'pending_loans': pending_loans,
        'total_savings': f"{total_savings:,.2f}",  # formatted with comma
    }
    return render(request, 'admin/dashboard.html', context)


def admin_savings_view(request):
    savings_data = []
    today = datetime.now()

    savings = db.child("savings").get()
    if savings.each():
        for entry in savings.each():
            data = entry.val()
            deposit_date = datetime.strptime(data.get('date_saved'), "%Y-%m-%d")
            is_eligible = (today - deposit_date).days >= 60 and data.get('status') == 'waiting'

            savings_data.append({
                'id': entry.key(),
                'email': data.get('user_id'),
                'amount': data.get('amount'),
                'interest_shown': data.get('interest_shown'),
                'interest_real': data.get('interest_real'),
                'status': data.get('status'),
                'date_saved': data.get('date_saved'),
                'eligible': is_eligible
            })

    context = {
        'savings': savings_data
    }

    return render(request, 'admin/savings_approval.html', context)

@csrf_exempt
def activate_interest(request, saving_id):
    if request.method == 'POST':
        try:
            # Fetch saving data
            saving = db.child("savings").child(saving_id).get().val()
            if not saving:
                return JsonResponse({'success': False, 'message': 'Saving not found'})

            if saving['status'] != 'waiting':
                return JsonResponse({'success': False, 'message': 'Already active or invalid status'})

            email = saving['user_id']
            interest_amount = float(saving.get('interest_shown', 0))

            # Update saving record
            db.child("savings").child(saving_id).update({
                'interest_real': interest_amount,
                'status': 'active'
            })

            # Add interest to user balance & total_interest
            users = db.child("userRegistrations").get()
            for user in users.each():
                user_key = user.key()
                user_data = user.val()
                if user_data.get('email') == email:
                    new_balance = float(user_data.get('balance', 0)) + interest_amount
                    new_total_interest = float(user_data.get('total_interest', 0)) + interest_amount
                    db.child("userRegistrations").child(user_key).update({
                        'balance': new_balance,
                        'total_interest': new_total_interest
                    })
                    break

            return JsonResponse({'success': True, 'message': 'Interest activated'})

        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)

    return JsonResponse({'success': False, 'message': 'Invalid method'}, status=405)
 
def loan_approvals(request):
    all_loans = db.child("loan_applications").get() 
    pending_loans = []

    total_pending = 0
    total_approved = 0
    total_rejected = 0

    if all_loans.each():
        for entry in all_loans.each():
            data = entry.val()
            status = data.get('status', '').lower()

            if status == 'pending':
                total_pending += 1
                data['key'] = entry.key()  # Add Firebase key for update buttons
                pending_loans.append(data)
            elif status == 'approved':
                total_approved += 1
            elif status == 'rejected':
                total_rejected += 1

    context = {
        'pending_loans': pending_loans,
        'total_pending': total_pending,
        'total_approved': total_approved,
        'total_rejected': total_rejected,
    }
    return render(request, 'admin/loan_approvals.html', context)


@csrf_exempt
def approve_loan(request):
    if request.method == 'POST':
        loan_key = request.POST.get('loan_key')
        action = request.POST.get('action')  # 'approve' or 'reject'

        if loan_key and action in ['approve', 'reject']:
            new_status = 'approved' if action == 'approve' else 'rejected'

            # Update the loan application status
            db.child("loan_applications").child(loan_key).update({
                'status': new_status,
                'date_reviewed': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })

            # If approved, update the user's balance
            if new_status == 'approved':
                loan_data = db.child("loan_applications").child(loan_key).get().val()
                user_email = loan_data.get('user_id')
                loan_amount = float(loan_data.get('amount', 0))

                # Search for the user in userRegistrations by email
                all_users = db.child("userRegistrations").get()
                for user in all_users.each():
                    user_data = user.val()
                    if user_data.get('email') == user_email:
                        user_key = user.key()
                        current_balance = float(user_data.get('balance', 0))
                        new_balance = current_balance + loan_amount
                        db.child("userRegistrations").child(user_key).update({'balance': new_balance})
                        break
                else:
                    print(f"User with email {user_email} not found.")

        return redirect('loan_approvals')

    return HttpResponse("Invalid request", status=400)


def reports(request):
    # Fetch savings
    savings_data = db.child("savings").get()
    savings_list = []
    total_savings = 0
    total_interest = 0

    if savings_data.each():
        for entry in savings_data.each():
            data = entry.val()
            amount = float(data.get('amount', 0))
            interest = float(data.get('interest_shown', 0))
            savings_list.append(data)
            total_savings += amount
            total_interest += interest

    # Fetch withdrawals
    withdrawals_data = db.child("withdrawals").get()
    withdrawals_list = []
    if withdrawals_data.each():
        for entry in withdrawals_data.each():
            withdrawals_list.append(entry.val())

    # Fetch loans
    loans_data = db.child("loan_applications").get()
    loans_list = []
    loan_applications = []
    total_loan_amount = 0
    approved_loans = 0
    for_approval = 0
    rejected_loans = 0

    if loans_data.each():
        for entry in loans_data.each():
            loan = entry.val()
            loan['key'] = entry.key()
            loan_applications.append(loan)

    if loans_data.each():
        for entry in loans_data.each():
            data = entry.val()
            loans_list.append(data)
            total_loan_amount += float(data.get('amount', 0))
            status = data.get('status', '').lower()
            if status == 'approved':
                approved_loans += 1
            elif status == 'pending':
                for_approval += 1
            elif status == 'rejected':
                rejected_loans += 1

    average_loan = total_loan_amount / len(loans_list) if loans_list else 0

    return render(request, 'admin/reports.html', {
        'savings': savings_list,
        'withdrawals': withdrawals_list,
        'loan_summary': {
            'total_amount': total_loan_amount,
            'total_count': len(loans_list),
            'average': average_loan,
            'approved': approved_loans,
            'pending': for_approval,
            'rejected': rejected_loans,
        },
        'loan_applications': loan_applications,
    })



def admin_logout(request):
    request.session.flush()   
    return redirect('admin_auth')