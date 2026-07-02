import frappe

from portal_theme import css_builder


def execute():
	"""One-time cleanup after the theming-engine rebuild (idempotent):
	- enforce exactly one active Portal Theme (keep the most recently modified)
	- seed an "Initial" revision per existing theme so pre-rebuild CSS is restorable
	- clear the merged-CSS cache
	"""
	active = frappe.get_all(
		"Portal Theme", filters={"is_active": 1}, order_by="modified desc", pluck="name"
	)
	for name in active[1:]:
		frappe.db.set_value("Portal Theme", name, "is_active", 0)

	for theme in frappe.get_all("Portal Theme", fields=["name", "css_content"]):
		if not (theme.css_content or "").strip():
			continue
		if frappe.db.exists(
			"Portal Theme CSS Revision", {"portal_theme": theme.name, "trigger": "Initial"}
		):
			continue
		frappe.get_doc(
			{
				"doctype": "Portal Theme CSS Revision",
				"portal_theme": theme.name,
				"trigger": "Initial",
				"css_content": theme.css_content,
				"note": "Seeded by normalize_theme_state (pre-rebuild CSS)",
			}
		).insert(ignore_permissions=True)

	css_builder.clear_theme_cache()
