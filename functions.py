# GU_Nodepack (C) Alexander Guryev, 2026 | https://alexguryev.com

import comfy.sd
import comfy.utils
import folder_paths
import importlib.util
import json
import math
import numpy as np
import os
from PIL import ImageDraw, ImageFont, Image
import platform
import psutil
import re
import requests
import threading
import torch

from .gu_funclib import make_unique_filename, get_datetime_str, calc_SHA256, strlist_to_str
from .prestartup_script import *

_StateLock = threading.RLock()

_SystemInfoCache = None
_SHA256Cache = {} # {filepath: (mtime, hash)}

NodesWF = None
NodesPrm = None
GetterReg = { # lists of node ids for specific node class
    "G_GetMediaInName": [],
    "G_GetModelName": [],
    "G_TextEdit": [],
}
GetterStart = ""

# ###############################################################################################
class AnyType(str):
    def __ne__(self, __value: object) -> bool:
        return False

# ###############################################################################################
def GetSystemInfo():
    global _SystemInfoCache
    with _StateLock:
        if _SystemInfoCache is not None:
            return _SystemInfoCache

        system_info = {
            'type': None,
            'gpu': None,
            'torch': None,
            'vram' : None,
            'cpu': None,
            'ram' : None,
        }

        if importlib.util.find_spec('torch'):
            if torch.cuda.is_available():
                system_info['gpu'] = torch.cuda.get_device_properties('cuda').name
                system_info['type'] = torch.device('cuda')
                system_info['torch'] = torch.__version__
                vram = math.ceil(torch.cuda.get_device_properties('cuda').total_memory / (1024**3)) # get Gb
                system_info['vram'] = str(vram) + " Gb"
            elif torch.backends.mps.is_available():
                system_info['type'] = torch.device('mps')
            else:
                system_info['type'] = torch.device('cpu')

        system_info['cpu'] = platform.processor()
        ram = math.ceil(psutil.virtual_memory().total / (1024**3)) # get Gb
        system_info['ram'] = str(ram) + " Gb"

        _SystemInfoCache = system_info
        return system_info

# ###############################################################################################
def DebugSavePromptWorkflow(prompt, promptname, wf, wfname):
    with open(make_unique_filename(f"{folder_paths.output_directory}/{promptname}.json"), "w") as file:
        file.write(json.dumps(prompt, indent=4))

    with open(make_unique_filename(f"{folder_paths.output_directory}/{wfname}.json"), "w") as file:
        file.write(json.dumps(wf, indent=4))

# ###############################################################################################
def GetLoraSubfolders():
    cut = len(GetLoraRoot()) + 1
    files, folders_all = folder_paths.recursive_search(GetLoraFolder(), excluded_dir_names=[".git"])
    out_dirs = []
    for x in folders_all:
        out_dirs.append(x[cut:])
    return sorted(out_dirs)

# ###############################################################################################
def BypassReroutes(wfnodes, targlink_wf, level=1): # recursive skip reroute nodes / top-call without specify level
    o_match = False
    for ntarg_wf in wfnodes:
        #print(f"level = {level}     id = {ntarg_wf['id']}     class = {ntarg_wf['type']}")
        if "outputs" in ntarg_wf:
            #print(f"{ntarg_wf["outputs"]}\n")
            for o in ntarg_wf["outputs"]:  # check output link match
                if "links" in o:
                    if isinstance(o["links"], list):
                        if targlink_wf in o["links"]: # found link number!
                            if "rerout" in ntarg_wf["type"].lower(): # current node is reroute
                                #print("/////// REROUTE found")
                                lnk_wf_next = ntarg_wf["inputs"][0]["link"] # new link to scan
                                #print(f"        wf link NEXT = {lnk_wf_next}")
                                ntarg_wf, o_match = BypassReroutes(wfnodes, lnk_wf_next, level+1) # go deeper
                            else: # not a reroute, breaking
                                o_match = True
                                #print("approved incoming node!")
                            break
        if o_match: break

    #print("\n")
    return ntarg_wf, o_match

