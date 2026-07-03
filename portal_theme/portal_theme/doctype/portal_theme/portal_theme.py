# Copyright (c) 2025, Sudhanshu Badole
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from portal_theme import css_builder

REVISION_LIMIT = 20  # FIFO ring buffer: inserting past the cap evicts the oldest


class PortalTheme(Document):
	# ---------------------------------------------------------
	# HOOKS
	# ---------------------------------------------------------

	def before_save(self):
		# only an activation should deactivate the others (saving an inactive
		# theme must never touch the currently active one)
		if self.is_active:
			others = frappe.get_all(
				self.doctype,
				filters={"is_active": 1, "name": ["!=", self.name]},
				pluck="name",
			)
			for name in others:
				frappe.db.set_value(self.doctype, name, "is_active", 0)

		self.slugify_theme_name()

		if not (self.css_content or "").strip():
			# cleared on an existing doc: snapshot the old CSS before reseeding
			# (make_css_revision no-ops on empty old_css, so first saves are unaffected)
			if not self.is_new():
				before = self.get_doc_before_save()
				if before:
					make_css_revision(
						self.name,
						before.css_content,
						"Manual Edit",
						note="Cleared in editor; reseeded generated CSS",
					)
			# first save (or cleared field): seed generated CSS + custom tail
			self.css_content = css_builder.initial_css_content(self)
		elif not self.is_new():
			# manual edit: snapshot the previous content before it is replaced
			before = self.get_doc_before_save()
			if before and (before.css_content or "") != (self.css_content or ""):
				make_css_revision(self.name, before.css_content, "Manual Edit")

	def validate(self):
		css_builder.validate_component_styles(self)

	def on_update(self):
		css_builder.queue_clear_theme_cache()

	def on_trash(self):
		revisions = frappe.get_all(
			"Portal Theme CSS Revision", filters={"portal_theme": self.name}, pluck="name"
		)
		for name in revisions:
			frappe.delete_doc(
				"Portal Theme CSS Revision", name, ignore_permissions=True, force=True
			)
		css_builder.queue_clear_theme_cache()

	# ---------------------------------------------------------
	# SLUG UTILITIES
	# ---------------------------------------------------------

	@staticmethod
	def slugify(value: str) -> str:
		return css_builder.slugify(value)

	def slugify_theme_name(self):
		if self.theme_name:
			self.slug = self.slugify(self.theme_name)

	# ---------------------------------------------------------
	# REGENERATION (explicit, confirmed, revision-backed)
	# ---------------------------------------------------------

	@frappe.whitelist()
	def regenerate_css(self):
		"""Rebuild the generated (sentinel) section from theme variables, the linked
		Theme Template and Component Style rows. The custom tail is preserved and the
		pre-image is always snapshotted as a revision first."""
		frappe.only_for("System Manager")

		if not self.theme_template:
			frappe.throw(_("Select a Theme Template before regenerating."))
		# same guard as the save path — regenerate must not serve rows a save would reject
		css_builder.validate_component_styles(self)

		make_css_revision(self.name, self.css_content, "Regenerate")
		new_css = css_builder.regenerate_css_content(self)
		self.db_set("css_content", new_css)
		css_builder.queue_clear_theme_cache()
		return new_css


# ---------------------------------------------------------
# REVISIONS
# ---------------------------------------------------------


def make_css_revision(theme_name, old_css, trigger, note=None):
	"""Snapshot old_css as a revision, keeping at most REVISION_LIMIT per theme
	(FIFO: the oldest revision is deleted to make room for the newest)."""
	if not (old_css or "").strip():
		return

	frappe.get_doc(
		{
			"doctype": "Portal Theme CSS Revision",
			"portal_theme": theme_name,
			"trigger": trigger,
			"css_content": old_css,
			"note": note,
		}
	).insert(ignore_permissions=True)

	stale = frappe.get_all(
		"Portal Theme CSS Revision",
		filters={"portal_theme": theme_name},
		order_by="creation desc",
		pluck="name",
	)[REVISION_LIMIT:]
	for name in stale:
		frappe.delete_doc(
			"Portal Theme CSS Revision", name, ignore_permissions=True, force=True
		)


@frappe.whitelist()
def restore_revision(revision):
	"""Restore a CSS snapshot onto its theme. The theme's current CSS is snapshotted
	as a Pre-Restore revision first, so a restore can itself be undone."""
	frappe.only_for("System Manager")

	rev = frappe.get_doc("Portal Theme CSS Revision", revision)
	theme = frappe.get_doc("Portal Theme", rev.portal_theme)

	make_css_revision(theme.name, theme.css_content, "Pre-Restore", note=_("Before restoring {0}").format(revision))
	theme.db_set("css_content", rev.css_content)
	css_builder.queue_clear_theme_cache()
	return theme.name
