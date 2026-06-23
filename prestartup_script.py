# GU_Nodepack (C) Alexander Guryev, 2026 | https://alexguryev.com

import folder_paths
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

LoraList = FillLoraList()
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
# LoRA list is refreshed via INPUT_TYPES() on each /object_info request (browser reload).
