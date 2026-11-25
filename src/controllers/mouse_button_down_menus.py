"""Compat re-export: menu click domains live in menu_* modules."""
from controllers.menu_pre_dispatch import _handle_pre_menu  # noqa: F401
from controllers.menu_clicks import _handle_menus  # noqa: F401
