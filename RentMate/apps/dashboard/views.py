from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.contrib.auth.hashers import check_password, make_password
from django.db.models import Sum
from datetime import datetime
from datetime import date
from decimal import Decimal
from django.db.models import Q
from django.views.decorators.http import require_POST
from .forms import TenantRegisterForm, MaintenanceRequestForm, LandlordMaintenanceUpdateForm, PaymentForm
from .models import Tenant, MaintenanceRequest, Payment
from django.views.decorators.cache import never_cache


# --- LANDLORD SIDE ---

@login_required(login_url='landlord_login')
def tenant_list_view(request):
    tenants = Tenant.objects.filter(assigned_landlord=request.user)
    query = request.GET.get('q', '').strip()

    if query:
        tenants = tenants.filter(
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(email__icontains=query)
        )

    status_filter = request.GET.get('status', 'all')
    payment_filter = request.GET.get('payment', 'all')

    if status_filter != 'all':
        tenants = tenants.filter(status__iexact=status_filter)

    if payment_filter != 'all':
        tenants = tenants.filter(payment_status__iexact=payment_filter)

    sort_by = request.GET.get('sort', 'name')
    sort_map = {
        'name': 'first_name',
        'unit': 'unit',
        'start_date': 'lease_start',
        'end_date': 'lease_end',
        'rent': 'rent',
        'payment_status': 'payment_status',
        'rental_status': 'status',
    }
    if sort_by in sort_map:
        tenants = tenants.order_by(sort_map[sort_by])

    return render(request, "home_app/tenant-list.html", {
        'tenants': tenants,
        'search_query': query,
        'current_status': status_filter or 'all',
        'current_payment': payment_filter or 'all',
        'current_sort': sort_by,
    })


def tenant_register(request):
    if not request.user.is_authenticated:
        return redirect('landlord_login')

    if request.method == 'POST':
        form = TenantRegisterForm(request.POST)
        if form.is_valid():
            tenant = form.save(commit=False)
            tenant.assigned_landlord = request.user
            tenant.is_active = False
            tenant.first_login = True
            tenant.status = 'Inactive'
            tenant.save()

            temp_password = form.cleaned_data['password']
            send_mail(
                'Your Tenant Account - RentMate',
                f"""
Hi {tenant.first_name},

Your account has been created.

Email: {tenant.email}
Temporary Password: {temp_password}

Please log in at: [http://127.0.0.1:8000/home/tenant/login/](http://127.0.0.1:8000/home/tenant/login/)

Thank you,
RentMate Team
""",
                settings.EMAIL_HOST_USER,
                [tenant.email],
                fail_silently=False
            )

            messages.success(request, 'Tenant created successfully! Credentials sent via email.')
            return redirect('tenant_list')
    else:
        form = TenantRegisterForm()

    return render(request, 'home_app/tenant-account-register.html', {'form': form})


def edit_tenant(request, tenant_id):
    tenant = get_object_or_404(Tenant, id=tenant_id)
    if request.method == 'POST':
        form = TenantRegisterForm(request.POST, instance=tenant)
        if form.is_valid():
            if 'password' in form.cleaned_data and form.cleaned_data['password']:
                tenant.password = make_password(form.cleaned_data['password'])
            form.save()
            tenant.save()
            messages.success(request, 'Tenant updated successfully!')
            return redirect('tenant_list')
    else:
        form = TenantRegisterForm(instance=tenant)
    return render(request, 'home_app/tenant-account-register.html', {'form': form, 'edit_mode': True})


def delete_tenant(request, tenant_id):
    tenant = get_object_or_404(Tenant, id=tenant_id)
    tenant.delete()
    messages.success(request, 'Tenant deleted successfully.')
    return redirect('tenant_list')


# --- TENANT LOGIN, LOGOUT & PASSWORD CHANGE ---

def tenant_login(request):
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")

        try:
            tenant = Tenant.objects.get(email=email)
        except Tenant.DoesNotExist:
            messages.error(request, "Invalid credentials.")
            return redirect("tenant_login")

        if check_password(password, tenant.password):
            request.session["tenant_id"] = tenant.id

            if tenant.first_login:
                messages.info(request, "Update password required.")
                return redirect("tenant_change_password")

            tenant.is_active = True
            tenant.save()
            messages.success(request, f"Welcome back, {tenant.first_name}!")
            return redirect("tenant_home")
        else:
            messages.error(request, "Invalid credentials.")
            return redirect("tenant_login")

    return render(request, "logins/tenant-login.html")


