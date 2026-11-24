from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from accounting.chart import seed_default_chart
from core.models import Company, Membership


class Command(BaseCommand):
    help = "Create (or reuse) a company, load the default chart of accounts, optionally add a user."

    def add_arguments(self, parser):
        parser.add_argument("name")
        parser.add_argument("--name-en", default="")
        parser.add_argument("--currency", default="EGP")
        parser.add_argument("--user", help="Existing username to add as a member")
        parser.add_argument(
            "--role",
            default=Membership.Role.CHIEF,
            choices=[r.value for r in Membership.Role],
        )

    def handle(self, *args, name, name_en, currency, user, role, **options):
        company, made = Company.objects.get_or_create(
            name=name, defaults={"name_en": name_en, "base_currency": currency}
        )
        self.stdout.write(f"{'Created' if made else 'Using'} company #{company.pk}: {company.name}")

        created, updated = seed_default_chart(company)
        self.stdout.write(f"Chart of accounts: {created} created, {updated} updated")

        if user:
            try:
                account_user = get_user_model().objects.get(username=user)
            except get_user_model().DoesNotExist:
                raise CommandError(f"User '{user}' does not exist")
            _, joined = Membership.objects.update_or_create(
                user=account_user, company=company, defaults={"role": role}
            )
            self.stdout.write(f"{user} is now {role} in {company.name}")
