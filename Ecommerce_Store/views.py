from django.shortcuts import render
from django.http import HttpResponse

def home(request):
    return HttpResponse('Showcase Store API is running. Explore /api/docs/ for the API reference.')
