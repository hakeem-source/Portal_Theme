# Copyright (c) 2025, Sudhanshu Badole and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

from portal_theme import css_builder


class ThemeTemplate(Document):
	def before_insert(self):
		if not self.version:
			self.version = frappe.__version__

	def on_update(self):
		# templates only affect the next Regenerate, but invalidating is free
		css_builder.clear_theme_cache()
