"""Load safe, repeatable sample data for the local showcase."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from store.models import Collection, Product


class Command(BaseCommand):
    help = "Create the showcase admin, demo customer, collections, and products."

    def handle(self, *args, **options):
        User = get_user_model()
        admin, created = User.objects.get_or_create(
            username="demo-admin",
            defaults={"email": "admin@example.com", "is_staff": True, "is_superuser": True},
        )
        if created:
            admin.set_password("Demo-admin-123!")
            admin.save(update_fields=["password"])
        customer, created = User.objects.get_or_create(
            username="demo-customer", defaults={"email": "customer@example.com"}
        )
        if created:
            customer.set_password("Demo-customer-123!")
            customer.save(update_fields=["password"])

        bags, _ = Collection.objects.get_or_create(title="Bags")
        accessories, _ = Collection.objects.get_or_create(title="Accessories")
        samples = [
            ("Everyday Canvas Tote", "everyday-canvas-tote", "Durable cotton tote for daily errands.", Decimal("24.95"), 25, bags),
            ("Compact Crossbody Bag", "compact-crossbody-bag", "Lightweight crossbody with adjustable strap.", Decimal("39.50"), 12, bags),
            ("Minimal Wallet", "minimal-wallet", "Slim wallet with room for daily essentials.", Decimal("18.00"), 40, accessories),
            ("Classic Keychain", "classic-keychain", "A simple metal keychain in a polished finish.", Decimal("7.50"), 100, accessories),
        ]
        for title, slug, description, price, inventory, collection in samples:
            Product.objects.update_or_create(
                slug=slug,
                defaults={"title": title, "description": description, "unit_price": price,
                          "inventory": inventory, "collection": collection},
            )
        self.stdout.write(self.style.SUCCESS(
            "Showcase data is ready. Admin: demo-admin / Demo-admin-123!; "
            "customer: demo-customer / Demo-customer-123!. Local demo credentials only."
        ))