# ###############################################################################################
def GetIncomingNodeWidContent(extra_pnginfo, prompt, thisclass, sought_widget=None): # get list of widget values from incoming node / sought_widget = search in self
    global NodesWF
    global NodesPrm
    global GetterReg
    global GetterStart

    with _StateLock:
        NodesWF = extra_pnginfo["workflow"]["nodes"] # always update, micro-changes in "widgets_values" are possible!
        # check new run: if PROMPT differs => this is a new run, clear all registry and update global prompt
        if (NodesPrm is None) or (NodesPrm != prompt):
            #print("::: new run detected")
            NodesPrm = prompt
            GetterStart = get_datetime_str() # start time string
            for k in GetterReg.keys():
                GetterReg[k].clear() # erase previous node ids for all node classes

    #DebugSavePromptWorkflow(NodesPrm, f"getter_{GetterStart}_prompt", NodesWF, f"getter_{GetterStart}_nodeswf")
    #print(json.dumps(GetterReg, indent=4))

    targ_wid_data = None
    if sought_widget is None:
        for nsrc_wf in NodesWF:
            nsrc_id = nsrc_wf["id"]
            #print(f".......checking {nsrc_id}")
            if nsrc_id in GetterReg[thisclass]: # skip registered
                #print("--- already done")
                continue
            if nsrc_wf["type"] == thisclass:
                #print(f"-------> {thisclass}")
                lnk_wf = nsrc_wf["inputs"][0]["link"] # wf link num in input slot / !!! inpslot=0
                #print(f"         wf link = {lnk_wf}")
                ntarg_wf, o_match = BypassReroutes(NodesWF, lnk_wf)
                #print("/////// BYPASSED")
                #print(ntarg_wf)
                #print("!!!!!")
                if o_match:
                    #print("!!! match")
                    with _StateLock:
                        GetterReg[thisclass].append(nsrc_id) # register current node id
                    if isinstance(ntarg_wf["widgets_values"], dict):
                        targ_wid_data = list(ntarg_wf["widgets_values"].values())[0] # 'widget values' is dict
                    else:
                        targ_wid_data = ntarg_wf["widgets_values"][0] # 'widget values' is list
                    break
                #else: print("??? incoming node is not approved ???")
        #print(f">>>>>>> GetIncomingNodeWidContent:\nsource {nsrc_id} / target {ntarg_wf['id']} / output = {targ_wid_data}")

    else: # sought_widget specified! search "this" node!
        for nsrc_id in NodesPrm:
            #print(f".......checking {nsrc_id}")
            if nsrc_id in GetterReg[thisclass]: # skip registered
                #print("--- already done")
                continue

            nsrc_prm = NodesPrm[nsrc_id]
            if nsrc_prm["class_type"] == thisclass:
                #print(f"-------> {thisclass}")
                GetterReg[thisclass].append(nsrc_id) # register current node id
                #print(nsrc_prm["inputs"])
                if sought_widget in nsrc_prm["inputs"]:
                    targ_wid_data = nsrc_prm["inputs"][sought_widget]
                    #print("!!! found sought_widget")
                break # @ this class!
        #print(f">>>>>>> GetIncomingNodeWidContent:\nsource {nsrc_id} / `{sought_widget}` content = {targ_wid_data}")

    return targ_wid_data

# ###############################################################################################
def AddImageLabPanel(img, text, font, font_size, pan_color):
    width = img.shape[2]
    font_path = folder_paths.get_full_path("customfonts", font)
    if font_path is None:
        print(f"[GU_Nodepack] Font '{font}' not found in customfonts/, using PIL default.")
        font = ImageFont.load_default()
    else:
        try:
            font = ImageFont.truetype(font_path, font_size)
        except (OSError, TypeError) as e:
            print(f"[GU_Nodepack] Failed to load font '{font}' ({type(e).__name__}: {e}), using PIL default.")
            font = ImageFont.load_default()
    font_color = "white"
    text_x = 5
    text_y = 2
    words = text.split()
    lines = []
    current_line = []
    current_line_width = 0

    for word in words:
        word_width = font.getbbox(word)[2]
        if word == "^": # line break, don't display this symbol
            lines.append(" ".join(current_line))
            current_line = []
            current_line_width = 0
            continue
        else:
            if current_line_width + word_width <= width - 2 * text_x:
                current_line.append(word)
                current_line_width += word_width + font.getbbox(" ")[2] # Add space width
            else:
                lines.append(" ".join(current_line))
                current_line = [word]
                current_line_width = word_width

    if current_line:
        lines.append(" ".join(current_line))

    # set the panel height automatically
    margin = 8
    required_height = (text_y + len(lines) * font_size) + margin
    pil_image = Image.new("RGB", (width, required_height), pan_color)
    draw = ImageDraw.Draw(pil_image)

    for line in lines:
        try:
            draw.text((text_x, text_y), line, font=font, fill=font_color, features=['-liga'])
        except (TypeError, KeyError):
            draw.text((text_x, text_y), line, font=font, fill=font_color)
        text_y += font_size

    img_out = torch.from_numpy(np.array(pil_image).astype(np.float32) / 255.0).unsqueeze(0)
    img_out = torch.cat((img, img_out), dim=1) # append down
    return img_out