def tenant_logout(request):
    # Remove tenant id from session
    request.session.pop("tenant_id", None)
    messages.success(request, "You have been logged out successfully")
    return redirect("tenant_login")


def tenant_change_password(request):
    tenant_id = request.session.get("tenant_id")
    if not tenant_id:
        return redirect("tenant_login")

    tenant = Tenant.objects.get(id=tenant_id)

    if request.method == "POST":
        password = request.POST.get("password")
        confirm_password = request.POST.get("confirm_password")
        if password == confirm_password:
            tenant.password = make_password(password)
            tenant.first_login = False
            tenant.is_active = True
            tenant.save()
            messages.success(request, "Password updated successfully! You can now login.")
            return redirect("tenant_login")
        else:
            messages.error(request, "Passwords do not match.")

    return render(request, "home_app/tenant-change-password.html")


# --- TENANT DASHBOARD ---

@never_cache
def tenant_home(request):
    tenant_id = request.session.get("tenant_id")
    if not tenant_id:
        messages.info(request, "Please log in to continue")
        return redirect("tenant_login")

    tenant = Tenant.objects.get(id=tenant_id)
    requests = MaintenanceRequest.objects.filter(requester=tenant).order_by('-date_requested')

    pending_count = requests.filter(request_status='Pending').count()
    approved_count = requests.filter(request_status='Approved').count()
    completed_count = requests.filter(request_status='Completed').count()

    today = datetime.now().date()
    days_remaining = (tenant.lease_end - today).days
    if days_remaining > 30:
        months = days_remaining // 30
        remaining_days = days_remaining % 30
        lease_remaining = f"{months} month{'s' if months > 1 else ''}"
        if remaining_days > 0:
            lease_remaining += f" and {remaining_days} day{'s' if remaining_days > 1 else ''}"
    else:
        lease_remaining = f"{days_remaining} day{'s' if days_remaining > 1 else ''}"

    lease_duration_months = (tenant.lease_end - tenant.lease_start).days // 30
    initial_balance = tenant.rent * Decimal(1 if lease_duration_months == 0 else lease_duration_months)
    total_paid = tenant.payments.filter(status="Approved").aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    outstanding_balance = initial_balance - total_paid

    payment_status = ("Paid" if outstanding_balance <= 0 else "Unpaid")

    return render(request, "home_app_tenant/tenant-home.html", {
        "tenant": tenant,
        "requests": requests,
        "pending_count": pending_count,
        "approved_count": approved_count,
        "completed_count": completed_count,
        "payment_status": payment_status,
        "lease_remaining": lease_remaining,
        "outstanding_balance": outstanding_balance,
    })


# --- TENANT MAINTENANCE REQUESTS ---

@never_cache
def tenant_maintenance_list_view(request):
    tenant_id = request.session.get("tenant_id")
    if not tenant_id:
        messages.info(request, "Please log in to continue")
        return redirect('tenant_login')

    tenant = Tenant.objects.get(id=tenant_id)
    requests = MaintenanceRequest.objects.filter(requester=tenant).order_by('-date_requested')

    return render(request, 'home_app_tenant/tenant-maintenance-list.html', {
        "tenant": tenant,
        "requests": requests
    })


