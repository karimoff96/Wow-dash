import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'WowDash.settings')
django.setup()

from services.models import Product
from django.template import Template, Context

# Get product 187
p = Product.objects.get(id=187)

print("="*50)
print("Product Data from Database:")
print("="*50)
print(f"ID: {p.id}")
print(f"Name: {p.name}")
print(f"ordinary_first_page_price: {p.ordinary_first_page_price}")
print(f"ordinary_other_page_price: {p.ordinary_other_page_price}")
print(f"agency_first_page_price: {p.agency_first_page_price}")
print(f"agency_other_page_price: {p.agency_other_page_price}")
print(f"user_copy_price_percentage: {p.user_copy_price_percentage}")
print(f"agency_copy_price_percentage: {p.agency_copy_price_percentage}")

print("\n" + "="*50)
print("Template Rendering Tests:")
print("="*50)

# Test 1: Without filter
template1 = Template('{{ product.ordinary_first_page_price }}')
context = Context({'product': p})
result1 = template1.render(context)
print(f"Without filter: '{result1}'")

# Test 2: With default filter
template2 = Template('{{ product.ordinary_first_page_price|default:0 }}')
result2 = template2.render(context)
print(f"With |default:0: '{result2}'")

# Test 3: With default_if_none
template3 = Template('{{ product.ordinary_first_page_price|default_if_none:0 }}')
result3 = template3.render(context)
print(f"With |default_if_none:0: '{result3}'")

# Test 4: Direct HTML input simulation
template4 = Template('<input value="{{ product.ordinary_first_page_price|default:0 }}">')
result4 = template4.render(context)
print(f"In input field: {result4}")

print("\n" + "="*50)
print("Type Information:")
print("="*50)
print(f"Type: {type(p.ordinary_first_page_price)}")
print(f"Is None: {p.ordinary_first_page_price is None}")
print(f"Boolean value: {bool(p.ordinary_first_page_price)}")
