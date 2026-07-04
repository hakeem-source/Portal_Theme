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


def queue_clear_theme_cache():
	"""Invalidate AFTER the transaction commits — clearing mid-transaction lets a
	concurrent get_theme_bundle re-cache the OLD css for the 24h TTL window."""
	after_commit = getattr(frappe.db, "after_commit", None)
	if after_commit is not None:
		after_commit.add(clear_theme_cache)
	else:
		clear_theme_cache()


def _neutralize_sentinels(css: str) -> str:
	"""Foreign CSS (templates, custom selectors) must never contain our structural
	markers — an embedded PT:GENERATED:END would corrupt split_custom_tail and make
	css_content grow on every Regenerate."""
	return (css or "").replace("PT:GENERATED:", "PT-GENERATED-")


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
	return _neutralize_sentinels(
		frappe.db.get_value("Theme Template", theme.theme_template, "theme_template")
		or f"/* Theme Template {theme.theme_template!r} is empty */"
	)


# ---------------------------------------------------------
# COLOR MATH (for the auto readable row-hover)
# ---------------------------------------------------------

def _hxrgb(h):
	h = (h or "").strip().lstrip("#")
	if len(h) == 3:
		h = "".join(c * 2 for c in h)
	return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _rgbhx(t):
	return "#%02X%02X%02X" % tuple(max(0, min(255, round(c))) for c in t)


def _blend(a, b, t):
	ra, rb = _hxrgb(a), _hxrgb(b)
	return _rgbhx(tuple(ra[i] + (rb[i] - ra[i]) * t for i in range(3)))


def _lin(c):
	c /= 255.0
	return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def _lum(h):
	r, g, b = _hxrgb(h)
	return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def _contrast(a, b):
	la, lb = _lum(a), _lum(b)
	hi, lo = max(la, lb), min(la, lb)
	return (hi + 0.05) / (lo + 0.05)


def _readable(bg, prefer):
	"""theme text token if it clears AA on bg, else near-black/near-white — whichever wins."""
	if prefer and _contrast(bg, prefer) >= 4.5:
		return prefer
	return "#111418" if _contrast(bg, "#111418") >= _contrast(bg, "#F5F5F5") else "#F5F5F5"


def _theme_var(theme, name):
	for row in theme.get("theme_variables") or []:
		if (row.variable_name or "").strip() == name:
			return row
	return None


def build_row_hover_css(theme) -> str:
	"""List-row hover that ALWAYS outranks the zebra stripe (which is !important) AND
	stays readable. Auto-derived from the theme's surface (--secondary) + accent, so a
	striped row never loses its hover and hover never makes a row unreadable. The
	`nth-child(even):hover` selector (specificity 0,4,0) beats the zebra's (0,3,0)."""
	sec = _theme_var(theme, "--secondary")
	acc = _theme_var(theme, "--accent")
	if not sec or not acc:
		return ""
	try:
		sL = sec.light_value
		sD = sec.dark_value or sL
		aL = acc.light_value
		aD = acc.dark_value or aL
		hL = _blend(sL, aL, 0.13)
		hD = _blend(sD, aD, 0.13)
		tL = _readable(hL, sec.light_text or "#111418")
		tD = _readable(hD, sec.dark_text or "#F5F5F5")
	except Exception:
		return ""  # non-hex values — skip rather than break generation

	bg = ".list-row-container:hover .list-row, .list-row-container:nth-child(even):hover .list-row"
	tx = (".list-row-container:hover .list-row a, .list-row-container:hover .list-row .ellipsis, "
	      ".list-row-container:hover .list-row .level-item, .list-row-container:hover .list-row .list-row-col")

	def dark(sel):
		return ", ".join('[data-theme="dark"] ' + p.strip() for p in sel.split(","))

	return (
		f"{bg} {{ background-color: {hL} !important; color: {tL} !important; }}\n"
		f"{tx} {{ color: {tL} !important; }}\n"
		f"{dark(bg)} {{ background-color: {hD} !important; color: {tD} !important; }}\n"
		f"{dark(tx)} {{ color: {tD} !important; }}"
	)


