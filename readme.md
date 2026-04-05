# MAIN LOL

Assistant desktop Windows pour League of Legends, ecrit en Python.

`MAIN LOL` automatise plusieurs actions autour du client LoL pour gagner du temps pendant la file, la selection des champions et l'apres-partie, tout en gardant une interface simple a configurer.

Version actuelle du projet: `6.1`

## Sommaire

- [Presentation](#presentation)
- [Fonctionnalites](#fonctionnalites)
- [Captures D Ecran](#captures-d-ecran)
- [Technologies](#technologies)
- [Prerequis](#prerequis)
- [Installation Depuis Le Code Source](#installation-depuis-le-code-source)
- [Lancement](#lancement)
- [Build Executable](#build-executable)
- [Configuration Et Fichiers Utilises](#configuration-et-fichiers-utilises)
- [Utilisation](#utilisation)
- [Raccourcis](#raccourcis)
- [Architecture Du Projet](#architecture-du-projet)
- [Tests Et Verification](#tests-et-verification)
- [Depannage](#depannage)
- [Roadmap Possible](#roadmap-possible)

## Presentation

Le but de l'application est de servir d'assistant local pour le client League of Legends.

Elle se connecte au client LoL via le LCU, detecte les phases importantes, puis execute automatiquement certaines actions en fonction de ta configuration:

- accepter une partie automatiquement
- preselectionner ou lock un champion selon un ordre de priorite
- bannir un champion choisi
- appliquer des sorts d'invocateur
- relancer une partie apres la fin de game
- ouvrir rapidement des pages externes comme `OP.GG` et `Porofessor`

L'application est concue pour fonctionner comme un outil desktop leger:

- interface graphique Tkinter via `ttkbootstrap`
- gestion des assets en local
- systray
- raccourcis clavier
- cache local pour certaines donnees Data Dragon

## Fonctionnalites

### Automatisation de la file et du champion select

- `Auto-Accept`
  Accepte automatiquement le ready-check lorsqu'une partie est trouvee.
- `Auto-Pick`
  Tente de pick `Pick 1`, puis `Pick 2`, puis `Pick 3` si le champion precedent n'est pas disponible.
- `Pre-hover`
  L'application peut preselectionner ton champion principal avant le lock.
- `Auto-Ban`
  Bannit automatiquement le champion configure.
- `Auto-Spells`
  Applique les sorts selectionnes une fois le pick verrouille.

### Automatisation post-game

- `Auto Play Again`
  Tente de retourner automatiquement au lobby apres la fin de partie.

### Confort d'utilisation

- detection automatique du compte
- detection automatique de la region du client
- liens rapides `OP.GG` et `Porofessor`
- masquage de la fenetre dans le systray
- raccourcis clavier globaux
- cache des icones champions et sorts
- logs dans `%APPDATA%`

### Comportements de securite / robustesse

Le projet contient maintenant plusieurs garde-fous utiles:

- separation entre valeurs `manual_*` et `auto_detected_*`
- fermeture plus propre de l'application
- fallback visuel si le systray ou les hotkeys ne sont pas disponibles
- comparaison semantique des versions pour la detection de mises a jour

## Captures D Ecran

### Fenetre principale


```md
![Fenetre principale](./docs/images/main-window.png)
```

### Fenetre de parametres

```md
![Parametres](./docs/images/settings-window.png)
```

### Pendant un champion select

```md
![Champion select](./docs/images/champ-select.png)
```

## Technologies

Le projet utilise principalement:

- `Python 3.13`
- `ttkbootstrap` pour l'interface
- `tkinter` pour la base UI
- `lcu-driver` pour dialoguer avec le client League of Legends
- `Pillow` pour les images
- `pygame` pour les effets sonores
- `pystray` pour le systray
- `keyboard` pour les raccourcis globaux
- `requests` pour Data Dragon et GitHub

## Prerequis

Avant de lancer le projet depuis le code source, il faut:

- Windows
- Python `3.13`
- `pip`
- le client League of Legends installe

## Installation Depuis Le Code Source

```bash
git clone https://github.com/qurnt1/main_lol_2.git
cd MAIN_LOL
pip install -r requirements.txt
```

## Lancement

Pour lancer l'application en local:

```bash
python launcher.py
```

Au demarrage, l'application:

1. verifie qu'une seule instance tourne
2. charge les parametres locaux
3. prepare les dossiers de cache
4. lance l'interface
5. initialise la connexion au client LoL
6. charge Data Dragon en arriere-plan

## Build Executable

Le projet fournit un script de build PyInstaller:

```bash
python install_exe.py
```

Ce script genere un executable portable:

- nom du binaire: `OTP LOL.exe`
- emplacement final: racine du projet

Le script gere egalement:

- l'inclusion des assets
- l'inclusion du package `src`
- plusieurs imports caches pour PyInstaller
- le nettoyage des dossiers temporaires de build

## Configuration Et Fichiers Utilises

### Fichiers utilisateur

- Parametres:
  `%APPDATA%\MainLoL\parameters.json`
- Logs:
  `%APPDATA%\MainLoL\app_debug.log`

### Cache local

- Cache champions:
  `%TEMP%\mainlol_ddragon_champions.json`
- Cache icones champions:
  `%TEMP%\mainlol_icons\`
- Cache icones sorts:
  `%TEMP%\mainlol_spells\`

### Parametres principaux

L'application stocke notamment:

- les toggles d'automatisation
- les picks `1 / 2 / 3`
- le ban configure
- les sorts d'invocateur
- le mode de detection automatique
- les valeurs manuelles du compte et de la region
- les valeurs auto-detectees du compte et de la region

## Utilisation

### Premier lancement

Au premier lancement, tu peux:

1. ouvrir les parametres via l'icone engrenage
2. choisir tes picks prioritaires
3. choisir ton ban
4. configurer les sorts
5. decider si tu veux la detection automatique du compte
6. activer ou non le retour automatique au lobby

### Detection automatique ou mode manuel

L'application distingue maintenant:

- les valeurs manuelles
- les valeurs detectees automatiquement par le client LoL

Cela evite qu'une detection auto ecrase ton compte ou ta region manuelle.

### Comportement pendant la partie

Quand le client est detecte:

- l'indicateur de connexion passe au vert
- l'application peut se masquer automatiquement
- elle suit les changements de phase du client

En champion select:

- elle detecte tes actions
- tente le hover
- essaie de lock le meilleur pick disponible selon l'ordre configure
- applique les sorts si l'option est active

Apres la partie:

- elle peut tenter `Play Again` automatiquement si l'option est active

## Raccourcis

- `Alt + P`
  Ouvre la page `Porofessor`
- `Alt + C`
  Affiche ou masque la fenetre principale

## Architecture Du Projet

```text
MAIN_LOL/
|-- launcher.py
|-- install_exe.py
|-- requirements.txt
|-- readme.md
|-- src/
|   |-- __init__.py
|   |-- config.py
|   |-- core.py
|   |-- ui.py
|   `-- utils.py
|-- config/
|   |-- son.wav
|   `-- images/
`-- tests/
    |-- test_config.py
    |-- test_core_champ_select.py
    `-- test_utils.py
```

### Role des fichiers principaux

- `launcher.py`
  Point d'entree principal et orchestration du cycle de vie.
- `src/config.py`
  Constantes, chemins, version, parametres par defaut, gestion des fichiers de config.
- `src/core.py`
  Logique metier, Data Dragon, WebSocket / LCU, automatisations de jeu.
- `src/ui.py`
  Interface graphique, systray, toasts, raccourcis et gestion des interactions utilisateur.
- `src/utils.py`
  Fonctions utilitaires: lockfile, URLs externes, verification de mise a jour, DPI.
- `install_exe.py`
  Build Windows via PyInstaller.

## Tests Et Verification

Le projet contient des tests de non-regression sur:

- la gestion de configuration
- les utilitaires
- certaines branches de la logique de champion select

Pour lancer les tests:

```bash
python -m unittest discover -s tests -v
```

Pour verifier rapidement que le code compile:

```bash
python -m compileall launcher.py src install_exe.py tests
```

## Depannage

### L'application ne detecte pas LoL

Verifie que:

- le client League of Legends est lance
- `lcu-driver` est bien installe
- l'application tourne sur la meme machine que le client LoL

### Le systray ou les hotkeys ne fonctionnent pas

L'application dispose maintenant d'un fallback:

- un bouton `Quitter` reste visible si le systray ou les raccourcis ne sont pas disponibles

### Les images ou les icones ne se chargent pas

Verifie la presence du dossier:

```text
config/
`-- images/
```

### Les logs

En cas de souci, le premier fichier a consulter est:

```text
%APPDATA%\MainLoL\app_debug.log
```

## Roadmap Possible

Quelques idees d'evolution pour la suite:

- profils par role
- profils par mode de jeu
- historique des actions auto
- meilleures captures d'ecran dans le README
- page de presentation plus visuelle
- import / export de profils

## Auteur

Projet maintenu par `Qurnt1`.
