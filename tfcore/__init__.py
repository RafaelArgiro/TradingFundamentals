"""Shared calculation logic for the TradingFundamentals apps.

Nothing in this package may import Streamlit. Keeping the core UI-free is what
makes it testable from plain pytest, reusable across apps, and safe to call
from a notebook.
"""
