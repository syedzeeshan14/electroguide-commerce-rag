"""Small, transparent query parser and deterministic catalog grounding."""
import re
from app.catalog import ALIASES
from scripts.generate_catalog import CATEGORIES

def constraints(question):
    tokens = re.findall(r'[a-z0-9]+',question.lower())
    normalized = [ALIASES.get(token,token) for token in tokens]
    category = next((token for token in normalized if token in CATEGORIES), None)
    match = re.search(r'(?:under|below|less than|up to|budget(?: of)?|maximum|max)\s*\$?\s*([\d,]+(?:\.\d{1,2})?)', question.lower())
    budget = float(match.group(1).replace(',','')) if match else None
    return category, budget

def retrieve(catalog, question):
    category,budget = constraints(question)
    if category:
        return catalog.search(category=category,max_price=budget,limit=5)
    # Policy questions do not silently return arbitrary products.
    return []

def subtotal(cart):
    return round(sum(item['price']*item['quantity'] for item in cart.values()),2)
