from django.db import models
from django.contrib.auth.hashers import make_password, check_password
from django.contrib.auth.models import User

class Tenant(models.Model):
    assigned_landlord = models.ForeignKey(User, on_delete=models.CASCADE)
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    address = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=100)
    password = models.CharField(max_length=128)
    unit = models.CharField(max_length=50)
    lease_start = models.DateField()
    lease_end = models.DateField()
    rent = models.DecimalField(max_digits=10, decimal_places=2)
    deposit = models.DecimalField(max_digits=10, decimal_places=2)
    payment_status = models.CharField(max_length=20, default="Pending")
    contract_url = models.URLField()
    status = models.CharField(max_length=20, default="Active")

    first_login = models.BooleanField(default=True)
    is_active = models.BooleanField(default=False)
    last_login = models.DateTimeField(blank=True, null=True)

    def set_password(self, raw_password):
        self.password = make_password(raw_password)
        self.save()

    def check_password(self, raw_password):
        return check_password(raw_password, self.password)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"




class MaintenanceRequest(models.Model):
    requester = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    date_requested = models.DateField()
    maintenance_type = models.CharField(max_length=20)
    request_status = models.CharField(max_length=20, default="Pending")
    other_description = models.TextField(blank=True, default="")
    description = models.TextField()
    completion_date = models.DateField(blank=True, null=True)
    remarks = models.TextField(blank=True, default="")

    def __str__(self):
        return f"{self.maintenance_type} - {self.date_requested}"


class Payment(models.Model):
    METHOD_CHOICES = [
        ("BPI", "BPI"),
        ("BDO", "BDO"),
        ("GCash", "GCash"),
        ("Other", "Other"),
    ]
    STATUS_CHOICES = [
        ("Pending", "Pending"),
        ("Approved", "Approved"),
        ("Disapproved", "Disapproved"),
    ]
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="payments")
    title = models.CharField(max_length=100)
    method = models.CharField(max_length=20, choices=METHOD_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    reference_number = models.CharField(max_length=50)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Pending")
    created_at = models.DateTimeField(auto_now_add=True)
    date_verified = models.DateField(blank=True, null=True)

    def __str__(self):
        return f"{self.title} - {self.amount} ({self.method}) - {self.status}"