@never_cache
def tenant_maintenance_add_view(request):
    tenant_id = request.session.get("tenant_id")
    if not tenant_id:
        messages.info(request, "Please log in to continue")
        return redirect('tenant_login')

    tenant = Tenant.objects.get(id=tenant_id)
    maintenance_requests = MaintenanceRequest.objects.filter(requester=tenant).order_by('-date_requested')[:5]

    if request.method == 'POST':
        problems = request.POST.getlist('problem[]')
        other_description = request.POST.get('other_description', '')
        description = request.POST.get('description', '')

        if problems:
            maintenance_type = ', '.join(problems)
        else:
            messages.error(request, 'Please select at least one problem.')
            return render(request, 'home_app_tenant/tenant-maintenance.html', {
                'tenant': tenant,
                'maintenance_requests': maintenance_requests
            })

        if 'Others' in problems and other_description:
            maintenance_type = maintenance_type.replace('Others', f'Others: {other_description}')

        if not description:
            messages.error(request, 'Please provide a description.')
            return render(request, 'home_app_tenant/tenant-maintenance.html', {
                'tenant': tenant,
                'maintenance_requests': maintenance_requests
            })

        MaintenanceRequest.objects.create(
            requester=tenant,
            date_requested=timezone.localtime().date(),
            maintenance_type=maintenance_type,
            other_description=other_description if 'Others' in problems else '',
            description=description
        )
        messages.success(request, 'Maintenance request submitted successfully!')
        return redirect('tenant_maintenance')

    return render(request, 'home_app_tenant/tenant-maintenance.html', {
        'tenant': tenant,
        'maintenance_requests': maintenance_requests
    })


# --- TENANT PAYMENTS ---

@never_cache
def tenant_payment(request):
    tenant_id = request.session.get("tenant_id")
    if not tenant_id:
        messages.info(request, "Please log in to continue")
        return redirect('tenant_login')

    tenant = Tenant.objects.get(id=tenant_id)

    if request.method == 'POST':
        form = PaymentForm(request.POST)
        if form.is_valid():
            Payment.objects.create(
                tenant=tenant,
                title=form.cleaned_data['title'],
                method=form.cleaned_data['method'],
                amount=form.cleaned_data['amount'],
                reference_number=form.cleaned_data['reference_number'],
            )
            messages.success(request, 'Payment submitted successfully!')
            return redirect('tenant_home')
    else:
        form = PaymentForm()

    return render(request, 'home_app_tenant/tenant-payment.html', {
        'form': form,
        'tenant': tenant,
    })


@never_cache
def tenant_maintenance_edit_view(request, request_id):
    tenant_id = request.session.get("tenant_id")
    if not tenant_id:
        messages.info(request, "Please log in to continue")
        return redirect('tenant_login')

    maintenance_request = get_object_or_404(MaintenanceRequest, id=request_id, requester_id=tenant_id)

    if maintenance_request.request_status in ["Approved", "Completed"]:
        messages.error(request, "You cannot edit an approved or completed request.")
        return redirect('tenant_home')

    if request.method == 'POST':
        form = MaintenanceRequestForm(request.POST, instance=maintenance_request)
        if form.is_valid():
            form.save()
            messages.success(request, "Maintenance request updated successfully!")
            return redirect('tenant_home')
    else:
        form = MaintenanceRequestForm(instance=maintenance_request)

    return render(request, 'home_app_tenant/tenant-maintenance-edit.html', {'form': form})


@never_cache
def tenant_maintenance_delete_view(request, request_id):
    tenant_id = request.session.get("tenant_id")
    if not tenant_id:
        messages.info(request, "Please log in to continue")
        return redirect('tenant_login')

    maintenance_request = get_object_or_404(MaintenanceRequest, id=request_id, requester_id=tenant_id)

    if maintenance_request.request_status in ["Approved", "Completed"]:
        messages.error(request, "You cannot delete an approved or completed request.")
    else:
        maintenance_request.delete()
        messages.success(request, "Maintenance request deleted successfully!")

    return redirect('tenant_home')


# --- LANDLORD MAINTENANCE MANAGEMENT ---

@never_cache
@login_required(login_url='landlord_login')
def home_view(request):
<<<<<<< HEAD
    try:
        # Count active tenants
        active_tenant_count = Tenant.objects.filter(status="Active").count()

        # Calculate monthly revenue
        current_month = date.today().month
        current_year = date.today().year
        monthly_revenue = Payment.objects.filter(
            status="Approved",
            date_verified__month=current_month,
            date_verified__year=current_year
        ).aggregate(total=Sum('amount'))['total'] or 0

        # Count leases ending this month
        lease_renewal_count = Tenant.objects.filter(
            lease_end__month=current_month,
            lease_end__year=current_year
        ).count()

        # Maintenance requests
        requests = MaintenanceRequest.objects.all()
        pending_count = requests.filter(request_status='Pending').count()

        context = {
            'active_tenant_count': active_tenant_count,
            'monthly_revenue': monthly_revenue,
            'lease_renewal_count': lease_renewal_count,
            'requests': requests,
            'pending_count': pending_count,
        }

        return render(request, "home_app/home.html", context)
    except Exception as e:
        print(f"Error in home_view: {e}")
        raise
