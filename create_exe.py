"""
FILE NAME: create_exe.py
GLOBAL PURPOSE:
- Build the Windows executable distribution with PyInstaller.
- Make packaging rules explicit for assets, hidden imports, and entry-point resolution.
- Produce a single executable, optionally create a desktop shortcut, and clean temporary artifacts.

KEY FUNCTIONS:
- _prompt_yes_no: Normalize an interactive yes or no answer from the console.
- _create_desktop_shortcut: Create a Windows desktop shortcut for the packaged executable.
- main: Prepare build arguments, run PyInstaller, move the final executable, and clean generated files.

AUDIENCE & LOGIC:
Why:
This script keeps release packaging reproducible and documents why the build includes assets and modules explicitly instead of relying only on auto-detection.
For whom:
Developers or maintainers who build the Windows executable from source.

DEPENDENCIES:
Used by:
- Executed manually as a build script.
Uses:
- Standard library: os, shutil, subprocess, sys
- Local config exports from src.config
- External tool: PyInstaller
"""

import os
import subprocess
import sys
import shutil

from src.config import APP_BUILD_NAME, APP_NAME, CURRENT_VERSION


def _prompt_yes_no(prompt: str, default: bool = True) -> bool:
    """Return a normalized boolean answer for an interactive console prompt."""
    yes_values = {"y", "yes", "o", "oui"}
    no_values = {"n", "no", "non"}
    suffix = "[Y/n]" if default else "[y/N]"

    while True:
        raw = input(f"{prompt} {suffix} ").strip().lower()
        if not raw:
            return default
        if raw in yes_values:
            return True
        if raw in no_values:
            return False
        print("Please answer with yes/no or oui/non.")


