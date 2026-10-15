from decimal import Decimal
from django.db import transaction
from django.db.models import F
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from .signals import order_created
from .models import Address, Cart, CartItem, Customer, Order, OrderItem, Product, Collection, Review

class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ['id', 'title', 'description', 'inventory','slug', 'unit_price', 'price_with_tax', 'collection']
    price_with_tax = serializers.SerializerMethodField(method_name='calculate_tax')
    @extend_schema_field(serializers.DecimalField(max_digits=10, decimal_places=2))
    def calculate_tax(self, product: Product):
        return product.unit_price * Decimal("1.10")

class CollectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Collection
        fields = ['id', 'title','products_count']
    products_count=serializers.IntegerField(read_only=True)

class ReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model=Review
        fields=['id','date','name','description']

    def create(self, validated_data):
        product_id=self.context['product_id']
        return Review.objects.create(product_id=product_id, **validated_data)

class SimpleProductSerializer(serializers.ModelSerializer):
    class Meta:
        model=Product
        fields=['id','title','unit_price']

class CartItemSerializer(serializers.ModelSerializer):
    product=SimpleProductSerializer()
    total_price=serializers.SerializerMethodField()

    @extend_schema_field(serializers.DecimalField(max_digits=10, decimal_places=2))
    def get_total_price(self,cart_item:CartItem):
        return cart_item.quantity * cart_item.product.unit_price

    class Meta:
        model=CartItem
        fields=['id','product','quantity','total_price']

class CartSerializer(serializers.ModelSerializer):
    id=serializers.UUIDField(read_only=True)
    items=CartItemSerializer(many=True, read_only=True)
    total_price=serializers.SerializerMethodField()

    @extend_schema_field(serializers.DecimalField(max_digits=12, decimal_places=2))
    def get_total_price(self, cart):
        return sum([item.quantity * item.product.unit_price for item in cart.items.all()])

    class Meta:
        model = Cart
        fields = ['id','items','total_price']

class AddCartItemSerializer(serializers.ModelSerializer):
    product_id=serializers.IntegerField()
    quantity=serializers.IntegerField(min_value=1, max_value=100)

    def validate_product_id(self,value):
        if not Product.objects.filter(pk=value).exists():
            raise serializers.ValidationError('No products found!')
        return value

    def save(self, **kwargs):
        cart=get_object_or_404(Cart, pk=self.context['cart_id'], owner_id=self.context['user_id'])
        product_id=self.validated_data['product_id']
        quantity=self.validated_data['quantity']
        with transaction.atomic():
            item, created=CartItem.objects.get_or_create(
                cart=cart, product_id=product_id, defaults={'quantity': quantity}
            )
            if not created:
                if item.quantity + quantity > 100:
                    raise serializers.ValidationError({"quantity": "A cart line cannot exceed 100 items."})
                CartItem.objects.filter(pk=item.pk).update(quantity=F('quantity') + quantity)
                item.refresh_from_db()
            self.instance=item
        return self.instance
    
    class Meta:
        model=CartItem
        fields=['id','product_id','quantity']

class UpdateCartItemSerializer(serializers.ModelSerializer):
    quantity=serializers.IntegerField(min_value=1, max_value=100)

    class Meta:
        model=CartItem
        fields=['quantity']

class CustomerSerializer(serializers.ModelSerializer):
    user_id=serializers.IntegerField(read_only=True)
    
    class Meta:
        model=Customer
        fields=['id','user_id','phone','birth_date','membership']
        read_only_fields=['membership']

class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model=Address
        fields=['street','city','zip']

class OrderItemSerializer(serializers.ModelSerializer):
    product=SimpleProductSerializer()
    
    class Meta:
        model = OrderItem
        fields = ['id','product','unit_price','quantity']

class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True)

    class Meta:
        model = Order
        fields = ['id','customer','placed_at','payment_status','items']

class UpdateOrderSerializer(serializers.ModelSerializer):
    class Meta: 
        model = Order
        fields=['payment_status']

class CreateOrderSerializer(serializers.Serializer):
    cart_id = serializers.UUIDField()

    def validate_cart_id(self, cart_id):
        if not Cart.objects.filter(pk=cart_id, owner_id=self.context['user_id']).exists():
            raise serializers.ValidationError('No cart with the given ID was found.')
        if not CartItem.objects.filter(cart_id=cart_id).exists():
            raise serializers.ValidationError('The cart is empty')
        return cart_id
    
    def save(self, **kwargs):
        with transaction.atomic():
            cart_id = self.validated_data['cart_id']
            customer=Customer.objects.get(user_id=self.context['user_id'])
            cart=get_object_or_404(Cart.objects.select_for_update(), pk=cart_id, owner_id=self.context['user_id'])
            cart_items=list(CartItem.objects.select_for_update().select_related('product').filter(cart=cart).order_by('product_id'))
            if not cart_items:
                raise serializers.ValidationError({'cart_id': 'The cart is empty.'})
            order = Order.objects.create(customer=customer)
            order_items = [
                OrderItem(
                    order=order,
                    product=item.product,
                    unit_price=item.product.unit_price,
                    quantity=item.quantity
                ) for item in cart_items
            ]
            for item in cart_items:
                changed=Product.objects.filter(pk=item.product_id, inventory__gte=item.quantity).update(
                    inventory=F('inventory') - item.quantity
                )
                if not changed:
                    raise serializers.ValidationError({
                        'inventory': f'Not enough stock for "{item.product.title}".'
                    })
            OrderItem.objects.bulk_create(order_items)
            cart.delete()

            order_created.send_robust(self.__class__, order=order)

            return order
