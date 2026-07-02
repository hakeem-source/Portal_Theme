// Portal Theme — single stylesheet injector (Desk + website).
// Kill switch: append ?no_theme=1 to any URL to disable theming for the browser
// session (works even when the served CSS makes the UI unreadable, because it
// runs before any network call). ?no_theme=0 re-enables.
(function () {
	try {
		const params = new URLSearchParams(window.location.search);
		if (params.get("no_theme") === "1") sessionStorage.setItem("portal_theme_off", "1");
		if (params.get("no_theme") === "0") sessionStorage.removeItem("portal_theme_off");
		if (sessionStorage.getItem("portal_theme_off")) return;
	} catch (e) {
		// sessionStorage unavailable (rare) — fall through and theme normally
	}

	if (!window.frappe || !frappe.call) return;

	frappe.call({
		method: "portal_theme.api.get_theme_bundle",
		type: "GET",
		callback(r) {
			const m = r && r.message;
			if (!m || !m.css) return;

			let tag = document.getElementById("portal-theme-css");
			if (!tag) {
				tag = document.createElement("style");
				tag.id = "portal-theme-css";
				document.head.appendChild(tag);
			}
			if (tag.dataset.hash !== m.hash) {
				tag.textContent = m.css;
				tag.dataset.hash = m.hash;
			}
		},
	});
})();
