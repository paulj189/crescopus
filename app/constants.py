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


# ---------- Needs / Offers tags: BACKUP COPY ----------
# The live lists are in the tag_options table in Supabase (see app/tags.py and
# sql/migration_tag_options.sql) — edit them there. These are only used if
# that table can't be read.
# Two vocabularies that mirror each other:
#   GROWTH_TAGS  — growth help: what builders NEED and growers OFFER
#   SUPPORT_TAGS — support/terms: what builders OFFER and growers NEED
# Stored as the slug (left); shown as the label (right).

GROWTH_TAGS = [
    ("app_store_growth", "App Store growth"),
    ("social", "Social"),
    ("paid_ads", "Paid ads"),
    ("influencers", "Influencers"),
    ("partnerships", "Partnerships"),
    ("content", "Content"),
    ("seo", "SEO"),
]

SUPPORT_TAGS = [
    ("revenue_share", "Revenue share"),
    ("equity", "Equity"),
    ("roadmap_input", "Roadmap input"),
    ("analytics_access", "Analytics access"),
    ("product_access", "Product access"),
    ("ad_budget", "Ad budget"),
    ("creative_assets", "Creative assets"),
]

TAG_LABELS = dict(GROWTH_TAGS + SUPPORT_TAGS)

# Which vocabulary each side's Needs / Offers use.
BUILDER_NEEDS_TAGS, BUILDER_OFFERS_TAGS = GROWTH_TAGS, SUPPORT_TAGS
GROWER_NEEDS_TAGS, GROWER_OFFERS_TAGS = SUPPORT_TAGS, GROWTH_TAGS

VERIFICATION_LABELS = {
    "id": "ID verified",
    "email": "Email verified",
    "phone": "Phone verified",
    "github": "GitHub linked",
    "linkedin": "LinkedIn linked",
    "app_ownership": "App ownership verified",
}


# ---------- Ledger currencies ----------
# The currencies the European Central Bank publishes daily rates for (used to
# suggest exchange rates), as (code, symbol, name). Add more here if needed.
CURRENCIES = [
    ("GBP", "£", "British pound"),
    ("EUR", "€", "Euro"),
    ("USD", "$", "US dollar"),
    ("CAD", "CA$", "Canadian dollar"),
    ("AUD", "A$", "Australian dollar"),
    ("NZD", "NZ$", "New Zealand dollar"),
    ("CHF", "CHF ", "Swiss franc"),
    ("SEK", "SEK ", "Swedish krona"),
    ("NOK", "NOK ", "Norwegian krone"),
    ("DKK", "DKK ", "Danish krone"),
    ("PLN", "PLN ", "Polish złoty"),
    ("CZK", "CZK ", "Czech koruna"),
    ("JPY", "¥", "Japanese yen"),
    ("SGD", "S$", "Singapore dollar"),
    ("HKD", "HK$", "Hong Kong dollar"),
    ("INR", "₹", "Indian rupee"),
    ("ZAR", "R ", "South African rand"),
    ("BRL", "R$", "Brazilian real"),
    ("MXN", "MX$", "Mexican peso"),
]
CURRENCY_SYMBOLS = {code: symbol for code, symbol, _ in CURRENCIES}
