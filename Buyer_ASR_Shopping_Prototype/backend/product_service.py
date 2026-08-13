"""
product_service.py
-------------------
Loads the product catalog from data/products.json and provides lookup /
search helpers. This is the ONLY module that reads products.json - every
other module asks this service for product data rather than touching the
file directly.
"""

import json
import os
from typing import List, Dict, Optional

DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "products.json")


class ProductService:
    def __init__(self, data_path: str = DATA_PATH):
        self._data_path = data_path
        self._products: List[Dict] = []
        self._by_id: Dict[str, Dict] = {}
        self._by_name: Dict[str, Dict] = {}  # lowercase name -> product
        self.reload()

    def reload(self) -> None:
        """(Re)loads the catalog from disk. Useful if products.json is edited."""
        with open(self._data_path, "r", encoding="utf-8") as f:
            self._products = json.load(f)
        self._by_id = {p["id"]: p for p in self._products}
        self._by_name = {p["name"].lower(): p for p in self._products}

    def get_all(self) -> List[Dict]:
        return list(self._products)

    def get_by_id(self, product_id: str) -> Optional[Dict]:
        return self._by_id.get(product_id)

    def get_by_name(self, name: str) -> Optional[Dict]:
        """Exact (case-insensitive) name lookup."""
        return self._by_name.get(name.strip().lower())

    def all_names_lower(self) -> List[str]:
        return list(self._by_name.keys())

    def search(self, query: str) -> List[Dict]:
        """Case-insensitive substring search across product name and category."""
        q = (query or "").strip().lower()
        if not q:
            return self.get_all()
        return [
            p for p in self._products
            if q in p["name"].lower() or q in p["category"].lower()
        ]

    def by_category(self, category: str) -> List[Dict]:
        if not category or category.lower() == "all":
            return self.get_all()
        return [p for p in self._products if p["category"].lower() == category.lower()]

    def categories(self) -> List[str]:
        seen = []
        for p in self._products:
            if p["category"] not in seen:
                seen.append(p["category"])
        return seen
