# Copyright (c) 2026, Starlink Gulf Trading Ltd
# CSS assembly for Portal Theme. Pure functions: no writes except cache clearing.

import re

import frappe

CACHE_KEY = "portal_theme:merged_css"

GENERATED_BEGIN = "/* == PT:GENERATED:BEGIN == */"
GENERATED_END = "/* == PT:GENERATED:END == */"
CUSTOM_BEGIN = "/* == PT:CUSTOM:BEGIN == manual CSS below is preserved across Regenerate == */"

DEFAULT_CUSTOM_TAIL = CUSTOM_BEGIN + "\n\n/* Add your custom CSS below. It survives Regenerate. */\n"


def clear_theme_cache():
	frappe.cache().delete_value(CACHE_KEY)


def slugify(value: str) -> str:
	if not value:
		return ""
	value = value.strip().lower()
	value = re.sub(r"\s+", "-", value)
	value = re.sub(r"[^a-z0-9\-]", "", value)
	value = re.sub(r"-+", "-", value)
	return value.strip("-")


def build_token_blocks(theme) -> str:
	""":root light block + :root[data-theme="dark"] block from the theme_variables table."""
	light_lines = []
	dark_lines = []

	for row in theme.get("theme_variables") or []:
		name = slugify((row.variable_name or "").strip())
		if not name:
			continue
		light_val = row.light_value or ""
		dark_val = row.dark_value or light_val
		light_text = row.light_text or "#000000"
		dark_text = row.dark_text or "#ffffff"

		light_lines.append(f"  --{name}: {light_val};")
		light_lines.append(f"  --{name}-text-color: {light_text};")
		dark_lines.append(f"  --{name}: {dark_val};")
		dark_lines.append(f"  --{name}-text-color: {dark_text};")

	border_lines = [
		f"  --border-radius: {theme.border_radius or 6}px;",
		f"  --border-color: {theme.border_color or '#e0e0e0'};",
		"  --border-width: 1px;",
	]

	root_block = ":root {\n" + "\n".join(light_lines + border_lines) + "\n}\n"
	dark_block = ""
	if dark_lines:
		dark_block = '\n:root[data-theme="dark"] {\n' + "\n".join(dark_lines) + "\n}\n"

	return root_block + dark_block


def get_template_css(theme) -> str:
	"""Raw CSS of the linked Theme Template. Problems become CSS comments, never rule text."""
	if not theme.theme_template:
		return "/* no Theme Template linked */"
	if not frappe.db.exists("Theme Template", theme.theme_template):
		return f"/* Theme Template {theme.theme_template!r} not found */"
	return (
		frappe.db.get_value("Theme Template", theme.theme_template, "theme_template")
		or f"/* Theme Template {theme.theme_template!r} is empty */"
	)


def build_generated_css(theme) -> str:
	"""The full generated (sentinel-wrapped) section: tokens -> template -> component rows."""
	parts = [
		GENERATED_BEGIN,
		f"/* theme: {theme.theme_name or theme.name} — rebuilt by the Regenerate CSS button; edits in this section are overwritten */",
		"",
		"/* -- design tokens -- */",
		build_token_blocks(theme),
		f"/* -- components (Theme Template: {theme.theme_template or 'none'}) -- */",
		get_template_css(theme),
	]

	component_css = build_component_css(theme)
	if component_css:
		parts += ["", "/* -- component styles (Component Style rows) -- */", component_css]

	parts.append(GENERATED_END)
	return "\n".join(parts)


def build_component_css(theme) -> str:
	"""Entity-based styling rows. Populated by the component registry (added in the
	entity-styling commit); safe no-op until the child table exists."""
	return ""


def validate_component_styles(theme):
	"""Row validation for the entity-styling layer; no-op until the child table exists."""
	return


def split_custom_tail(css_content: str) -> str:
	"""Return the custom tail of an existing css_content.

	- Sentinel present: everything after GENERATED_END (existing CUSTOM marker kept).
	- No sentinel: the ENTIRE content is treated as custom tail — nothing is discarded.
	- Empty: a fresh default tail.
	"""
	content = css_content or ""
	if GENERATED_END in content:
		tail = content.split(GENERATED_END, 1)[1].lstrip("\n")
		if not tail.strip():
			return DEFAULT_CUSTOM_TAIL
		if CUSTOM_BEGIN.split("==")[1].strip() not in tail.split("\n", 1)[0]:
			# tail lost its marker; re-add so future splits stay stable
			return CUSTOM_BEGIN + "\n" + tail
		return tail
	if content.strip():
		return CUSTOM_BEGIN + "\n\n/* preserved pre-existing CSS (no sentinel found) */\n" + content
	return DEFAULT_CUSTOM_TAIL


def regenerate_css_content(theme) -> str:
	"""Fresh generated section + preserved custom tail."""
	return build_generated_css(theme) + "\n\n" + split_custom_tail(theme.css_content)


def initial_css_content(theme) -> str:
	"""First-save content for a new theme."""
	return build_generated_css(theme) + "\n\n" + DEFAULT_CUSTOM_TAIL


# ---------------------------------------------------------
# SETTINGS CSS (server-side port of the old client builder)
# ---------------------------------------------------------


