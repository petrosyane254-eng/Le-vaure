from django.core.management.base import BaseCommand
from django.utils.text import slugify
from shop.models import Category,Product
class Command(BaseCommand):
    def handle(self,*args,**kwargs):
        rows=[
          ("Hoodies","LE VAURÉ Hoodie","Premium heavyweight black hoodie with signature LE VAURÉ branding","69.99"),
          ("T-Shirts","LE VAURÉ T-Shirt","Minimal black cotton T-shirt","39.99"),
          ("Caps","LE VAURÉ Cap","Structured premium black cap","29.99"),
          ("Accessories","LE VAURÉ Phone Case","Slim matte black phone case","19.99"),
        ]
        for cat,name,desc,price in rows:
            c,_=Category.objects.get_or_create(slug=slugify(cat),defaults={"name":cat})
            Product.objects.get_or_create(slug=slugify(name),defaults={"name":name,"category":c,"description":desc,"price":price,"stock":25})
        self.stdout.write(self.style.SUCCESS("Starter products created."))
