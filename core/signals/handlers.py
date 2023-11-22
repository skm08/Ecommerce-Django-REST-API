from django.dispatch import receiver
from store.signals import order_created

@receiver(order_created)
def on_delete_created(sender, **kwargs):
    print(kwargs['order'])