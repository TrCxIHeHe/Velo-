"""Pricing: strategy (algorithm) / configuration (data) / ride lifecycle (orchestration).

* ``strategy.py``   — the :class:`PricingStrategy` interface and value objects.
* ``fixed_pair.py`` — first strategy: a configured fixed fare per directed dock pair.
* ``service.py``    — :class:`PricingService`, the only thing the ride lifecycle talks to.
* ``repository.py`` — storage of the dock-pair tariff table.
* ``router.py``     — admin CRUD for the tariff table.

Adding a strategy (distance, time, subscription, promo, surge...): see
``docs/pricing-and-ride-lifecycle.md`` — implement ``PricingStrategy``, register
it in ``PricingService.STRATEGIES`` and select it with ``PRICING_STRATEGY``.
Ride completion does not change.
"""
