"""Minimal RevenueCat REST API client.

Stubbed deliberately — no RevenueCat project is connected yet, so this
returns None rather than guessing at a response shape. Replace the body of
fetch_revenuecat_totals with a real call once there's a project to test
against: https://www.revenuecat.com/docs/api-v1

Expected return: (period_start: date, period_end: date, gross_amount: float)
for the most recently closed reporting period, or (None, None, None) if the
call fails.
"""


def fetch_revenuecat_totals(project_key):
    # TODO: call RevenueCat's REST API using project_key, parse the period
    # totals, and return them. Left unimplemented until a real project
    # exists to build and test this against.
    return None, None, None
