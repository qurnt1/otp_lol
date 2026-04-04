"""
MAIN LOL - Module Utilitaires
-----------------------------
Fonctions utilitaires: lockfile, mise à jour, DPI, etc.
"""

import os
import sys
import logging
import requests
from typing import Optional
import urllib.parse

import psutil
from packaging.version import InvalidVersion, Version

from .config import LOCKFILE_PATH, GITHUB_RELEASES_API, CURRENT_VERSION


# ───────────────────────────────────────────────────────────────────────────
# HIGH DPI AWARENESS (Windows)
# ───────────────────────────────────────────────────────────────────────────

def enable_high_dpi() -> None:
    """Active la gestion du High DPI sous Windows."""
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass


# ───────────────────────────────────────────────────────────────────────────
# SINGLE INSTANCE (LOCKFILE)
# ───────────────────────────────────────────────────────────────────────────

def check_single_instance() -> bool:
    """
    Vérifie qu'une seule instance de l'application est en cours.
    
    Returns:
        True si cette instance peut continuer, False si une autre existe déjà
    """
    if os.path.exists(LOCKFILE_PATH):
        try:
            with open(LOCKFILE_PATH, 'r') as f:
                pid = int(f.read())
            if pid != os.getpid() and psutil.pid_exists(pid):
                logging.info(f"Instance existante détectée (PID: {pid})")
                return False
        except (ValueError, IOError):
            pass
    
    # Créer/mettre à jour le lockfile
    try:
        with open(LOCKFILE_PATH, 'w') as f:
            f.write(str(os.getpid()))
    except IOError:
        pass
    
    return True


def remove_lockfile() -> None:
    """Supprime le lockfile lors de la fermeture."""
    try:
        if os.path.exists(LOCKFILE_PATH):
            os.remove(LOCKFILE_PATH)
    except IOError:
        pass


# ───────────────────────────────────────────────────────────────────────────
# UPDATE CHECKING (GitHub Releases API)
# ───────────────────────────────────────────────────────────────────────────

def check_for_updates() -> Optional[str]:
    """
    Vérifie les mises à jour via l'API GitHub Releases.
    
    Returns:
        Nouvelle version disponible (str) ou None si à jour
    """
    try:
        logging.info("[Update] Vérification via GitHub Releases API...")
        
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "MainLoL-UpdateChecker"
        }
        
        resp = requests.get(GITHUB_RELEASES_API, headers=headers, timeout=10)
        
        if resp.status_code == 200:
            data = resp.json()
            tag_name = data.get("tag_name", "")
            
            remote_version = normalize_version(tag_name)
            
            logging.info(f"[Update] Version en ligne: {remote_version}, locale: {CURRENT_VERSION}")
            
            if remote_version and is_newer_version(remote_version, CURRENT_VERSION):
                return remote_version
        
        elif resp.status_code == 404:
            logging.warning("[Update] Aucune release trouvée sur le repo")
        else:
            logging.warning(f"[Update] Réponse API: {resp.status_code}")
            
    except requests.RequestException as e:
        logging.warning(f"[Update] Erreur réseau: {e}")
    except Exception as e:
        logging.error(f"[Update] Erreur inattendue: {e}")
    
    return None


def normalize_version(version: str) -> str:
    """Normalise une version de type v6.1 vers 6.1."""
    return (version or "").strip().lstrip("vV")


def parse_version(version: str) -> Version:
    """Parse une version en objet sémantique comparable."""
    normalized = normalize_version(version)
    if not normalized:
        raise InvalidVersion("Version vide")
    return Version(normalized)


def is_newer_version(remote_version: str, current_version: str) -> bool:
    """Retourne True seulement si la version distante est strictement plus récente."""
    try:
        return parse_version(remote_version) > parse_version(current_version)
    except InvalidVersion as e:
        logging.warning(f"[Update] Version invalide ignorée: {e}")
        return False


# ───────────────────────────────────────────────────────────────────────────
# URL UTILITIES
# ───────────────────────────────────────────────────────────────────────────

def build_opgg_url(region: str, riot_id: str) -> str:
    """
    Construit l'URL OP.GG pour un joueur.
    
    Args:
        region: Région (euw, na, etc.)
        riot_id: Riot ID (GameName#Tag)
        
    Returns:
        URL OP.GG complète
    """
    url_name = _normalize_riot_id_for_url(riot_id)
    
    return f"https://www.op.gg/lol/summoners/{region}/{urllib.parse.quote(url_name)}"


def build_porofessor_url(region: str, riot_id: str) -> str:
    """
    Construit l'URL Porofessor pour un joueur.
    
    Args:
        region: Région (euw, na, etc.)
        riot_id: Riot ID (GameName#Tag)
        
    Returns:
        URL Porofessor complète
    """
    
    url_name = _normalize_riot_id_for_url(riot_id)
    
    return f"https://porofessor.gg/fr/live/{region}/{urllib.parse.quote(url_name)}"


def _normalize_riot_id_for_url(riot_id: str) -> str:
    """Convertit GameName#Tag en GameName-Tag pour les URLs externes."""
    riot_id = riot_id or ""
    if "#" in riot_id:
        left, right = riot_id.split("#", 1)
        if left and right:
            return f"{left}-{right}"
    return riot_id
