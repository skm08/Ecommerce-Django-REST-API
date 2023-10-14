from django.shortcuts import render
from django.contrib.contenttypes.models import ContentType
from store.models import *
from tags.models import TaggedItem
from django.db import transaction, connection


def HomePage(request):
    with connection.cursor() as cursor:
        cursor.execute()

    return render(request,'index.html',
                  {'name':'index.html'})
