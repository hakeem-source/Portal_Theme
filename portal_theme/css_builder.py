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
