# GU_Nodepack (C) Alexander Guryev, 2026 | https://alexguryev.com

try:
    from importlib.metadata import version as _pkg_ver, PackageNotFoundError as _PkgNF
    _GU_FUNCLIB_MIN = "1.8.5"
    try:
        _inst = _pkg_ver("gu-funclib")
        if tuple(int(x) for x in _inst.split(".")) < tuple(int(x) for x in _GU_FUNCLIB_MIN.split(".")):
            print(f"\033[93m[GU_Nodepack] WARNING: gu-funclib {_inst} is outdated (need >={_GU_FUNCLIB_MIN}). Run: pip install --upgrade gu-funclib\033[0m")
    except _PkgNF:
        print(f"\033[91m[GU_Nodepack] ERROR: gu-funclib is not installed. Run: pip install gu-funclib>={_GU_FUNCLIB_MIN}\033[0m")
except ImportError:
    pass

from .nodes import *
import folder_paths

folder_paths.add_model_folder_path("customfonts", os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts"))

WEB_DIRECTORY = "./web"
__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
MANIFEST = {
    "name": "GU_Nodepack",
    "version": (2, 6, 5), # maj:arch.changes . min:new functionality . tuning:fixes,tuning
    "author": "Alexander Guryev",
    "project": "https://github.com/alexguryev/ComfyUI-GU_Nodepack",
    "description": "Several utility nodes for ComfyUI: LoRA management, image annotation, project organization, sampling utilities, system integration.",
}
__version__ = f"{MANIFEST['version'][0]}.{MANIFEST['version'][1]}.{MANIFEST['version'][2]}"
ascii_art = """\033[94m\n
   _____ _    _                   _                       _
  / ____| |  | |                 | |                     | |
 | |  __| |  | |  _ __   ___   __| | ___ _ __   __ _  ___| | __
 | | |_ | |  | | | '_ \\ / _ \\ / _` |/ _ \\ '_ \\ / _` |/ __| |/ /
 | |__| | |__| | | | | | (_) | (_| |  __/ |_) | (_| | (__|   <
  \\_____|\\____/  |_| |_|\\___/ \\__,_|\\___| .__/ \\__,_|\\___|_|\\_\\
                                        | |
                                        |_|
 """
print(ascii_art)
print(f"           V {__version__}\n\033[0m")
