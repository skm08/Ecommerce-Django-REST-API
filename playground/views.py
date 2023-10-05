from django.shortcuts import render
from django.http import HttpResponse
from store.models import Product,OrderItem,Order
from django.db.models import Q

def HomePage(request):
    queryset=Order.objects.select_related('customer').prefetch_related('orderitem_set__product').order_by('-placed_at')[:5]

    return render(request,'index.html',{'name':'index.html','orders':queryset})
