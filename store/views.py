from django.db.models import Count
from django.http import Http404
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.mixins import (
    CreateModelMixin,
    DestroyModelMixin,
    ListModelMixin,
    RetrieveModelMixin,
)
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet, ModelViewSet

from .models import Address, Cart, CartItem, Collection, Customer, Order, OrderItem, Product, Review
from .pagination import DefaultPagination
from .permissions import IsAdminOrReadOnly
from .serializers import (
    AddCartItemSerializer,
    AddressSerializer,
    CartItemSerializer,
    CartSerializer,
    CollectionSerializer,
    CreateOrderSerializer,
    CustomerSerializer,
    OrderSerializer,
    ProductSerializer,
    ReviewSerializer,
    UpdateCartItemSerializer,
    UpdateOrderSerializer,
)
from .filters import ProductFilter


class ProductViewSet(ModelViewSet):
    queryset = Product.objects.select_related("collection").all()
    serializer_class = ProductSerializer
    filter_backends = (DjangoFilterBackend, SearchFilter, OrderingFilter)
    filterset_class = ProductFilter
    search_fields = ("title", "description")
    ordering_fields = ("unit_price", "last_update")
    pagination_class = DefaultPagination
    permission_classes = (IsAdminOrReadOnly,)
    lookup_value_regex = r"\d+"

    def destroy(self, request, *args, **kwargs):
        if OrderItem.objects.filter(product_id=kwargs["pk"]).exists():
            return Response(
                {"detail": "Products in existing orders cannot be deleted."},
                status=status.HTTP_409_CONFLICT,
            )
        return super().destroy(request, *args, **kwargs)


class CollectionViewSet(ModelViewSet):
    queryset = Collection.objects.annotate(products_count=Count("products")).order_by("title", "pk")
    serializer_class = CollectionSerializer
    permission_classes = (IsAdminOrReadOnly,)

    def destroy(self, request, *args, **kwargs):
        if Product.objects.filter(collection_id=kwargs["pk"]).exists():
            return Response(
                {"detail": "Collections with products cannot be deleted."},
                status=status.HTTP_409_CONFLICT,
            )
        return super().destroy(request, *args, **kwargs)


class ReviewViewSet(ModelViewSet):
    queryset = Review.objects.none()
    serializer_class = ReviewSerializer
    permission_classes = (AllowAny,)

    def get_parent_product(self):
        try:
            product_id = int(self.kwargs["product_pk"])
        except (TypeError, ValueError) as exc:
            raise Http404 from exc
        return get_object_or_404(Product, pk=product_id)

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return self.queryset
        return Review.objects.filter(product=self.get_parent_product())

    def get_serializer_context(self):
        if getattr(self, "swagger_fake_view", False):
            return super().get_serializer_context()
        return {**super().get_serializer_context(), "product_id": self.get_parent_product().pk}


class CartViewSet(
    ListModelMixin,
    CreateModelMixin,
    RetrieveModelMixin,
    DestroyModelMixin,
    GenericViewSet,
):
    queryset = Cart.objects.prefetch_related("items__product").all()
    serializer_class = CartSerializer
    permission_classes = (IsAuthenticated,)
    lookup_value_regex = r"[0-9a-f-]{36}"

    def get_queryset(self):
        return super().get_queryset().filter(owner=self.request.user).order_by("created_at", "pk")

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class CartItemViewSet(ModelViewSet):
    queryset = CartItem.objects.none()
    http_method_names = ("get", "post", "patch", "delete", "head", "options")
    permission_classes = (IsAuthenticated,)

    def get_serializer_class(self):
        if self.request.method == "POST":
            return AddCartItemSerializer
        if self.request.method == "PATCH":
            return UpdateCartItemSerializer
        return CartItemSerializer

    def get_serializer_context(self):
        return {
            **super().get_serializer_context(),
            "cart_id": self.kwargs["cart_pk"],
            "user_id": self.request.user.id,
        }

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return self.queryset
        cart = get_object_or_404(Cart, pk=self.kwargs["cart_pk"], owner=self.request.user)
        return CartItem.objects.filter(cart=cart).select_related("product").order_by("pk")


class CustomerViewSet(ModelViewSet):
    queryset = Customer.objects.select_related("user").all()
    serializer_class = CustomerSerializer
    permission_classes = (IsAdminUser,)

    @action(detail=True, permission_classes=(IsAuthenticated,))
    def history(self, request, pk=None):
        customer = get_object_or_404(Customer.objects.select_related("user"), pk=pk)
        if customer.user_id != request.user.id and not request.user.has_perm("store.view_history"):
            return Response(
                {"detail": "You do not have permission to view this history."},
                status=status.HTTP_403_FORBIDDEN,
            )
        orders = Order.objects.filter(customer=customer).prefetch_related("items__product").order_by("-placed_at", "-pk")
        return Response(OrderSerializer(orders, many=True).data)

    @action(detail=False, methods=("GET", "PUT"), permission_classes=(IsAuthenticated,))
    def me(self, request):
        customer, _ = Customer.objects.get_or_create(user_id=request.user.id)
        if request.method == "GET":
            return Response(CustomerSerializer(customer).data)
        serializer = CustomerSerializer(customer, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(detail=False, methods=("GET", "PUT"), permission_classes=(IsAuthenticated,))
    def address(self, request):
        customer, _ = Customer.objects.get_or_create(user_id=request.user.id)
        address = Address.objects.filter(customer=customer).first()
        if request.method == "GET":
            return Response(AddressSerializer(address).data if address else None)
        serializer = AddressSerializer(address, data=request.data)
        serializer.is_valid(raise_exception=True)
        Address.objects.update_or_create(customer=customer, defaults=serializer.validated_data)
        return Response(AddressSerializer(Address.objects.get(customer=customer)).data)


class OrderViewSet(ModelViewSet):
    http_method_names = ("get", "post", "patch", "delete", "head", "options")

    def get_permissions(self):
        if self.request.method in ("PATCH", "DELETE"):
            return (IsAdminUser(),)
        return (IsAuthenticated(),)

    def create(self, request, *args, **kwargs):
        serializer = CreateOrderSerializer(
            data=request.data, context={"user_id": request.user.id}
        )
        serializer.is_valid(raise_exception=True)
        order = serializer.save()
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)

    def get_serializer_class(self):
        if self.request.method == "POST":
            return CreateOrderSerializer
        if self.request.method == "PATCH":
            return UpdateOrderSerializer
        return OrderSerializer

    def get_queryset(self):
        orders = Order.objects.select_related("customer").prefetch_related("items__product")
        if self.request.user.is_staff:
            return orders.order_by("-placed_at", "-pk")
        return orders.filter(customer__user_id=self.request.user.id).order_by("-placed_at", "-pk")
