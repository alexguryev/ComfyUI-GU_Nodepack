# GU_Nodepack (C) Alexander Guryev, 2026 | https://alexguryev.com

from .nodes import *
import folder_paths

folder_paths.add_model_folder_path("customfonts", os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts"))

WEB_DIRECTORY = "./web"
__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
MANIFEST = {
    "name": "GU_Nodepack",
    "version": (2, 6, 3), # maj:arch.changes . min:new functionality . tuning:fixes,tuning
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