=======
    requests = MaintenanceRequest.objects.filter(requester__assigned_landlord=request.user).order_by('-date_requested')
    pending_count = requests.filter(request_status='Pending').count()
>>>>>>> upstream/main


@login_required(login_url='landlord_login')
def landlord_maintenance_list_view(request):
    requests = MaintenanceRequest.objects.filter(requester__assigned_landlord=request.user).order_by('-date_requested')
    return render(request, 'home_app/landlord-maintenance-list.html', {'requests': requests})


@login_required(login_url='landlord_login')
def landlord_maintenance_update_view(request, request_id):
    maintenance_request = get_object_or_404(MaintenanceRequest, id=request_id)

    if request.method == "POST":
        remarks = request.POST.get("remarks")
        completion_date = request.POST.get("completion_date")

        maintenance_request.remarks = remarks

        if remarks == "Done":
            maintenance_request.request_status = "Completed"
            if completion_date:
                maintenance_request.completion_date = datetime.strptime(completion_date, "%Y-%m-%d").date()
            else:
                maintenance_request.completion_date = timezone.localtime().date()
        elif remarks == "Canceled":
            maintenance_request.request_status = "Canceled"
            maintenance_request.completion_date = None
        else:
            maintenance_request.request_status = "Pending"
            if completion_date:
                maintenance_request.completion_date = datetime.strptime(completion_date, "%Y-%m-%d").date()
            else:
                maintenance_request.completion_date = None

        maintenance_request.save()
        messages.success(request, "Maintenance request updated successfully.")
        return redirect("landlord_maintenance_list")

    return render(request, "home_app/landlord-maintenance-update.html", {
        "request_item": maintenance_request
    })


# ----- LANDLORD PROOF OF PAYMENTS LIST --------

@login_required(login_url='landlord_login')
def landlord_payments_list_view(request):
<<<<<<< HEAD
    payments = Payment.objects.all().order_by('-created_at')
=======

    payments = Payment.objects.filter(tenant__assigned_landlord=request.user).order_by('-created_at')

>>>>>>> upstream/main
    return render(request, 'home_app/landlord-payments-list.html', {
        "payments": payments
    })


@login_required(login_url='landlord_login')
def landlord_payments_update_view(request, payment_id):
    payment = Payment.objects.get(id=payment_id)
    if request.method == "POST":
        status = request.POST.get("status")
        date_verified = request.POST.get("date_verified")

        if status != payment.status:
            payment.status = status
            payment.date_verified = date_verified
            payment.save()
            return redirect("landlord_payments_list")

<<<<<<< HEAD
    return render(request, 'home_app/landlord-payments-list-update.html', {
        "payment": payment
    })

=======
    return render(request, 'home_app/landlord-payments-list-update.html',{
        "payment": payment,
    })

@require_POST
def approve_payment(request,payment_id):
    payment = get_object_or_404(Payment, id=payment_id)
    payment.status = "Approved"
    payment.date_verified = datetime.now().date()
    payment.save()
    return redirect('landlord_payments_list')
>>>>>>> upstream/main

# Landlord - Tenant Profile View

@login_required(login_url='landlord_login')
def landlord_tenant_profile_view(request, tenant_id):
    tenant = get_object_or_404(Tenant, id=tenant_id)
    approved_payments = Payment.objects.filter(tenant=tenant, status="Approved").order_by('date_verified')
    activities = Payment.objects.filter(tenant=tenant).exclude(status="Approved").order_by('created_at')
    requests = MaintenanceRequest.objects.filter(requester=tenant).order_by('date_requested')

    return render(request, 'home_app/landlord-tenant-profile.html', {
        "tenant": tenant,
        "approved_payments": approved_payments,
        "activities": activities,
        "requests": requests,
    })
