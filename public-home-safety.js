(() => {
  if (window.__MISTICA_PUBLIC_HOME_SAFETY_LOADED__) return;
  window.__MISTICA_PUBLIC_HOME_SAFETY_LOADED__ = true;

  function isAdminMode() {
    const params = new URLSearchParams(window.location.search);
    return params.get("admin") === "mistica" || window.location.hash === "#admin-mistica";
  }

  function apply() {
    if (isAdminMode()) return;
    document.querySelectorAll(".internal-section").forEach(section => { section.hidden = true; });
    const admin = document.getElementById("admin");
    if (admin) admin.hidden = true;
    document.querySelectorAll("#clientForm, #supplierForm, #adminLoginForm").forEach(form => {
      form.setAttribute("aria-hidden", "true");
    });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", apply, { once: true });
  else apply();
})();