def build_generated_css(theme) -> str:
	"""The full generated (sentinel-wrapped) section: tokens -> template -> component rows -> row hover."""
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

	row_hover = build_row_hover_css(theme)
	if row_hover:
		parts += ["", "/* -- row hover (auto: outranks zebra, contrast-safe) -- */", row_hover]

	parts.append(GENERATED_END)
	return "\n".join(parts)


# ---------------------------------------------------------
# COMPONENT REGISTRY (entity-based styling)
# ---------------------------------------------------------
# Human-named UI entities -> vetted Frappe v15 Desk/website selectors.
# Extending the registry = adding one entry here (and mirroring the key in the
# Component Style child doctype's `component` Select options).

CUSTOM_SELECTOR = "Custom Selector"

COMPONENT_REGISTRY = {
	# navbar
	"Navbar / Bar": ".navbar",
	"Navbar / Links": (
		".navbar .navbar-brand, .navbar .navbar-nav > li > .nav-link, "
		".navbar #navbar-breadcrumbs li a"
	),
	"Navbar / Dropdown Menu": ".navbar .dropdown-menu, .navbar .dropdown-menu .dropdown-item",
	"Navbar / Awesomebar Input": ".navbar .awesomplete > input.form-control",
	"Navbar / Awesomebar Dropdown": ".navbar .awesomplete > ul, .navbar .awesomplete > ul > li",
	"Navbar / Awesomebar Selected Item": '.navbar .awesomplete > ul > li[aria-selected="true"]',
	# buttons
	"Button / Primary": ".btn.btn-primary",
	"Button / Secondary": ".btn.btn-secondary",
	"Button / Danger": ".btn.btn-danger",
	# fields (editable vs read-only styled independently)
	"Field / Editable Input": (
		"input.form-control:not([readonly]):not([disabled]), "
		"textarea.form-control:not([readonly]):not([disabled]), "
		"select.form-control:not([disabled])"
	),
	"Field / Read-only or Disabled": (
		".like-disabled-input, .form-control[readonly], .form-control[disabled], input[disabled]"
	),
	"Field / Label": ".control-label",
	# form view
	"Form / Section Head": ".form-section .section-head, .section-head",
	"Form / Sidebar": ".form-sidebar",
	"Form / Grid Header": ".grid-heading-row",
	"Form / Grid Row": ".grid-body .grid-row",
	"Form / Tab (inactive)": ".form-tabs-list .nav-link",
	"Form / Tab (active)": ".form-tabs-list .nav-link.active",
	# list view
	"List / Header": ".list-row-head",
	"List / Row": ".list-row-container .list-row",
	"List / Zebra Stripe (even rows)": ".list-row-container:nth-child(even) .list-row",
	"List / Filter Controls": ".standard-filter-section .form-control",
	# dialogs
	"Dialog / Header": ".modal .modal-header",
	"Dialog / Body": ".modal .modal-body",
	"Dialog / Content": ".modal .modal-content",
	# sidebar
	"Sidebar / Item": ".desk-sidebar .desk-sidebar-item",
	"Sidebar / Item Selected": ".desk-sidebar .desk-sidebar-item.selected",
	# page chrome
	"Page / Background": "body, .content.page-container",
	"Page / Title": ".page-title .title-text",
	"Page / Breadcrumbs": "#navbar-breadcrumbs li a",
	# workspace widgets
	"Workspace / Widget Card": ".widget",
	"Workspace / Widget Title": ".widget .widget-title",
	"Workspace / Shortcut": ".widget.shortcut-widget-box",
	# login page (delivered via web_include_js)
	"Login / Card": ".for-login .page-card, .for-login .page-card-container",
	"Login / Card Button": ".for-login .btn-primary, .for-login .btn-login",
	"Login / Card Inputs": ".for-login .form-control",
	"Login / Footer": ".web-footer",
	# escape hatch: selector comes from the row itself
	CUSTOM_SELECTOR: None,
}

