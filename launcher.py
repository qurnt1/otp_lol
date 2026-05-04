"""
FILE NAME: launcher.py
GLOBAL PURPOSE:
- Bootstrap the desktop application and coordinate the main runtime dependencies.
- Create the UI, background services, and shared configuration in a safe startup order.
- Guarantee orderly shutdown, cleanup, and background task handoff.

KEY FUNCTIONS:
- OtpLolApplication: Own the application lifecycle from startup to cleanup.
- _load_datadragon_async: Load champion metadata without blocking the UI thread.
- _check_updates_async: Fetch update metadata in the background and surface it to the UI.
- main: Start the application and guard the top-level error path.

AUDIENCE & LOGIC:
Why:
This module exists as the single runtime entry point so startup ordering, shared state wiring, and shutdown guarantees remain easy to reason about.
For whom:
Developers maintaining the desktop app lifecycle and anyone debugging startup or shutdown behavior.

DEPENDENCIES:
Used by:
- Executed directly for local runs and by create_exe.py during packaging.
Uses:
- Standard library: logging, sys, threading, typing
- Local modules: src.config, src.core, src.services, src.ui
"""

import sys
import logging
from threading import Thread, Lock
from typing import Dict, Any

from src.config import (
    load_parameters, save_parameters,
    get_cache_dirs, CURRENT_VERSION
)
from src.core import DataDragon, WebSocketManager
from src.services.single_instance import check_single_instance, remove_lockfile
from src.services.updates import check_for_updates
from src.ui import LoLAssistantUI


class OtpLolApplication:
    """Coordinate startup, background services, and final cleanup for the app."""
    
    def __init__(self):
        """Initialize shared runtime services in the only safe startup order."""
        # UI scaling must be configured before the Tk window is created.
        try:
            from ctypes import windll
            windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
        self._shutdown_lock = Lock()
        self._shutdown_started = False
        self._cleanup_done = False
        
        # The single-instance guard prevents concurrent processes from racing on
        # shared settings, tray resources, and the lock file.
        if not check_single_instance():
            logging.info("Another instance is already running. Closing.")
            sys.exit(0)
        
        # Keep one in-memory settings snapshot that the UI and websocket layer can share.
        self._params: Dict[str, Any] = load_parameters()
        
        # Cache folders are created early because both the UI and metadata loader depend on them.
        get_cache_dirs()
        
        # DataDragon is instantiated immediately so dependent objects can reference it,
        # but the expensive load stays asynchronous to avoid blocking first paint.
        logging.info("Initializing DataDragon...")
        self.dd = DataDragon()
        
        # Build the UI before the background metadata load so the app becomes interactive sooner.
        logging.info("Creating UI...")
        self.ui = LoLAssistantUI(
            dd=self.dd,
            params=self._params,
            save_callback=self._save_params,
            update_param_callback=self._update_param,
            get_params_callback=self._get_params,
            quit_callback=self.quit_app
        )
        
        # The websocket manager owns live client events and pushes them back into the UI.
        logging.info("Initializing WebSocket...")
        self.ws_manager = WebSocketManager(
            ui_callback=self.ui.on_core_event,
            dd=self.dd,
            get_params=self._get_params,
            update_param=self._update_param
        )
        
        # Wire the UI to the live manager before any background work starts emitting events.
        self.ui.set_ws_manager(self.ws_manager)
        
        # Metadata and update checks run in the background so startup stays responsive.
        self._load_datadragon_async()
        self._check_updates_async()
        
        # Start the LCU bridge last so event handling cannot fire before the UI is ready.
        self.ws_manager.start()
    
    def _load_datadragon_async(self) -> None:
        """Load DataDragon off the UI thread and report the result back safely."""
        def load_task():
            try:
                logging.info("Loading DataDragon in the background...")
                self.dd.load()
                
                # UI notifications must be marshalled back through Tk once metadata becomes available.
                champion_count = len(self.dd.all_names)
                if champion_count > 0:
                    message = f"Champions loaded ({champion_count})"
                    self.ui.root.after(0, lambda: self.ui.show_toast(message, duration=1500))
                    logging.info(f"DataDragon loaded: {champion_count} champions")
                else:
                    logging.warning("DataDragon loaded without champions")
                    
            except Exception as e:
                logging.error(f"Error while loading DataDragon: {e}")
                self.ui.root.after(0, lambda: self.ui.show_toast("Champion loading error", duration=3000))
        
        # Reuse the UI executor when available so background work shares the same shutdown path.
        if hasattr(self.ui, 'executor'):
            self.ui.executor.submit(load_task)
        else:
            Thread(target=load_task, daemon=True).start()
    
    def _get_params(self) -> Dict[str, Any]:
        """Return a defensive copy of the current parameter snapshot."""
        return self._params.copy()
    
    def _update_param(self, key: str, value: Any) -> None:
        """Update one in-memory parameter value shared by the runtime components."""
        self._params[key] = value
    
    def _save_params(self) -> None:
        """Persist the current parameter snapshot and log the outcome."""
        if save_parameters(self._params):
            logging.info("Settings saved successfully.")
        else:
            logging.error("Failed to save settings.")
    
    def _check_updates_async(self) -> None:
        """Check for remote releases off the UI thread and notify the window if needed."""
        def check_task():
            try:
                update_info = check_for_updates()
                if update_info:
                    new_version = str(update_info.get("version") or "")
                    ignored_version = str(self._params.get("ignored_update_version") or "").strip()
                    if ignored_version and ignored_version == new_version:
                        logging.info(f"Update {new_version} ignored by user preference.")
                        return
                    logging.info(f"New version available: {new_version}")
                    # The popup is scheduled on the UI thread because Tk widgets are not thread-safe.
                    self.ui.root.after(0, lambda: self.ui.show_update_popup(update_info))
                else:
                    logging.info("Application is up to date.")
            except Exception as e:
                logging.warning(f"Error while checking for updates: {e}")
        
        # Reuse the same executor strategy as the metadata loader for consistent shutdown behavior.
        if hasattr(self.ui, 'executor'):
            self.ui.executor.submit(check_task)
        else:
            Thread(target=check_task, daemon=True).start()
    
    def run(self) -> None:
        """Enter the UI main loop and guarantee cleanup when it exits."""
        logging.info(f"OTP LOL v{CURRENT_VERSION} started.")
        try:
            self.ui.run()
        finally:
            self.cleanup()
    
    def quit_app(self) -> None:
        """Request a single orderly shutdown, even if multiple callers race to close the app."""
        with self._shutdown_lock:
            if self._shutdown_started:
                return
            self._shutdown_started = True

        logging.info("Closing application...")
        try:
            self._save_params()
            self.ws_manager.stop()
            self.ui.stop()
        finally:
            self.cleanup()
    
    def cleanup(self) -> None:
        """Perform idempotent final cleanup for lock-file based single-instance protection."""
        if self._cleanup_done:
            return
        self._cleanup_done = True
        remove_lockfile()
        logging.info("Cleanup complete.")


def main() -> None:
    """Run the desktop application and guard the top-level failure path."""
    try:
        app = OtpLolApplication()
        app.run()
    except KeyboardInterrupt:
        logging.info("Keyboard interrupt detected.")
    except Exception as e:
        logging.critical(f"Fatal error: {e}", exc_info=True)
    finally:
        remove_lockfile()


if __name__ == "__main__":
    main()