def build_settings_css(settings) -> str:
	"""Desk chrome CSS from Portal Theme Setting. Emits ONLY set fields — the old
	client builder emitted `inherit !important` for every empty field, breaking
	Desk defaults. Variables are prefixed --pt- to avoid colliding with Frappe
	core variables and theme tokens."""
	if not settings.enable:
		return ""

	css_vars = {}
	rules = []

	def var(name, value):
		if value:
			css_vars[name] = value
		return bool(value)

	# page ground
	if var("--pt-portal-bg", settings.portal_background_color):
		rules.append(
			"html, body, .content.page-container {\n"
			"  background-color: var(--pt-portal-bg) !important;\n}"
		)

	# navbar — text via allowlist so dropdown menus and the awesomebar results
	# (which live inside .navbar but render on light menus) are never matched
	if var("--pt-navbar-bg", settings.navbar_color):
		rules.append(".navbar {\n  background-color: var(--pt-navbar-bg) !important;\n}")
	if var("--pt-navbar-text", settings.navbar_text_color):
		rules.append(
			".navbar .navbar-brand,\n"
			".navbar .navbar-nav > li > .nav-link,\n"
			".navbar #navbar-breadcrumbs li a {\n"
			"  color: var(--pt-navbar-text) !important;\n}"
		)

	# primary button
	if var("--pt-btn-primary-bg", settings.primary_button_background):
		rules.append(
			".btn.btn-primary {\n  background-color: var(--pt-btn-primary-bg) !important;\n}"
		)
		rules.append(
			".form-control:focus {\n"
			"  box-shadow: 0 0 0 1px var(--pt-btn-primary-bg) !important;\n}"
		)
	if var("--pt-btn-primary-text", settings.primary_button_text):
		rules.append(".btn.btn-primary {\n  color: var(--pt-btn-primary-text) !important;\n}")
	if var("--pt-btn-primary-hover-bg", settings.primary_button_hover_background):
		rules.append(
			".btn.btn-primary:hover {\n"
			"  background-color: var(--pt-btn-primary-hover-bg) !important;\n}"
		)

	# secondary button
	if var("--pt-btn-secondary-bg", settings.secondary_button_background):
		rules.append(
			".btn.btn-secondary {\n  background-color: var(--pt-btn-secondary-bg) !important;\n}"
		)
	if var("--pt-btn-secondary-text", settings.secondary_button_text):
		rules.append(".btn.btn-secondary {\n  color: var(--pt-btn-secondary-text) !important;\n}")

	# cards / widgets
	if var("--pt-card-bg", settings.card_background_color):
		rules.append(
			".card, .widget.card-box {\n  background-color: var(--pt-card-bg) !important;\n}"
		)
	if var("--pt-card-text", settings.card_text_color):
		rules.append(
			".card, .card p, .card span, .card li,\n"
			".widget.card-box,\n"
			".widget.links-widget-box .link-item {\n"
			"  color: var(--pt-card-text) !important;\n}"
		)
	if var("--pt-card-header-bg", settings.card_header_color):
		rules.append(
			".card .card-header, .card-header {\n"
			"  background-color: var(--pt-card-header-bg) !important;\n}"
		)
	if var("--pt-card-header-text", settings.card_header_text_color):
		rules.append(
			".card .card-header, .card-header {\n"
			"  color: var(--pt-card-header-text) !important;\n}"
		)

	# form controls
	if var("--pt-form-bg", settings.form_background_color):
		rules.append(".form-control {\n  background-color: var(--pt-form-bg) !important;\n}")
	if var("--pt-form-text", settings.form_text_color):
		rules.append(".form-control {\n  color: var(--pt-form-text) !important;\n}")

	# section headings — scoped to page/section headings, NOT every h1-h6 in Desk
	if var("--pt-section-heading", settings.section_heading_color):
		rules.append(
			".page-title .title-text,\n"
			".form-section .section-head,\n"
			".section-head,\n"
			".widget .widget-title {\n"
			"  color: var(--pt-section-heading) !important;\n}"
		)

	# field labels
	if var("--pt-label-text", settings.label_text_color):
		rules.append(
			".control-label, .grid-heading-row {\n  color: var(--pt-label-text) !important;\n}"
		)

	if not rules:
		return ""

	var_block = ":root {\n" + "\n".join(f"  {k}: {v};" for k, v in css_vars.items()) + "\n}"
	return var_block + "\n\n" + "\n\n".join(rules)


# ---------------------------------------------------------
# FINAL BUNDLE
# ---------------------------------------------------------


def merge_theme_css() -> str:
	"""The single served stylesheet. Order (later wins at equal specificity):
	settings chrome CSS -> active theme css_content (the hand-editable artifact,
	whose CUSTOM tail is therefore always last)."""
	settings = frappe.get_cached_doc("Portal Theme Setting")
	active = frappe.get_all(
		"Portal Theme",
		filters={"is_active": 1},
		fields=["name", "css_content"],
		limit=1,
	)

	parts = []

	settings_css = build_settings_css(settings)
	if settings_css:
		parts.append("/* -- Portal Theme Setting (desk chrome) -- */\n" + settings_css)

	if active and (active[0].css_content or "").strip():
		parts.append(
			f"/* -- active Portal Theme: {active[0].name} -- */\n" + active[0].css_content
		)

	if not parts:
		return ""

	header = (
		"/* portal_theme bundle — settings: "
		f"{'on' if settings.enable else 'off'}; theme: {active[0].name if active else 'none'} */"
	)
	return header + "\n\n" + "\n\n".join(parts)
