(() => {
  const menuToggle = document.getElementById("menu-toggle");
  const navLinks = document.getElementById("nav-links");
  if (!menuToggle || !navLinks) return;

  function closeMobileMenu(returnFocus = false) {
    navLinks.classList.remove("open");
    menuToggle.setAttribute("aria-expanded", "false");
    menuToggle.setAttribute("aria-label", "Open navigation menu");
    if (returnFocus) menuToggle.focus();
  }

  menuToggle.addEventListener("click", () => {
    const isOpen = menuToggle.getAttribute("aria-expanded") === "true";
    menuToggle.setAttribute("aria-expanded", String(!isOpen));
    menuToggle.setAttribute("aria-label", isOpen ? "Open navigation menu" : "Close navigation menu");
    navLinks.classList.toggle("open", !isOpen);
    if (!isOpen) navLinks.querySelector("a").focus();
  });

  navLinks.querySelectorAll("a").forEach((link) => {
    link.addEventListener("click", () => {
      closeMobileMenu();
      const destination = new URL(link.href, window.location.href);
      if (destination.pathname !== window.location.pathname || !destination.hash) return;
      const target = document.getElementById(destination.hash.slice(1));
      if (target) target.focus({ preventScroll: true });
    });
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && navLinks.classList.contains("open")) {
      closeMobileMenu(true);
    }
  });

  window.addEventListener("resize", () => {
    if (window.innerWidth > 860 && navLinks.classList.contains("open")) {
      closeMobileMenu();
    }
  });
})();
