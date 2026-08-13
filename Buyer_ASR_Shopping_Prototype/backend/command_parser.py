"""
command_parser.py
------------------
Turns transcribed shopping speech ("Add two apples and one litre of milk")
into structured [{product, quantity}] items, matched against the real
product catalog.

Deliberately simple and deterministic - no LLM. This mirrors the
architecture requested: ASR handles speech -> text, this module handles
text -> shopping intent, and product_service supplies the ground truth
for what "apple" or "milk" actually resolves to.
"""

import re
from typing import List, Dict, Optional
from product_service import ProductService

NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "a": 1, "an": 1, "single": 1, "couple": 2, "few": 3,
}

# Words that appear between a quantity and a product but carry no product
# meaning themselves (units, connectors, filler). Skipping these lets
# "one litre of milk" and "two bottles of water" resolve correctly.
NOISE_WORDS = {
    "litre", "litres", "liter", "liters", "l",
    "kilo", "kilos", "kg", "kgs", "gram", "grams", "g",
    "bottle", "bottles", "packet", "packets", "bunch", "bunches",
    "dozen", "piece", "pieces", "pc", "pcs",
    "of", "and", "add", "please", "some", "the", "me",
    "to", "cart", "want", "need", "get", "buy", "order",
    "also", "more", "with", "&",
}

# Explicit plural -> singular overrides for irregular/ambiguous cases.
PLURAL_OVERRIDES = {
    "tomatoes": "tomato",
    "potatoes": "potato",
    "onions": "onion",
    "carrots": "carrot",
    "cabbages": "cabbage",
    "beans": "beans",       # already catalog name, don't singularize away
    "brinjals": "brinjal",
    "cucumbers": "cucumber",
    "apples": "apple",
    "bananas": "banana",
    "oranges": "orange",
    "mangoes": "mango",
    "mangos": "mango",
    "grapes": "grapes",     # catalog name is already plural
    "watermelons": "watermelon",
    "leaves": "leaves",
}


def _singularize(word: str) -> str:
    """Best-effort singular form for simple English plurals."""
    if word in PLURAL_OVERRIDES:
        return PLURAL_OVERRIDES[word]
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"
    if word.endswith("es") and len(word) > 4:
        return word[:-2]
    if word.endswith("s") and not word.endswith("ss") and len(word) > 3:
        return word[:-1]
    return word


def _tokenize(text: str) -> List[str]:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s]", " ", text)  # drop punctuation
    return [t for t in text.split() if t]


class CommandParser:
    """
    Parses free-text shopping commands into catalog-matched items.
    Multi-word product names (e.g. "wheat flour", "curry leaves",
    "cooking oil") are matched greedily against the longest known phrase
    before falling back to single-word matching.
    """

    def __init__(self, product_service: ProductService):
        self.products = product_service
        # Build a lookup of every catalog product name as a tuple of
        # lowercase tokens, sorted longest-first so multi-word names win.
        self._name_token_map = []
        for p in self.products.get_all():
            tokens = tuple(_tokenize(p["name"]))
            self._name_token_map.append((tokens, p))
        self._name_token_map.sort(key=lambda x: -len(x[0]))

    def parse(self, text: str) -> Dict:
        """
        Returns:
            {
              "items": [{"product_id":..., "product_name":..., "quantity": N}, ...],
              "unmatched_terms": ["xyz", ...]   # words that looked like products but didn't match
            }
        """
        tokens = _tokenize(text)
        items: Dict[str, Dict] = {}   # product_id -> {product, quantity}
        unmatched_terms: List[str] = []

        i = 0
        pending_qty: Optional[int] = None

        while i < len(tokens):
            token = tokens[i]

            # 1) Numeric quantity, e.g. "2"
            if token.isdigit():
                pending_qty = int(token)
                i += 1
                continue

            # 2) Number word, e.g. "two"
            if token in NUMBER_WORDS:
                pending_qty = NUMBER_WORDS[token]
                i += 1
                continue

            # 3) Try multi-word product match starting at position i
            matched_product, consumed = self._match_product_at(tokens, i)
            if matched_product:
                qty = pending_qty or 1
                pid = matched_product["id"]
                if pid in items:
                    items[pid]["quantity"] += qty
                else:
                    items[pid] = {
                        "product_id": pid,
                        "product_name": matched_product["name"],
                        "quantity": qty,
                    }
                pending_qty = None
                i += consumed
                continue

            # 4) Noise / filler word - skip without resetting pending_qty,
            #    so "one litre of milk" still applies qty=1 to milk.
            if token in NOISE_WORDS:
                i += 1
                continue

            # 5) Unknown word - if we were holding a quantity expecting a
            #    product, this might be a product we don't stock. Record it.
            if pending_qty is not None:
                unmatched_terms.append(token)
                pending_qty = None
            i += 1

        return {
            "items": list(items.values()),
            "unmatched_terms": unmatched_terms,
        }

    def _match_product_at(self, tokens: List[str], start: int):
        """
        Tries to match a catalog product name beginning at tokens[start],
        checking multi-word names first (self._name_token_map is sorted
        longest-first). Handles simple plural forms via _singularize.
        Returns (product_dict_or_None, num_tokens_consumed).
        """
        remaining = tokens[start:]
        singular_remaining = [_singularize(t) for t in remaining]

        for name_tokens, product in self._name_token_map:
            n = len(name_tokens)
            if n == 0 or n > len(remaining):
                continue
            window = tuple(singular_remaining[:n])
            if window == name_tokens:
                return product, n
        return None, 0