# ###############################################################################################
def SubscribeImage(img, lab_tech, lab_pos, lab_neg, lab_gen, font, font_size):
    img_out = img
    pan_color_def = "black"
    pan_color_alt = "#101010"
    img_out = AddImageLabPanel(img_out, lab_tech, font, font_size, pan_color_def)
    img_out = AddImageLabPanel(img_out, lab_pos,  font, font_size, pan_color_alt)
    img_out = AddImageLabPanel(img_out, lab_neg,  font, font_size, pan_color_def)
    img_out = AddImageLabPanel(img_out, lab_gen,  font, font_size, pan_color_alt)
    return img_out

# ###############################################################################################
def GetModelVerInfo(hash_value):
    api_url = f"https://civitai.com/api/v1/model-versions/by-hash/{hash_value}"
    try:
        response = requests.get(api_url, timeout=10) # try because error on some workstation ???
    except (requests.RequestException, ConnectionError):
        return None

    if response.status_code == 200:
        return response.json()
    else:
        return None

# ###############################################################################################
def GetMetaData(filepath, type):
    filepath = folder_paths.get_full_path(type, filepath)
    with open(filepath, "rb") as file:
        # https://github.com/huggingface/safetensors#format
        # 8 bytes: N, an unsigned little-endian 64-bit integer, containing the size of the header
        header_size = int.from_bytes(file.read(8), "little", signed=False)

        if header_size <= 0:
            raise BufferError("Invalid header size")

        try:
            header = file.read(header_size)
            if header_size <= 0:
                raise BufferError("Invalid header")
            header_json = json.loads(header)
            return header_json["__metadata__"] if "__metadata__" in header_json else None
        except (json.JSONDecodeError, KeyError, BufferError, UnicodeDecodeError):
            return None

# ###############################################################################################
def ExtractTags(metadata):
    if metadata is None:
        return []
    if "ss_tag_frequency" in metadata:
        metadata = metadata["ss_tag_frequency"]
        metadata = json.loads(metadata)
        tags_dict = {}
        for _, dataset in metadata.items():
            for tag, count in dataset.items():
                tag = str(tag).strip()
                if tag in tags_dict:
                    tags_dict[tag] = tags_dict[tag] + count
                else:
                    tags_dict[tag] = count
        # sort tags by training frequency descending
        tags_dict = dict(sorted(tags_dict.items(), key=lambda item: item[1], reverse=True))
        #print("!!!!!!!!!!!!")
        #print(json.dumps(tags_dict, indent=4))
        train_keys = list(tags_dict.keys())

        trash_words = GetTrashWords()
        tags = []
        for x in train_keys:
            t = x.split()[0]  # assume tag is always first word
            if t in tags:
                continue
            # heuristic bypass: underscore/digit/mixedCase tokens are specific triggers
            # and should skip the common-word filter (e.g. g_boss, style2, CharName)
            if is_likely_trigger(t) or t.lower() not in trash_words:
                tags.append(t)
            if len(tags) == 5: break  # limit count, use only max weight, because sorted
        return tags
    else:
        return []

