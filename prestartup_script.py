# GU_Nodepack (C) Alexander Guryev, 2026 | https://alexguryev.com

from aiohttp import web
import folder_paths
import inspect
import os
import threading

def IsModelFile(s):
    ext = os.path.splitext(os.path.basename(s))[1]
    return ext in [".safetensors", ".sft", ".ckpt", ".bin"]

def GetLoraFolder():
    #os.path.join(folder_paths.base_path, "models\\loras")
    # ??????????????????    use both system and stabmatrix folders ????????????????????
    try:
        s = folder_paths.folder_names_and_paths[folder_paths.map_legacy("loras")][0][1]  # stability folder
    except (KeyError, IndexError, AttributeError):
        s = folder_paths.folder_names_and_paths["loras"][0][0]  # comfy default folder
    return s

LoraFolder = GetLoraFolder()

def GetLoraRoot():
    global LoraFolder
    return os.path.dirname(LoraFolder)

def FillLoraList(root=None):
    global LoraFolder
    arr = []

    if root is None: #no root folder specified, use default
        loras, folders_all = folder_paths.recursive_search(LoraFolder, excluded_dir_names=[".git"])
    else:
        loras, folders_all = folder_paths.recursive_search(root, excluded_dir_names=[".git"])

    for x in loras:
        if IsModelFile(x):
            arr.append(x)

    arr = sorted(arr, key=lambda item: item.lower(), reverse=False)
    if root is None:
        arr.insert(0, "None")
    return arr

_StateLock = threading.RLock()

LoraList = FillLoraList() # init in case of websocket intercept failed
def GetLoraList():
    global LoraList
    return LoraList

SeedFileLoaded = False
def GetSeedFileLoaded():
    global SeedFileLoaded
    return SeedFileLoaded

def SetSeedFileLoaded(s):
    global SeedFileLoaded
    with _StateLock:
        SeedFileLoaded = s
        return SeedFileLoaded

def on_reload(): # file lists refill upon ComfyUI browser page refresh
    global LoraList, SeedFileLoaded
    new_list = FillLoraList()  # slow I/O, keep outside the lock
    with _StateLock:
        LoraList = new_list
        SeedFileLoaded = False

# #########################################################################################

# intercept UI enable (WebSocket) — defensive patching with signature check
PreOK = False
orig_prepare = None

try:
    orig_prepare = web.WebSocketResponse.prepare
    # verify patched method has >=2 params (arity check). Name of the 'self' param varies across
    # aiohttp versions (seen 'self' and 'ws'), so we do not check names — only that we can call
    # it as prepare(instance, request), which requires 2+ positional params.
    sig = inspect.signature(orig_prepare)
    actual_params = list(sig.parameters.keys())
    if len(actual_params) >= 2:
        PreOK = True
    else:
        try:
            import aiohttp
            ver = aiohttp.__version__
        except Exception:
            ver = "unknown"
        print(f"[GU_Nodepack] WebSocket patch skipped: prepare() arity {len(actual_params)} < 2 (aiohttp {ver}, params {actual_params})")
except Exception as e:
    print(f"[GU_Nodepack] WebSocket patch skipped: {type(e).__name__}: {e}")

async def patched_prepare(ws, request):
    result = await orig_prepare(ws, request)
    try:
        on_reload()
    except Exception as e:
        print(f"[GU_Nodepack] on_reload hook failed (passing through): {type(e).__name__}: {e}")
    return result

if PreOK:
    try:
        web.WebSocketResponse.prepare = patched_prepare
    except (AttributeError, TypeError) as e:
        print(f"[GU_Nodepack] WebSocket patch install failed: {type(e).__name__}: {e}")
        PreOK = False
