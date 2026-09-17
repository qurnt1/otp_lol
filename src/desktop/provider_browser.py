"""Top-level pywebview window for allowlisted third-party provider pages."""

from __future__ import annotations

import logging
from collections.abc import Callable

from ..services.urls import get_provider, is_allowed_provider_url


class ProviderBrowserWindow:
    def __init__(self, provider_id: str, url: str, on_closed: Callable[[], None]) -> None:
        self.provider_id = provider_id
        self.url = url
        self.on_closed = on_closed
        self.window = None

    def open(self) -> bool:
        provider = get_provider(self.provider_id)
        if provider is None or not is_allowed_provider_url(self.provider_id, self.url):
            return False
        try:
            import webview

            webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = True
            self.window = webview.create_window(
                f"{provider.label} | OTP LOL",
                url=self.url,
                width=1100,
                height=760,
                min_size=(800, 540),
                resizable=True,
                js_api=None,
                text_select=True,
            )
            closed = getattr(getattr(self.window, "events", None), "closed", None)
            if closed is not None:
                closed += self.on_closed
            return True
        except Exception as error:
            logging.warning("Unable to open provider window: %s", error)
            return False
