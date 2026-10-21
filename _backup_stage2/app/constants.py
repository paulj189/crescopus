"""Countries offered in signup/settings country pickers.

Not exhaustive — Stripe Connect supports more than this — but covers the
common markets. Extend as needed; codes are ISO 3166-1 alpha-2, matching
what Stripe's Accounts v2 API expects for identity.country.
"""

COUNTRIES = [
    ("GB", "United Kingdom"),
    ("US", "United States"),
    ("CA", "Canada"),
    ("AU", "Australia"),
    ("NZ", "New Zealand"),
    ("IE", "Ireland"),
    ("DE", "Germany"),
    ("FR", "France"),
    ("ES", "Spain"),
    ("IT", "Italy"),
    ("NL", "Netherlands"),
    ("BE", "Belgium"),
    ("AT", "Austria"),
    ("PT", "Portugal"),
    ("LU", "Luxembourg"),
    ("FI", "Finland"),
    ("SE", "Sweden"),
    ("DK", "Denmark"),
    ("NO", "Norway"),
    ("PL", "Poland"),
    ("CH", "Switzerland"),
    ("SG", "Singapore"),
    ("HK", "Hong Kong"),
    ("JP", "Japan"),
]