def _create_desktop_shortcut(target_exe: str, app_name: str) -> bool:
    """Create a desktop shortcut for the packaged executable on Windows."""
    powershell = shutil.which("powershell") or shutil.which("powershell.exe")
    if not powershell:
        print("⚠️  PowerShell not found. Desktop shortcut skipped.")
        return False

    target_exe = os.path.abspath(target_exe)
    working_dir = os.path.dirname(target_exe)
    shortcut_name = f"{app_name}.lnk"

    ps_script = f"""
$desktop = [Environment]::GetFolderPath('Desktop')
if (-not $desktop) {{ throw 'Desktop path not found.' }}
$shortcutPath = Join-Path $desktop '{shortcut_name}'
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = '{target_exe}'
$shortcut.WorkingDirectory = '{working_dir}'
$shortcut.IconLocation = '{target_exe},0'
$shortcut.Save()
"""

    try:
        subprocess.run(
            [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
            check=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        print(f"   ✓ Desktop shortcut created for {app_name}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"   ⚠️  Desktop shortcut creation failed: {e}")
        return False

def main():
    """Run the end-to-end executable build workflow for the current project root."""
    print("=" * 60)
    print(f"   {APP_NAME} - Script de Creation EXE (v{CURRENT_VERSION})")
    print("   Architecture Modulaire (src/)")
    print("=" * 60)

    create_shortcut = _prompt_yes_no("Create a desktop shortcut after build?", default=True)
    
    # Resolve the repository root from the script location so every relative
    # build path stays stable no matter where the command is launched from.
    try:
        script_path = os.path.abspath(__file__)
    except NameError:
        script_path = os.path.abspath(sys.argv[0])
        
    root_dir = os.path.dirname(script_path)
    os.chdir(root_dir)

    # Keep packaging rules in one place so PyInstaller behavior stays predictable
    # across local environments and future refactors.
    raw_args = [
        '--onefile',      # Produce one portable executable.
        '--windowed',     # Hide the extra console window for the desktop app.
        '--noconfirm',    # Allow rebuilds without an extra prompt.
        '--name', APP_BUILD_NAME,
        '--icon', r'.\config\images\app\garen.ico',
        
        # Ship runtime assets explicitly because they are loaded from disk at runtime.
        '--add-data', r'.\config;config',
        
        # Include the source tree as data as an extra safety net for modules and
        # resources that are resolved dynamically at runtime.
        '--add-data', r'.\src;src',
        
        # ttkbootstrap bundles theme assets that are easier to keep intact via collect-all.
        '--collect-all', 'ttkbootstrap',
        
        # Hidden imports document packaging assumptions for modules that may be
        # missed when imports are optional, indirect, or environment-dependent.
        '--hidden-import=src',
        '--hidden-import=src.config',
        '--hidden-import=src.core',
        '--hidden-import=src.ui',
        
        # Third-party modules referenced through dynamic code paths.
        '--hidden-import=keyboard',
        '--hidden-import=pygame',
        '--hidden-import=pygame.mixer',
        '--hidden-import=pygame.sndarray',
        '--hidden-import=psutil',
        '--hidden-import=urllib3',
        '--hidden-import=pystray',
        '--hidden-import=PIL.Image',
        '--hidden-import=PIL.ImageTk',
        '--hidden-import=PIL.ImageEnhance',
        '--hidden-import=lcu_driver',
        '--hidden-import=packaging',
        '--hidden-import=requests',
        
        # Application entry point.
        'launcher.py'
    ]
    
    # Convert file-based options to absolute paths before invoking PyInstaller.
    # This avoids failures caused by the current working directory.
    processed_args = []
    app_name = None 
    arg_iter = iter(raw_args)
    
    for arg in arg_iter:
        if arg == '--add-data':
            try:
                value = next(arg_iter) 
                parts = value.split(';')
                if len(parts) >= 2:
                    src_path = parts[0]
                    dest_path = parts[1]
                    abs_src_path = os.path.abspath(src_path)
                    processed_args.append(arg)
                    processed_args.append(f"{abs_src_path}{os.pathsep}{dest_path}")
                else:
                    processed_args.extend([arg, value])
            except StopIteration:
                processed_args.append(arg) 
        elif arg == '--icon':
            icon_path = next(arg_iter)
            abs_icon = os.path.abspath(icon_path)
            if os.path.exists(abs_icon):
                processed_args.extend([arg, abs_icon])
            else:
                print(f"⚠️  Icône non trouvée: {abs_icon}")
        elif arg == '--name':
            val = next(arg_iter)
            app_name = val
            processed_args.extend([arg, val])
        elif arg.endswith('.py'):
            processed_args.append(os.path.abspath(arg))
            if not app_name:
                app_name = os.path.splitext(os.path.basename(arg))[0]
        else:
            processed_args.append(arg)

    dist_path = os.path.join(root_dir, 'dist')
    build_path = os.path.join(root_dir, 'build')
    
    # Use dedicated dist/build/spec paths so the script can clean its own
    # artifacts without affecting unrelated files in the repository.
    py_command = [sys.executable, "-m", "PyInstaller"] + processed_args
    py_command.extend([
        "--clean", 
        f"--distpath={dist_path}", 
        f"--workpath={build_path}", 
        f"--specpath={root_dir}"
    ])

    print("\n📦 Compilation en cours...")
    print("   (Cela peut prendre quelques minutes)\n")
    
    try:
        subprocess.run(py_command, check=True, text=True, encoding='utf-8', errors='replace')
    except subprocess.CalledProcessError as e:
        print(f"\n❌ ERREUR COMPILATION: {e}")
        sys.exit(1)

    # Move the final executable to the repository root so the output path stays
    # stable for release usage and shortcut creation.
    exe_name = f"{app_name}.exe"
    source = os.path.join(dist_path, exe_name)
    target = os.path.join(root_dir, exe_name)
    
    print(f"\n📁 Déplacement de l'exécutable...")
    
    if os.path.exists(source):
        if os.path.exists(target):
            os.remove(target)
        
        shutil.move(source, target)
        print(f"\n✅ SUCCÈS : {target}")
        print(f"   Taille : {os.path.getsize(target) / (1024*1024):.1f} Mo")

        if create_shortcut:
            print("\n🔗 Creating desktop shortcut...")
            _create_desktop_shortcut(target, APP_BUILD_NAME)
        else:
            print("\nℹ️  Desktop shortcut skipped by user choice.")
        
        # Clean generated folders and legacy build outputs so repeated runs do
        # not leave stale artifacts that could confuse future packaging steps.
        print("\n🧹 Nettoyage des fichiers temporaires...")
        try:
            if os.path.exists(build_path):
                shutil.rmtree(build_path)
            if os.path.exists(dist_path):
                shutil.rmtree(dist_path)
            spec_file = os.path.join(root_dir, f"{app_name}.spec")
            if os.path.exists(spec_file):
                os.remove(spec_file)
            # Remove the old one-dir folder if a previous build left it behind.
            old_dir = os.path.join(root_dir, app_name)
            if os.path.exists(old_dir):
                shutil.rmtree(old_dir)
            print("   ✓ Nettoyage terminé")
        except Exception as e:
            print(f"   ⚠️ Erreur nettoyage: {e}")
    else:
        print(f"\n❌ Erreur : EXE non trouvé à {source}")
        sys.exit(1)
    
    print("\n" + "=" * 60)
    print("   COMPILATION TERMINÉE")
    print("=" * 60)


if __name__ == "__main__":
    main()
