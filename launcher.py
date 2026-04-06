"""
MAIN LOL - Point d'Entrée (Refactorisé v6.1)
---------------------------------------------
Initialise l'application, gère les threads et la fermeture propre.

Améliorations v6.1:
- Chargement asynchrone de DataDragon (ne bloque plus l'UI)
- Meilleure gestion des erreurs avec logging
"""

import sys
import logging
from threading import Thread, Lock
from typing import Dict, Any

# Imports locaux depuis le package src
from src.config import (
    load_parameters, save_parameters,
    get_cache_dirs, CURRENT_VERSION, PHASE_DISPLAY_MAP
)
from src.services import TelegramService
from src.utils import enable_high_dpi, check_single_instance, remove_lockfile, check_for_updates
from src.core import DataDragon, WebSocketManager
from src.ui import LoLAssistantUI


class MainLoLApplication:
    """Classe principale gérant le cycle de vie de l'application."""
    
    def __init__(self):
        """
        Initialise l'application MAIN LOL.
        
        v6.1: DataDragon est maintenant chargé de manière asynchrone
        pour éviter de bloquer l'interface utilisateur au démarrage.
        """
        # Activer High DPI
        enable_high_dpi()
        self._shutdown_lock = Lock()
        self._shutdown_started = False
        self._cleanup_done = False
        
        # Vérifier instance unique
        if not check_single_instance():
            logging.info("Une autre instance est déjà en cours. Fermeture.")
            sys.exit(0)
        
        # Charger les paramètres
        self._params: Dict[str, Any] = load_parameters()
        
        # Créer les dossiers de cache
        get_cache_dirs()
        
        # Initialiser DataDragon (NE PAS CHARGER ICI - fait en async)
        logging.info("Initialisation de DataDragon...")
        self.dd = DataDragon()
        # Note: dd.load() sera appelé en arrière-plan
        
        # Créer l'interface AVANT de charger DataDragon
        logging.info("Création de l'interface...")
        self.ui = LoLAssistantUI(
            dd=self.dd,
            params=self._params,
            save_callback=self._save_params,
            update_param_callback=self._update_param,
            get_params_callback=self._get_params,
            quit_callback=self.quit_app
        )
        
        # Créer le gestionnaire WebSocket
        logging.info("Initialisation du WebSocket...")
        self.ws_manager = WebSocketManager(
            ui_callback=self._handle_core_event,
            dd=self.dd,
            get_params=self._get_params,
            update_param=self._update_param
        )
        self.telegram_service = TelegramService(
            dd=self.dd,
            get_params=self._get_params,
            update_param=self._update_param,
            save_params=self._save_params,
            get_snapshot=self._build_runtime_snapshot,
            commit_remote_changes=self._commit_remote_changes,
        )
        
        # Connecter le WS à l'UI
        self.ui.set_ws_manager(self.ws_manager)
        self.ui.set_telegram_service(self.telegram_service)
        
        # Charger DataDragon en arrière-plan (v6.1)
        self._load_datadragon_async()
        
        # Vérifier les mises à jour en arrière-plan
        self._check_updates_async()
        
        # Démarrer le WebSocket
        self.ws_manager.start()
        self.telegram_service.start()
    
    def _load_datadragon_async(self) -> None:
        """
        Charge DataDragon en arrière-plan pour ne pas bloquer l'UI.
        
        Une fois chargé, affiche un toast de confirmation.
        """
        def load_task():
            try:
                logging.info("Chargement de DataDragon en arrière-plan...")
                self.dd.load()
                
                # Notifier l'UI que le chargement est terminé
                champion_count = len(self.dd.all_names)
                if champion_count > 0:
                    message = f"Champions chargés ({champion_count})"
                    self.ui.root.after(0, lambda: self.ui.show_toast(message, duration=1500))
                    logging.info(f"DataDragon chargé: {champion_count} champions")
                else:
                    logging.warning("DataDragon chargé mais sans champions")
                    
            except Exception as e:
                logging.error(f"Erreur lors du chargement de DataDragon: {e}")
                self.ui.root.after(0, lambda: self.ui.show_toast("Erreur chargement champions", duration=3000))
        
        # Utiliser le ThreadPoolExecutor de l'UI si disponible
        if hasattr(self.ui, 'executor'):
            self.ui.executor.submit(load_task)
        else:
            Thread(target=load_task, daemon=True).start()
    
    def _get_params(self) -> Dict[str, Any]:
        """Retourne les paramètres actuels."""
        return self._params.copy()
    
    def _update_param(self, key: str, value: Any) -> None:
        """Met à jour un paramètre."""
        self._params[key] = value

    def _handle_core_event(self, event_type: str, data: Any = None) -> None:
        """Diffuse les événements coeur vers l'UI et Telegram."""
        self.ui.on_core_event(event_type, data)
        if getattr(self, "telegram_service", None):
            self.telegram_service.handle_core_event(event_type, data)

    def _build_runtime_snapshot(self) -> Dict[str, Any]:
        """Construit un instantané compact pour Telegram et les diagnostics."""
        params = self._get_params()
        phase = self.ws_manager.state.current_phase if self.ws_manager else "None"
        return {
            "connected": bool(self.ws_manager.is_active if self.ws_manager else False),
            "phase": phase,
            "phase_label": PHASE_DISPLAY_MAP.get(phase, phase),
            "riot_id": self.ws_manager.get_riot_id() if self.ws_manager else params.get("manual_summoner_name", ""),
            "region": self.ui.get_platform_for_websites(),
            "detected_role": self.ws_manager.state.assigned_position if self.ws_manager else "GLOBAL",
            "selected_profile_role": params.get("selected_profile_role", "GLOBAL"),
            "effective": self.ws_manager.get_effective_profile_config() if self.ws_manager else {},
            "params": params,
            "lcu": self.ws_manager.get_diagnostics() if self.ws_manager else {},
        }

    def _commit_remote_changes(self, toast_message: str | None = None) -> None:
        """Sauvegarde puis reflète les changements issus des commandes Telegram."""
        self._save_params()

        def refresh_ui():
            self.ui._queue_feature_preview_refresh(force=True)
            self.ui._refresh_stats_button()
            if self.ui.settings_win and self.ui.settings_win.window.winfo_exists():
                self.ui.settings_win._sync_from_params()
            if toast_message:
                self.ui.show_toast(toast_message, duration=2200)

        self.ui.root.after(0, refresh_ui)
    
    def _save_params(self) -> None:
        """Sauvegarde les paramètres."""
        if save_parameters(self._params):
            logging.info("Paramètres sauvegardés avec succès.")
        else:
            logging.error("Échec de la sauvegarde des paramètres.")
    
    def _check_updates_async(self) -> None:
        """Vérifie les mises à jour en arrière-plan."""
        def check_task():
            try:
                new_version = check_for_updates()
                if new_version:
                    logging.info(f"Nouvelle version disponible: {new_version}")
                    # Planifier l'affichage du popup sur le thread UI
                    self.ui.root.after(0, lambda: self.ui.show_update_popup(new_version))
                else:
                    logging.info("Application à jour.")
            except Exception as e:
                logging.warning(f"Erreur lors de la vérification des mises à jour: {e}")
        
        # Utiliser le ThreadPoolExecutor de l'UI si disponible
        if hasattr(self.ui, 'executor'):
            self.ui.executor.submit(check_task)
        else:
            Thread(target=check_task, daemon=True).start()
    
    def run(self) -> None:
        """Lance la boucle principale de l'application."""
        logging.info(f"MAIN LOL v{CURRENT_VERSION} démarré.")
        try:
            self.ui.run()
        finally:
            self.cleanup()
    
    def quit_app(self) -> None:
        """Ferme l'application proprement."""
        with self._shutdown_lock:
            if self._shutdown_started:
                return
            self._shutdown_started = True

        logging.info("Fermeture de l'application...")
        try:
            self._save_params()
            if getattr(self, "telegram_service", None):
                self.telegram_service.stop()
            self.ws_manager.stop()
            self.ui.stop()
        finally:
            self.cleanup()
    
    def cleanup(self) -> None:
        """Nettoyage final avant fermeture."""
        if self._cleanup_done:
            return
        self._cleanup_done = True
        remove_lockfile()
        logging.info("Nettoyage terminé.")


def main() -> int:
    if "--overlay-host" in sys.argv:
        from src.ui.overlay_host import main as overlay_main

        return overlay_main(sys.argv[1:])
    if "--stats-overlay" in sys.argv:
        from src.ui.stats_overlay_host import main as overlay_main

        return overlay_main(sys.argv[1:])
    if "--qt-overlay" in sys.argv:
        from src.ui.qt_overlay_host import main as overlay_main

        return overlay_main(sys.argv[1:])
    """Point d'entrée principal."""
    try:
        app = MainLoLApplication()
        app.run()
    except KeyboardInterrupt:
        logging.info("Interruption clavier détectée.")
    except Exception as e:
        logging.critical(f"Erreur fatale: {e}", exc_info=True)
        return 1
    finally:
        remove_lockfile()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