# property label -> (css property, pseudo-class suffix)
COMPONENT_PROPERTIES = {
	"Background": ("background-color", ""),
	"Text": ("color", ""),
	"Border Color": ("border-color", ""),
	"Border Radius": ("border-radius", ""),
	"Box Shadow": ("box-shadow", ""),
	"Hover Background": ("background-color", ":hover"),
	"Hover Text": ("color", ":hover"),
	"Focus Ring": ("box-shadow", ":focus"),
}


def _component_selector(row):
	if row.component == CUSTOM_SELECTOR:
		return _neutralize_sentinels((row.custom_selector or "").strip())
	return COMPONENT_REGISTRY.get(row.component) or ""


def _apply_pseudo(selector: str, pseudo: str) -> str:
	if not pseudo:
		return selector
	return ", ".join(part.strip() + pseudo for part in selector.split(","))


def _dark_scope(selector: str) -> str:
	return ", ".join('[data-theme="dark"] ' + part.strip() for part in selector.split(","))


def _normalize_value(prop_label: str, value: str) -> str:
	value = (value or "").strip().rstrip(";")
	if not value:
		return ""
	if prop_label == "Border Radius" and value.isdigit():
		value += "px"
	return value


def validate_component_styles(theme):
	"""Reject invalid rows at save time with actionable messages."""
	for row in theme.get("component_styles") or []:
		if not row.enabled:
			continue
		label = f"Component Styles row #{row.idx}"
		if row.component not in COMPONENT_REGISTRY:
			frappe.throw(f"{label}: unknown component {row.component!r}.")
		if row.property not in COMPONENT_PROPERTIES:
			frappe.throw(f"{label}: unknown property {row.property!r}.")
		if row.component == CUSTOM_SELECTOR and not (row.custom_selector or "").strip():
			frappe.throw(f"{label}: 'Custom Selector' rows need a selector.")
		if "}" in (row.custom_selector or "") or "{" in (row.custom_selector or ""):
			frappe.throw(f"{label}: the selector must not contain braces.")
		for field_label, val in (("light value", row.light_value), ("dark value", row.dark_value)):
			if val and ("{" in val or "}" in val):
				frappe.throw(f"{label}: the {field_label} must not contain braces.")
		if not (row.light_value or "").strip() and not (row.dark_value or "").strip():
			frappe.throw(f"{label}: set a light and/or dark value.")


def build_component_css(theme) -> str:
	"""CSS from Component Style rows: one light rule per row, plus a
	[data-theme="dark"]-scoped counterpart when a dark value is set."""
	light_rules = []
	dark_rules = []

	for row in theme.get("component_styles") or []:
		if not row.enabled:
			continue
		selector = _component_selector(row)
		prop = COMPONENT_PROPERTIES.get(row.property)
		if not selector or not prop:
			continue
		css_prop, pseudo = prop
		target = _apply_pseudo(selector, pseudo)

		light_value = _normalize_value(row.property, row.light_value)
		dark_value = _normalize_value(row.property, row.dark_value)

		if light_value:
			light_rules.append(f"{target} {{ {css_prop}: {light_value} !important; }}")
		if dark_value:
			dark_rules.append(
				f"{_dark_scope(target)} {{ {css_prop}: {dark_value} !important; }}"
			)

	return "\n".join(light_rules + dark_rules)


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
	# No sentinel: legacy content was 100% machine-generated by the old engine
	# (it clobbered every save), and Regenerate snapshots the pre-image as a
	# revision before calling this — preserving it as a tail would let its stale
	# :root tokens permanently override every future regenerate (tail wins the
	# cascade). Replace it; it stays restorable from the revision.
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
