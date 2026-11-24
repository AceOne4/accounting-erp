"""Tenancy foundation.

Decision (default, change before any domain model is ported): one database, one
shared schema, every business row belongs to a Company. Adding this later means
touching every table, so it goes in first.
"""
from django.conf import settings
from django.db import models
from simple_history.models import HistoricalRecords


class Company(models.Model):
    name = models.CharField(max_length=200)
    name_en = models.CharField(max_length=200, blank=True)
    base_currency = models.CharField(max_length=3, default="EGP")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    history = HistoricalRecords()

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "companies"

    def __str__(self):
        return self.name


class Membership(models.Model):
    """Which users may work in which company, and in which role."""

    class Role(models.TextChoices):
        ACCOUNTANT = "accountant", "Accountant"
        REVIEWER = "reviewer", "Reviewer"
        CHIEF = "chief_accountant", "Chief accountant"
        ADMIN = "system_admin", "System admin"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships"
    )
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=20, choices=Role.choices)
    history = HistoricalRecords()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "company"], name="one_membership_per_company")
        ]

    def __str__(self):
        return f"{self.user} @ {self.company} ({self.role})"


class CompanyQuerySet(models.QuerySet):
    def for_company(self, company):
        return self.filter(company=company)


class CompanyOwned(models.Model):
    """Abstract base for every business table (accounts, entries, products...)."""

    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="+")

    objects = CompanyQuerySet.as_manager()

    class Meta:
        abstract = True
