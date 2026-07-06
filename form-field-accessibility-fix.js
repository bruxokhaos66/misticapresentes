(() => {
  const prefix = "mistica-field";

  function slug(value) {
    return String(value || "campo")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/[^a-zA-Z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "")
      .toLowerCase()
      .slice(0, 48) || "campo";
  }

  function labelFor(field, index) {
    return field.getAttribute("aria-label")
      || field.getAttribute("placeholder")
      || field.dataset?.adminActivitySearch
      || field.dataset?.fieldPurpose
      || field.type
      || field.tagName
      || `campo-${index + 1}`;
  }

  function ensureFieldIdentity(field, index) {
    if (!field || field.type === "hidden") return;

    const base = slug(labelFor(field, index));
    const identity = `${prefix}-${base}-${index + 1}`;

    if (!field.id) field.id = identity;
    if (!field.name) field.name = field.id;
  }

  function applyFormFieldAccessibilityFix() {
    document.querySelectorAll("input, select, textarea").forEach(ensureFieldIdentity);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", applyFormFieldAccessibilityFix, { once: true });
  } else {
    applyFormFieldAccessibilityFix();
  }

  window.addEventListener("load", () => {
    applyFormFieldAccessibilityFix();
    setTimeout(applyFormFieldAccessibilityFix, 500);
    setTimeout(applyFormFieldAccessibilityFix, 1500);
  });

  const observer = new MutationObserver(() => applyFormFieldAccessibilityFix());
  observer.observe(document.documentElement, { childList: true, subtree: true });

  window.misticaFormFieldFix = { apply: applyFormFieldAccessibilityFix };
})();
