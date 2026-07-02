import hashlib

import frappe

from portal_theme import css_builder


@frappe.whitelist()
def get_theme_bundle():
	"""Merged Desk/portal stylesheet: Portal Theme Setting chrome CSS + the active
	Portal Theme's css_content. Redis-cached; invalidated on save of any theming
	doctype. Never raises — a broken build returns empty CSS and an Error Log
	entry instead of breaking every page load."""
	cached = frappe.cache().get_value(css_builder.CACHE_KEY)
	if cached is not None:
		return {"css": cached["css"], "hash": cached["hash"], "cached": True}

	try:
		css = css_builder.merge_theme_css()
	except Exception:
		frappe.log_error(title="Portal Theme: bundle build failed")
		return {"css": "", "hash": "", "cached": False}

	payload = {
		"css": css,
		"hash": hashlib.sha1(css.encode("utf-8")).hexdigest()[:10] if css else "",
	}
	frappe.cache().set_value(css_builder.CACHE_KEY, payload, expires_in_sec=86400)
	return {"css": payload["css"], "hash": payload["hash"], "cached": False}


@frappe.whitelist()
def get_active_theme_css():
	"""Deprecated: kept one release so browsers holding the old cached loader JS
	keep working across the deploy window. Use get_theme_bundle instead."""
	return {"css": get_theme_bundle()["css"]}