# ###############################################################################################
def ProcessLora(model, clip, lora, lora_str, clip_str):
    lorapath = folder_paths.get_full_path("loras", lora)
    loratens = comfy.utils.load_torch_file(lorapath, safe_load=True)
    model_lora, clip_lora = comfy.sd.load_lora_for_models(model, clip, loratens, lora_str, clip_str)

    lora_name = {"content": lora, "image": None, "type": "loras"}
    metadata = GetMetaData(lora_name["content"], "loras")
    #print("!!!!!!!!!!!!")
    #print(json.dumps(metadata, indent=4))

    tags = []
    # first search on civitai (with cached hash to avoid re-reading large files)
    mtime = os.path.getmtime(lorapath)
    with _StateLock:
        cached = _SHA256Cache.get(lorapath)
    if cached is not None and cached[0] == mtime:
        lora_hash = cached[1]
    else:
        lora_hash = calc_SHA256(lorapath)  # slow I/O outside the lock
        with _StateLock:
            _SHA256Cache[lorapath] = (mtime, lora_hash)
    model_info = GetModelVerInfo(lora_hash)
    if model_info is not None:
        if "trainedWords" in model_info:
            tags = model_info["trainedWords"]

    if len(tags) == 0: # not found, try get from lora file
        tags = ExtractTags(metadata)

    output_tags = strlist_to_str(tags)

    if len(output_tags) > 0:
        output_tags += " " # add safe space
    #else: output_tags = os.path.splitext(lora)[0] # no tags found, use lora filename ???

    return model_lora, clip_lora, output_tags

# ###############################################################################################
# ###############################################################################################
# ###############################################################################################

class Folders:
    MOTION_LORA = "animatediff_motion_lora"

class MotionLoraInfo:
    def __init__(self, name: str, strength: float = 1.0, hash: str = ""):
        self.name = name
        self.strength = strength
        self.hash = ""

    def set_hash(self, hash: str):
        self.hash = hash

    def clone(self):
        return MotionLoraInfo(self.name, self.strength, self.hash)

class MotionLoraList:
    def __init__(self):
        self.loras: list[MotionLoraInfo] = []

    def add_lora(self, lora: MotionLoraInfo):
        self.loras.append(lora)

    def clone(self):
        new_list = MotionLoraList()
        for lora in self.loras:
            new_list.add_lora(lora.clone())
        return new_list

# ###############################################################################################
def GetAvailableMotionLoras():
    ml = ["None"]
    adpath = os.path.join(folder_paths.models_dir, Folders.MOTION_LORA)
    try:
        for filename in os.listdir(adpath):
            if IsModelFile(filename):
                ml.append(os.path.basename(filename))
    except OSError: pass
    return ml

# ###############################################################################################
def GetMotionLoraPath(lora_name):
    return os.path.join(folder_paths.models_dir, Folders.MOTION_LORA, lora_name)


# ###############################################################################################
# ##################################### TRIGGER WORDS ###########################################
# ###############################################################################################

_TrashWordsCache = None

def _LoadWordsFile(fname):
    # load plain word list from a text file in web/ (one word per line, '#' starts a comment)
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web", fname)
    words = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.split("#", 1)[0].strip()
                if line:
                    words.append(line.lower())
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"[GU_Nodepack] {fname} read failed: {type(e).__name__}: {e}")
    return words

def GetTrashWords():
    # return combined built-in (default_words.txt) + user (custom_words.txt), dedup, lowercase, cached
    global _TrashWordsCache
    with _StateLock:
        if _TrashWordsCache is not None:
            return _TrashWordsCache
        default = _LoadWordsFile("default_words.txt")
        custom = _LoadWordsFile("custom_words.txt")
        _TrashWordsCache = list({*default, *custom})
        return _TrashWordsCache

def is_likely_trigger(word):
    # fast-accept heuristic: words with non-letter chars or mixedCase are specific trigger tokens
    # (e.g. g_boss, style2, CharName), not common dictionary words. Callers use this BEFORE the
    # trash-list check to avoid false-negatives for specific triggers.
    if len(word) < 2:
        return False
    if "_" in word:
        return True
    if any(c.isdigit() for c in word):
        return True
    if re.search(r'[a-z]', word) and re.search(r'[A-Z]', word):
        return True
    return False

