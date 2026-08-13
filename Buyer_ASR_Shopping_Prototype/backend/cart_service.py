"""
cart_service.py
----------------
A simple in-memory cart for the prototype. Single shared cart (no user
accounts/sessions in this demo) - matches the brief's API design, which
has no session identifier on the cart endpoints.

Quantities for the same product accumulate rather than creating duplicate
rows: adding "two apples" then "three apples" results in Apple x 5.
"""

from typing import Dict, List, Optional


class CartService:
    def __init__(self, product_service):
        self.products = product_service
        self._items: Dict[str, int] = {}  # product_id -> quantity

    def add_item(self, product_id: str, quantity: int = 1) -> Dict:
        if quantity <= 0:
            raise ValueError("Quantity must be a positive number.")
        product = self.products.get_by_id(product_id)
        if not product:
            raise KeyError(f"Product '{product_id}' was not found in the catalog.")
        if not product.get("available", True):
            raise ValueError(f"'{product['name']}' is currently unavailable.")

        self._items[product_id] = self._items.get(product_id, 0) + quantity
        return self.get_cart()

    def update_quantity(self, product_id: str, quantity: int) -> Dict:
        """Sets the ABSOLUTE quantity for a product. quantity<=0 removes it."""
        product = self.products.get_by_id(product_id)
        if not product:
            raise KeyError(f"Product '{product_id}' was not found in the catalog.")

        if quantity <= 0:
            self._items.pop(product_id, None)
        else:
            self._items[product_id] = quantity
        return self.get_cart()

    def remove_item(self, product_id: str) -> Dict:
        self._items.pop(product_id, None)
        return self.get_cart()

    def clear(self) -> Dict:
        self._items.clear()
        return self.get_cart()

    def get_cart(self) -> Dict:
        line_items: List[Dict] = []
        subtotal = 0.0

        for product_id, qty in self._items.items():
            product = self.products.get_by_id(product_id)
            if not product:
                continue  # catalog changed under us - skip gracefully
            line_total = round(product["price"] * qty, 2)
            subtotal += line_total
            line_items.append({
                "product_id": product_id,
                "name": product["name"],
                "unit": product["unit"],
                "price": product["price"],
                "quantity": qty,
                "line_total": line_total,
            })

        subtotal = round(subtotal, 2)
        return {
            "items": line_items,
            "count": sum(self._items.values()),
            "subtotal": subtotal,
            "total": subtotal,  # no taxes/shipping in this prototype
        }
