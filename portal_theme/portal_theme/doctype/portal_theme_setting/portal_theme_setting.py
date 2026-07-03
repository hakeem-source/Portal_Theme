# Copyright (c) 2025, Indictrans and contributors
# For license information, please see license.txt

from frappe.model.document import Document

from portal_theme import css_builder


class PortalThemeSetting(Document):
	def validate(self):
		if self.enable:
			self.status = "Active"
		else:
			self.status = "Inactive"

	def on_update(self):
		css_builder.queue_clear_theme_cache()
