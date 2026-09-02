"""PRODUCT-03 — the one-screen judge dashboard.

This package is a presentation layer only. It performs no governance work
of its own: every field the dashboard shows is read off the real Product-01
result (scripts/judge_demo.py::ScenarioResult) and the shared Product-02
presentation model (product/judge_presentation.py, product/judge_views.py).
See demo/web.py's module docstring for the execution boundary this enforces.
"""
