from typing import Any
from django.contrib import admin, messages
from django.db.models.query import QuerySet
from django.http.request import HttpRequest

from tags.models import TaggedItem
from .import models
from django.db.models.aggregates import Count
from django.utils.html import format_html, urlencode
from django.urls import reverse
from django.contrib.contenttypes.admin import GenericTabularInline


class InventoryFilter(admin.SimpleListFilter):
    title='inventory'
    parameter_name='inventory'
    def lookups(self,request,model_admin):
        return [
            ('<10','Low')
        ]
    def queryset(self,request,queryset:QuerySet):
        if self.value() == '<10':
            return queryset.filter(inventory__lt=10)



@admin.register(models.Product)
class ProductAdmin(admin.ModelAdmin):
    prepopulated_fields= {
        'slug': ['title']
    }
    autocomplete_fields=['collection']
    actions=['clear_inventory']
    list_display=['title','unit_price','inventory_status','collection_status']
    list_editable=['unit_price']
    list_per_page=10
    list_filter=['collection','last_update',InventoryFilter]
    list_select_related = ['collection']
    search_fields = ['title']

    @admin.display(ordering='inventory')
    def inventory_status(self,product):
        if product.inventory < 10:
            return 'Low'
        else: 
            return 'Okay'
        
    @admin.display(ordering='collection')
    def collection_status(self,product):
        return product.collection.title

    @admin.action(description='clear inventory')
    def clear_inventory(self,request,queryset):
        updated_count=queryset.update(inventory=0)
        self.message_user(
            request,
            f'{updated_count} products were updated',
            messages.ERROR
        )

@admin.register(models.Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display=['first_name','last_name','membership','orders']
    list_editable=['membership']
    list_select_related=['user']
    ordering=['user__first_name','user__last_name']
    search_fields=['first_name__istartwith','last_name__istartwith']
    list_per_page=10

    @admin.display(ordering='orders')
    def orders(self,customer):
        url=(
            reverse('admin:store_order_changelist')
            + '?'
            + urlencode({
                'customer__id': str(customer.id)
            })
        )
        return format_html('<a href="{}">{} Orders<a/>',
                           url,
                           customer.orders)
    
    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            orders=Count('order')
        )


class OrderItemsInline(admin.TabularInline):
    model=models.OrderItem
    autocomplete_fields=['product']
    extra=2

@admin.register(models.Order)
class OrderAdmin(admin.ModelAdmin):
    list_display=['id','placed_at','customer']
    autocomplete_fields=['customer']
    inlines=[OrderItemsInline]


@admin.register(models.Collection)
class CollectionAdmin(admin.ModelAdmin):
    list_display=['title','products_count']
    search_fields=['title']

    @admin.display(ordering='products_count')
    def products_count(self,collection):
        url=(
            reverse('admin:store_product_changelist')
            + '?'
            + urlencode({
                'collection__id': str(collection.id)
            })
        )
        return format_html('<a href="{}">{}<a/>',
                           url,
                           collection.products_count)
    
    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            products_count=Count('products')
        )