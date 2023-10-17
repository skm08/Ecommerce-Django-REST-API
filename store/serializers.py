from rest_framework import serializers
from decimal import Decimal
from store.models import Product, Collection

class CollectionSerializer(serializers.ModelSerializer):
    class Meta:
        model=Collection
        fields=['id','title']

class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model=Product
        fields=['id','title','unit_price','price_with_tax','collection']

    price_with_tax=serializers.SerializerMethodField(
        method_name='calculate_tax'
    )

    def calculate_tax(sel,product: Product):
        return product.unit_price * Decimal(1.1)
    
    # collection=serializers.HyperlinkedRelatedField(
    #     queryset=Collection.objects.all(),
    #     view_name='collection-detail'
    # )      