import os
import json
import base64
import urllib3
import logging
import traceback
from pathlib import Path
from datetime import datetime

try:
    import requests
except ImportError:
    raise SystemExit("Le module requests est requis: pip install requests")

try:
    from http.client import HTTPConnection
except ImportError:
    from httplib import HTTPConnection


# =========================
# CONFIG LOGS
# =========================
VERBOSE_HTTP = False   # True = logs très bavards de requests/urllib3
LOG_LOCKFILE_SCAN = True
TIMEOUT = 10

if VERBOSE_HTTP:
    HTTPConnection.debuglevel = 1
    logging.basicConfig(level=logging.DEBUG)
    logging.getLogger().setLevel(logging.DEBUG)
    urllib3_logger = logging.getLogger("urllib3")
    urllib3_logger.setLevel(logging.DEBUG)
    urllib3_logger.propagate = True

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


DEFAULT_CANDIDATES = [
    r"C:\Riot Games\League of Legends\lockfile",
    r"C:\Riot Games\League of Legends\Game\lockfile",
]

GAREN_ID = 86


def log(msg, level="INFO"):
    now = datetime.now().strftime("%H:%M:%S")
    print(f"[{now}] [{level}] {msg}")


def safe_json(response):
    try:
        return response.json()
    except Exception:
        return response.text


def find_lockfile():
    log("Début recherche du lockfile")

    env_path = os.environ.get("LEAGUE_LOCKFILE")
    if env_path:
        log(f"Variable LEAGUE_LOCKFILE détectée: {env_path}")
        p = Path(env_path)
        if p.exists():
            log(f"Lockfile trouvé via variable d'environnement: {p}", "SUCCESS")
            return p
        else:
            log("Le chemin LEAGUE_LOCKFILE n'existe pas", "WARNING")

    for candidate in DEFAULT_CANDIDATES:
        log(f"Test chemin candidat: {candidate}")
        p = Path(candidate)
        if p.exists():
            log(f"Lockfile trouvé via chemin candidat: {p}", "SUCCESS")
            return p

    roots = [Path("C:/")]
    home_drive = getattr(Path.home(), "drive", "")
    if home_drive:
        roots.append(Path(home_drive + "/"))

    for root in roots:
        if not root:
            continue
        log(f"Scan récursif de: {root}", "DEBUG")
        try:
            for p in root.rglob("lockfile"):
                if LOG_LOCKFILE_SCAN:
                    log(f"Lockfile potentiel détecté: {p}", "DEBUG")
                if "League of Legends" in str(p):
                    log(f"Lockfile LoL trouvé pendant le scan: {p}", "SUCCESS")
                    return p
        except Exception as e:
            log(f"Erreur pendant le scan de {root}: {e}", "ERROR")

    log("Aucun lockfile trouvé", "ERROR")
    return None


def read_lockfile(path: Path):
    log(f"Lecture du lockfile: {path}")
    content = path.read_text(encoding="utf-8").strip()
    log(f"Contenu brut lockfile: {content}", "DEBUG")

    parts = content.split(":")
    if len(parts) != 5:
        raise ValueError(f"Format lockfile inattendu: {content}")

    process_name, pid, port, password, protocol = parts

    lock = {
        "process_name": process_name,
        "pid": pid,
        "port": port,
        "password": password,
        "protocol": protocol,
    }

    log(
        f"Lockfile parsé: process={process_name}, pid={pid}, port={port}, protocol={protocol}",
        "SUCCESS"
    )
    return lock


def lcu_get(lock, endpoint):
    auth = base64.b64encode(f"riot:{lock['password']}".encode()).decode()
    url = f"{lock['protocol']}://127.0.0.1:{lock['port']}{endpoint}"
    headers = {"Authorization": f"Basic {auth}"}

    log(f"GET {url}")
    log(f"Headers: Authorization=Basic ***masqué***", "DEBUG")

    try:
        r = requests.get(url, headers=headers, verify=False, timeout=TIMEOUT)
        log(f"Réponse reçue: status={r.status_code} content-type={r.headers.get('content-type')}", "SUCCESS")
        body = safe_json(r)

        if isinstance(body, (dict, list)):
            preview = json.dumps(body, ensure_ascii=False)[:500]
        else:
            preview = str(body)[:500]

        log(f"Aperçu réponse: {preview}", "DEBUG")

        return {
            "url": url,
            "status_code": r.status_code,
            "headers": dict(r.headers),
            "json": body,
        }

    except requests.exceptions.ConnectTimeout:
        log(f"Timeout de connexion sur {url}", "ERROR")
        raise
    except requests.exceptions.ReadTimeout:
        log(f"Timeout de lecture sur {url}", "ERROR")
        raise
    except requests.exceptions.ConnectionError as e:
        log(f"Erreur de connexion sur {url}: {e}", "ERROR")
        raise
    except requests.exceptions.RequestException as e:
        log(f"Erreur HTTP requests sur {url}: {e}", "ERROR")
        raise


def main():
    log("=== DÉMARRAGE TEST LCU GAREN RUNES ===")

    try:
        lockfile = find_lockfile()
        if not lockfile:
            result = {
                "ok": False,
                "error": "lockfile introuvable",
                "hint": "Lance le client League of Legends puis réessaie, ou définis la variable d'environnement LEAGUE_LOCKFILE.",
            }
            log("Fin du programme: lockfile introuvable", "ERROR")
            print(json.dumps(result, indent=2, ensure_ascii=False))
            return

        lock = read_lockfile(lockfile)

        result = {
            "ok": True,
            "lockfile": str(lockfile),
            "process_name": lock["process_name"],
            "pid": lock["pid"],
            "port": lock["port"],
            "protocol": lock["protocol"],
            "requests": {}
        }

        endpoints = {
            "session": "/lol-champ-select/v1/session",
            "current_champion": "/lol-champ-select/v1/current-champion",
            "recommended_pages_position_garen": f"/lol-perks/v1/recommended-pages-position/champion/{GAREN_ID}",
            "recommended_pages_garen": f"/lol-perks/v1/recommended-pages/champion/{GAREN_ID}",
            "perk_pages": "/lol-perks/v1/pages",
        }

        log(f"{len(endpoints)} endpoints à tester")

        for key, endpoint in endpoints.items():
            log(f"--- Test endpoint: {key} ---")
            try:
                result["requests"][key] = lcu_get(lock, endpoint)
            except Exception as e:
                result["requests"][key] = {
                    "error": str(e),
                    "endpoint": endpoint,
                    "traceback": traceback.format_exc(),
                }

        log("=== FIN TEST LCU ===", "SUCCESS")
        print(json.dumps(result, indent=2, ensure_ascii=False))

    except Exception as e:
        log(f"Erreur fatale: {e}", "ERROR")
        print(json.dumps({
            "ok": False,
            "fatal_error": str(e),
            "traceback": traceback.format_exc()
        }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()