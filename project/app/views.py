from django.shortcuts import render, redirect
from django.template.loader import get_template
from django.http import HttpResponse
from django.http import HttpRequest
from django.conf import settings
import requests
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from .firebase import db
from django.http import JsonResponse 
import json
from django.core.mail import send_mail
import random

code = random.randint(100000, 999999)
# Create your views here.
def load(request):
    template = get_template('index.html')  # this will raise an error if not found
    return HttpResponse(template.render({}, request))

@csrf_exempt
def auth(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            action_type = data.get('type')

            if action_type == 'login':
                email = data.get('email')
                password = data.get('password')

                users = db.child("userRegistrations").get()
                user_found = False
                if users.each():
                    for user in users.each():
                        user_data = user.val()
                        if user_data.get('email') == email and user_data.get('password') == password:
                            user_found = True
                            break

                if user_found:
                    # Generate 6-digit OTP
                    otp_code = random.randint(100000, 999999)

                    # Send email with OTP
                    send_mail(
                        'Your Login OTP Code',
                        f'Your one-time login code is: {otp_code}',
                        'no-reply@yourdomain.com',  # from email
                        [email],
                        fail_silently=False,
                    )

                    # Optionally, save OTP to db or cache here for verification later

                    return JsonResponse({'success': True, 'message': 'Login successful, OTP sent', 'otp': otp_code})

                else:
                    return JsonResponse({'success': False, 'message': 'Invalid email or password'}, status=401)

            elif action_type == 'register':
                first_name = data.get('first_name')
                last_name = data.get('last_name')
                email = data.get('email')
                password = data.get('password')

                db.child("userRegistrations").push({
                    'first_name': first_name,
                    'last_name': last_name,
                    'email': email,
                    'password': password
                })
                return JsonResponse({'success': True, 'message': 'Registration successful'})

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
            email = data.get('email')
            code = data.get('code')

            if not email or not code:
                return JsonResponse({'success': False, 'message': 'Missing email or code'}, status=400)

            email_key = email.replace('.', '_').replace('@', '_at_')

            otp_data = db.child("userVerificationCodes").child(email_key).get()
            otp_value = otp_data.val()

            if not otp_value:
                return redirect ("userDashboard")

            if str(otp_value.get('otp')) == str(code):
                db.child("userVerificationCodes").child(email_key).remove()
                return JsonResponse({'success': True, 'message': 'Verification successful'})
            else:
                return JsonResponse({'success': False, 'message': 'Invalid code'}, status=401)

        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)

    return render(request, 'authentication/verify.html')


def userDashboard(request):
    return render(request, 'user-dashboard/index.html')

def deposit(request):
    return render(request, 'user-dashboard/deposit.html')

def interest(request):
    return render(request, 'user-dashboard/interest.html')

def record(request):
    return render(request, 'user-dashboard/record.html')

def withdrawal(request):
    return render(request, 'user-dashboard/withdrawal.html')

def loan(request):
    return render(request, 'user-dashboard/loan.html')