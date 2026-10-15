from decimal import Decimal
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase

from .models import Cart, CartItem, Collection, Customer, Order, OrderItem, Product


User = get_user_model()


class StoreApiTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="buyer", email="buyer@example.com", password="Valid-pass123")
        self.other_user = User.objects.create_user(username="other", email="other@example.com", password="Valid-pass123")
        self.customer = Customer.objects.get(user=self.user)
        self.collection = Collection.objects.create(title="Accessories")
        self.product = Product.objects.create(
            title="Canvas Bag", slug="canvas-bag", unit_price=Decimal("12.50"),
            inventory=5, collection=self.collection,
        )

    def authenticate(self, user=None):
        self.client.force_authenticate(user=user or self.user)

    def test_products_and_collections_are_public_and_paginated(self):
        response = self.client.get("/store/products/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["title"], "Canvas Bag")
        self.assertEqual(self.client.get("/store/collections/").status_code, 200)

    def test_product_writes_require_staff(self):
        self.authenticate()
        response = self.client.post("/store/products/", {
            "title": "New", "unit_price": "1.00", "inventory": 1,
            "collection": self.collection.pk,
        })
        self.assertEqual(response.status_code, 403)

    def test_users_only_see_their_own_carts(self):
        own_cart = Cart.objects.create(owner=self.user)
        foreign_cart = Cart.objects.create(owner=self.other_user)
        self.authenticate()
        self.assertEqual(self.client.get(f"/store/carts/{own_cart.pk}/").status_code, 200)
        self.assertEqual(self.client.get(f"/store/carts/{foreign_cart.pk}/").status_code, 404)
        self.assertEqual(self.client.get("/store/carts/").data["count"], 1)

    def test_cart_creation_and_items_are_owned_by_authenticated_user(self):
        self.authenticate()
        created = self.client.post("/store/carts/", {}, format="json")
        self.assertEqual(created.status_code, 201)
        cart_id = created.data["id"]
        self.assertEqual(Cart.objects.get(pk=cart_id).owner, self.user)
        added = self.client.post(f"/store/carts/{cart_id}/items/", {
            "product_id": self.product.pk, "quantity": 2,
        }, format="json")
        self.assertEqual(added.status_code, 201)
        self.assertEqual(added.data["quantity"], 2)
        foreign_cart = Cart.objects.create(owner=self.other_user)
        denied = self.client.post(f"/store/carts/{foreign_cart.pk}/items/", {
            "product_id": self.product.pk, "quantity": 1,
        }, format="json")
        self.assertEqual(denied.status_code, 404)

    def test_cart_quantity_updates_add_atomically_and_validate_positive_quantity(self):
        cart = Cart.objects.create(owner=self.user)
        self.authenticate()
        url = f"/store/carts/{cart.pk}/items/"
        self.client.post(url, {"product_id": self.product.pk, "quantity": 2}, format="json")
        response = self.client.post(url, {"product_id": self.product.pk, "quantity": 3}, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(CartItem.objects.get(cart=cart, product=self.product).quantity, 5)
        invalid = self.client.post(url, {"product_id": self.product.pk, "quantity": 0}, format="json")
        self.assertEqual(invalid.status_code, 400)
        over_limit = self.client.post(url, {"product_id": self.product.pk, "quantity": 100}, format="json")
        self.assertEqual(over_limit.status_code, 400)

    def test_checkout_creates_order_snapshots_price_decrements_stock_and_consumes_cart(self):
        cart = Cart.objects.create(owner=self.user)
        CartItem.objects.create(cart=cart, product=self.product, quantity=2)
        self.authenticate()
        response = self.client.post("/store/orders/", {"cart_id": str(cart.pk)}, format="json")
        self.assertEqual(response.status_code, 201)
        order = Order.objects.get(pk=response.data["id"])
        item = OrderItem.objects.get(order=order)
        self.assertEqual(order.customer, self.customer)
        self.assertEqual(item.unit_price, Decimal("12.50"))
        self.assertEqual(self.product.__class__.objects.get(pk=self.product.pk).inventory, 3)
        self.assertFalse(Cart.objects.filter(pk=cart.pk).exists())
        repeated = self.client.post("/store/orders/", {"cart_id": str(cart.pk)}, format="json")
        self.assertEqual(repeated.status_code, 400)

    def test_checkout_rejects_foreign_and_empty_carts(self):
        self.authenticate()
        foreign_cart = Cart.objects.create(owner=self.other_user)
        self.assertEqual(self.client.post("/store/orders/", {"cart_id": str(foreign_cart.pk)}, format="json").status_code, 400)
        empty_cart = Cart.objects.create(owner=self.user)
        self.assertEqual(self.client.post("/store/orders/", {"cart_id": str(empty_cart.pk)}, format="json").status_code, 400)

    def test_checkout_with_insufficient_stock_rolls_back_without_consuming_cart(self):
        cart = Cart.objects.create(owner=self.user)
        CartItem.objects.create(cart=cart, product=self.product, quantity=6)
        self.authenticate()
        response = self.client.post("/store/orders/", {"cart_id": str(cart.pk)}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Order.objects.exists())
        self.assertTrue(Cart.objects.filter(pk=cart.pk).exists())
        self.product.refresh_from_db()
        self.assertEqual(self.product.inventory, 5)

    def test_checkout_rolls_back_stock_for_all_items_when_one_is_unavailable(self):
        second_product = Product.objects.create(
            title="Leather Pouch", slug="leather-pouch", unit_price=Decimal("19.00"),
            inventory=1, collection=self.collection,
        )
        cart = Cart.objects.create(owner=self.user)
        CartItem.objects.create(cart=cart, product=self.product, quantity=2)
        CartItem.objects.create(cart=cart, product=second_product, quantity=2)
        self.authenticate()
        response = self.client.post("/store/orders/", {"cart_id": str(cart.pk)}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Order.objects.exists())
        self.assertTrue(Cart.objects.filter(pk=cart.pk).exists())
        self.product.refresh_from_db()
        second_product.refresh_from_db()
        self.assertEqual(self.product.inventory, 5)
        self.assertEqual(second_product.inventory, 1)

    def test_user_only_sees_their_orders(self):
        other_customer = Customer.objects.get(user=self.other_user)
        own_order = Order.objects.create(customer=self.customer)
        foreign_order = Order.objects.create(customer=other_customer)
        self.authenticate()
        response = self.client.get("/store/orders/")
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], own_order.pk)
        self.assertEqual(self.client.get(f"/store/orders/{foreign_order.pk}/").status_code, 404)

    def test_customer_me_is_scoped_to_the_current_user(self):
        self.authenticate()
        response = self.client.get("/store/customers/me/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["user_id"], self.user.pk)

    def test_review_creation_is_nested_under_a_real_product(self):
        response = self.client.post(f"/store/products/{self.product.pk}/reviews/", {
            "name": "Guest", "description": "Great bag",
        }, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.client.post(f"/store/products/{uuid4()}/reviews/", {
            "name": "Guest", "description": "No parent",
        }, format="json").status_code, 404)

    def test_anonymous_users_cannot_create_carts_or_orders(self):
        self.assertEqual(self.client.post("/store/carts/", {}, format="json").status_code, 401)
        self.assertEqual(self.client.post("/store/orders/", {"cart_id": str(uuid4())}, format="json").status_code, 401)

    def test_jwt_login_refresh_and_public_api_docs(self):
        token_response = self.client.post("/auth/jwt/create/", {
            "username": "buyer", "password": "Valid-pass123",
        }, format="json")
        self.assertEqual(token_response.status_code, 200)
        refresh_response = self.client.post("/auth/jwt/refresh/", {
            "refresh": token_response.data["refresh"],
        }, format="json")
        self.assertEqual(refresh_response.status_code, 200)
        self.assertTrue(refresh_response.data["access"])
        self.assertEqual(self.client.get("/api/docs/").status_code, 200)

    def test_customer_can_view_own_order_history(self):
        order = Order.objects.create(customer=self.customer)
        self.authenticate()
        response = self.client.get(f"/store/customers/{self.customer.pk}/history/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]["id"], order.pk)

    def test_customer_can_manage_shipping_address(self):
        self.authenticate()
        url = "/store/customers/address/"
        self.assertIsNone(self.client.get(url).data)
        saved = self.client.put(url, {
            "street": "10 Main Street", "city": "Dhaka", "zip": "1207",
        }, format="json")
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(self.client.get(url).data["city"], "Dhaka")
