(() => {
  const screenshots = [
    {
      src: "assets/screenshots/dashboard-web.png",
      alt: "Tableau de bord OTP LOL avec les champions prioritaires et les réglages de partie",
      label: "TABLEAU DE BORD",
      title: "Tableau de bord",
      caption: "Capture du tableau de bord",
      note: "Retrouve tes priorités, les actions activées et l’état de League dans ton tableau de bord.",
    },
    {
      src: "assets/screenshots/settings-web.png",
      alt: "Réglages OTP LOL pour les automatismes et la configuration locale",
      label: "RÉGLAGES",
      title: "Réglages",
      caption: "Capture des réglages",
      note: "Choisis les automatismes et les options qui correspondent à ta façon de jouer.",
    },
    {
      src: "assets/screenshots/statistics-web.png",
      alt: "Statistiques OTP LOL avec le compte League et les fournisseurs disponibles",
      label: "STATISTIQUES",
      title: "Statistiques",
      caption: "Capture de l’écran des statistiques",
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
        caption.textContent = screenshot.caption;
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
        dialogTitle.textContent = selected.title;
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

})();
