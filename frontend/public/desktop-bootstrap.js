(() => {
  const desktop = new URLSearchParams(window.location.search).get("desktop") === "1";
  window.__otpDesktopMode = desktop;
  window.__otpNativeBridgeReady = false;
  window.addEventListener("pywebviewready", () => {
    window.__otpNativeBridgeReady = true;
  });
})();
