document.addEventListener("DOMContentLoaded", () => {
  const params = new URLSearchParams(window.location.search);
  const openAdmin = params.get("admin") === "mistica" || window.location.hash === "#admin-mistica";
  const admin = document.getElementById("admin");
  const internalSections = document.querySelectorAll(".internal-section");

  if (admin && !openAdmin) {
    admin.style.display = "none";
  }

  internalSections.forEach(section => {
    section.style.display = "none";
  });

  if (admin && openAdmin) {
    admin.style.display = "block";
    setTimeout(() => admin.scrollIntoView({ behavior: "smooth" }), 250);
  }
});
