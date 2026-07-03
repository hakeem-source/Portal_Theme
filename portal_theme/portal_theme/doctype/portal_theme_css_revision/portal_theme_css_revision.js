// Copyright (c) 2026, Starlink Gulf Trading Ltd
// For license information, please see license.txt

frappe.ui.form.on("Portal Theme CSS Revision", {
	refresh(frm) {
		if (frm.is_new()) return;

		frm.add_custom_button(__("Restore This Revision"), () => {
			frappe.confirm(
				__(
					"Restore this CSS snapshot onto <b>{0}</b>?<br><br>The theme's current CSS will be saved as a <i>Pre-Restore</i> revision first, so this action can itself be undone.",
					[frm.doc.portal_theme]
				),
				() => {
					frappe
						.call({
							method:
								"portal_theme.portal_theme.doctype.portal_theme.portal_theme.restore_revision",
							args: { revision: frm.doc.name },
						})
						.then(() => {
							frappe.show_alert({ message: __("Revision restored"), indicator: "green" });
							// evict the cached doc so the form refetches the restored CSS
							frappe.model.remove_from_locals("Portal Theme", frm.doc.portal_theme);
							frappe.set_route("Form", "Portal Theme", frm.doc.portal_theme);
						});
				}
			);
		}).addClass("btn-primary");
	},
});
