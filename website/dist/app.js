(() => {
  const screenshots = [
    {
      src: "assets/screenshots/dashboard-web.png",
      alt: "Tableau de bord OTP LOL avec les presets de champions et les automatismes configurables",
      label: "TABLEAU DE BORD",
      caption: "du tableau de bord",
      note: "Retrouve tes presets, les actions activées et l’état du client dans une vue simple.",
    },
    {
      src: "assets/screenshots/settings-web.png",
      alt: "Réglages OTP LOL pour les automatismes et la configuration locale",
      label: "RÉGLAGES",
      caption: "des réglages",
      note: "Choisis les automatismes et les options qui correspondent à ta façon de jouer.",
    },
    {
      src: "assets/screenshots/statistics-web.png",
      alt: "Statistiques OTP LOL avec le compte League et les fournisseurs disponibles",
      label: "STATISTIQUES",
      caption: "des statistiques",
      note: "Retrouve le compte utilisé et ouvre tes services de statistiques depuis l’application.",
    },
  ];

  const image = document.querySelector("#showcase-image");
  const label = document.querySelector("#showcase-label");
  const caption = document.querySelector("#showcase-caption");
  const note = document.querySelector("#shot-note");
  const tabs = [...document.querySelectorAll("[data-shot]")];

  if (image && label && caption && note && tabs.length === screenshots.length) {
    tabs.forEach((tab) => {
      tab.addEventListener("click", () => {
        const screenshot = screenshots[Number(tab.dataset.shot)];
        if (!screenshot) return;

        if (image.getAttribute("src") !== screenshot.src) {
          image.classList.add("is-changing");
          const finishTransition = () => image.classList.remove("is-changing");
          image.addEventListener("load", finishTransition, { once: true });
          image.addEventListener("error", finishTransition, { once: true });
          image.src = screenshot.src;
          if (image.complete) finishTransition();
        }

        image.alt = screenshot.alt;
        label.textContent = screenshot.label;
        caption.textContent = "Capture " + screenshot.caption;
        note.textContent = screenshot.note;

        tabs.forEach((item) => {
          const isSelected = item === tab;
          item.classList.toggle("is-active", isSelected);
          item.setAttribute("aria-pressed", String(isSelected));
        });
      });
    });

    const expandButton = document.querySelector("#expand-shot");
    const dialog = document.querySelector("#shot-dialog");
    const dialogTitle = document.querySelector("#dialog-title");
    const dialogImage = document.querySelector("#dialog-image");
    const closeButton = document.querySelector("#close-shot");

    if (expandButton && dialog && dialogTitle && dialogImage && closeButton) {
      expandButton.addEventListener("click", () => {
        const selected = screenshots.find((screenshot) => screenshot.src === image.getAttribute("src")) ?? screenshots[0];
        dialogTitle.textContent = "Capture " + selected.caption;
        dialogImage.src = selected.src;
        dialogImage.alt = selected.alt;
        if (typeof dialog.showModal === "function") dialog.showModal();
      });
      closeButton.addEventListener("click", () => dialog.close());
      dialog.addEventListener("click", (event) => {
        if (event.target === dialog) dialog.close();
      });
    }
  }

  const revealItems = document.querySelectorAll("[data-reveal]");
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  if (revealItems.length && "IntersectionObserver" in window && !reducedMotion) {
    document.body.classList.add("reveal-ready");
    const revealObserver = new IntersectionObserver((entries, observer) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add("is-visible");
        observer.unobserve(entry.target);
      });
    }, { threshold: 0.12, rootMargin: "0px 0px -4% 0px" });

    revealItems.forEach((item) => revealObserver.observe(item));
  }
})();
