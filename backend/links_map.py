"""Logical navigation keys shared by the API and the Matrixify import.

The storefront never hardcodes a slug: it asks for a key and /api/links answers with the path that
exists right now. Resolution order is (1) the doc carrying link_key — so renaming a page or a
collection in the admin keeps every link working — then (2) the known handles below.
"""

# key -> (kind, candidate handles/slugs in priority order)
LINK_TARGETS = {
    "catalog": ("collection", ["2all-the-peptides-1", "all-peptides"]),
    "retatrutide": ("collection", ["retatrutide-price"]),
    "terms": ("page", ["terms-conditions", "terms-of-service", "general-terms"]),
    "privacy": ("page", ["privacy-policy", "data-sharing-opt-out"]),
    "cookies": ("page", ["cookies", "cookie-policy"]),
    "refund": ("page", ["refund-policy", "returns-policy"]),
    "shipping": ("page", ["delivery-and-payment", "shipping-policy"]),
    "faq": ("page", ["faq"]),
    "contacts": ("page", ["contact-1", "contacts", "contact"]),
    "about": ("page", ["about-1", "about"]),
    "whatArePeptides": ("page", ["какво-са-пептиди", "what-are-peptides"]),
    "chemicalAnalysis": ("page", ["chemical-analysis"]),
    "scientificLiterature": ("page", ["scientific-literature"]),
    "partners": ("page", ["become-a-distributor", "partners"]),
}


def link_key_for(kind: str, handle: str):
    """The logical key a page/collection handle belongs to (used when importing or seeding)."""
    for key, (target_kind, candidates) in LINK_TARGETS.items():
        if target_kind == kind and handle in candidates:
            return key
    return None
