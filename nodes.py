# GU_Nodepack (C) Alexander Guryev, 2026 | https://alexguryev.com

import comfy.samplers
import folder_paths
import json
import math
import numpy as np
import os
from PIL import Image
import random
import time
import torch

from .gu_funclib import get_datetime_str, make_unique_filename, safe_string, is_media_file, check_arr_elem_in_str
from .functions import (AnyType, GetSystemInfo, GetIncomingNodeWidContent, SubscribeImage,
                        ProcessLora, GetLoraSubfolders, GetAvailableMotionLoras,
                        MotionLoraList, GetMotionLoraPath, MotionLoraInfo)
from .prestartup_script import IsModelFile, GetLoraFolder, FillLoraList, GetLoraList, GetSeedFileLoaded, SetSeedFileLoaded


TAny = AnyType("*")
TSides = [0,0,0,0]
TimeGlobal = None
SeedList = []
SampList = comfy.samplers.SAMPLER_NAMES.copy()
SampListLen = len(SampList)
SchedList = comfy.samplers.SCHEDULER_NAMES.copy()
SchedListLen = len(SchedList)

# ###############################################################################################
# ###############################################################################################
# ###############################################################################################

class G_GetModelName: # get checkpoint file name from incoming node
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
            },
            "optional": {
                "model" : ("MODEL", {}),
            },
            "hidden": {
                "extra_pnginfo" : "EXTRA_PNGINFO",
                "prompt"        : "PROMPT",
            },
        }

    @classmethod
    def IS_CHANGED(s, **kwargs):
        return float("NaN")

    INPUT_IS_LIST = True
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("filename",)
    FUNCTION = "run"
    CATEGORY = "GU_Nodepack"
    DESCRIPTION = """Get a checkpoint filename from incoming node"""

    def run(self, extra_pnginfo, prompt, model=None):
        name = "!unknown!"
        if model is None:
            return (name,)

        model_data = GetIncomingNodeWidContent(extra_pnginfo[0], prompt[0], "G_GetModelName")
        if IsModelFile(model_data): name = model_data

        return (os.path.splitext(os.path.basename(name))[0],) # name only
        #return { "ui": { "uid": uid, }, "result": (os.path.splitext(os.path.basename(name))[0],) }

# ###############################################################################################
# ###############################################################################################
# ###############################################################################################

class G_ImgLabel: # make image label
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
            },
            "optional": {
                "model_name"     : ("STRING", {"forceInput": True, "tooltip": "Put a model name string here"}),
                "lora_names"     : ("STRING", {"forceInput": True, "tooltip": "Put all lora names in single string here"}),
                "prompt_pos"     : ("STRING", {"forceInput": True, "tooltip": ""}),
                "prompt_neg"     : ("STRING", {"forceInput": True, "tooltip": ""}),
                "time_ctrl"      : ("STRING", {"forceInput": True, "tooltip": "Elapsed time input"}),
                "samp_seed"      : ("INT",    {"forceInput": True, "tooltip": "-//- seed"}),
                "samp_steps"     : ("INT",    {"forceInput": True, "tooltip": "-//- steps"}),
                "samp_cfg"       : ("FLOAT",  {"forceInput": True, "tooltip": "-//- cfg"}),
                "samp_denoise"   : ("FLOAT",  {"forceInput": True, "tooltip": "-//- denoise"}),
                "samp_sampler"   : (TAny,     {"forceInput": True, "tooltip": "Sampling sampler"}),
                "samp_scheduler" : (TAny,     {"forceInput": True, "tooltip": "-//- scheduler"}),
                "image"          : ("IMAGE", {"tooltip": "Ready image for labeling",}),
                "font"           : ([f for f in folder_paths.get_filename_list("customfonts") if f.lower().endswith((".ttf", ".otf", ".ttc"))],),
                "font_size"      : ("INT", {"default": 14, "min": 8, "max": 200, "step": 1}),
                "used_ctrlnet"   : ("BOOLEAN", {"default": False, "forceInput": False, "tooltip": "If ControlNet is used - for filename suffix"}),
                "used_detdaemon" : ("BOOLEAN", {"default": False, "forceInput": False, "tooltip": "If DetailDaemon is used - for filename suffix"}),
                "used_redux"     : ("BOOLEAN", {"default": False, "forceInput": False, "tooltip": "If Redux is used - for filename suffix"}),
            },
        }

    RETURN_TYPES = ("IMAGE", "STRING", "STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("img_w_label", "tech_label", "pos_label", "neg_label", "gen_label", "tech_suffix")
    OUTPUT_TOOLTIPS = ("Image with label",
                       "Technical system info",
                       "Positive prompt", 
                       "Negative prompt", 
                       "Generation params info",
                       "Filename short technical suffix")
    OUTPUT_NODE = True
    FUNCTION = "run"
    CATEGORY = "GU_Nodepack"
    DESCRIPTION = """Creates a technical labels for an image.
All inputs are optional!"""

    # all inputs init in case of missing
    def run(self, model_name="", lora_names="", prompt_pos="", prompt_neg="", time_ctrl="",
            samp_seed=-1, samp_steps=0, samp_cfg=-1, samp_denoise=-1, samp_sampler=None, samp_scheduler=None,
            image=None, font=None, font_size=0,
            used_ctrlnet=None, used_detdaemon=None, used_redux=None):
        # date-time + hardware
        si = GetSystemInfo()
        lab_tech = (get_datetime_str(filesafe=False) +
            f" ^ Device: {si['gpu']} Type: {si['type']} PyTorch/CUDA: {si['torch']} | VRAM: {si['vram']} ^ CPU: {si['cpu']} | RAM: {si['ram']}")

        # prompts retranslate
        lab_pos = str(prompt_pos)
        lab_neg = str(prompt_neg)

        # gen params
        lab_gen = "Model: " + str(model_name) + " ^ Loras: " + str(lora_names)
        lab_gen += f" ^ Seed: {samp_seed} | Steps: {samp_steps} | CFG: {samp_cfg:.2f} | Samp: {samp_sampler} | Sched: {samp_scheduler} | Denoise: {samp_denoise:.2f} ^ "

        # filename suffix
        techsuffix = "(used"
        if lora_names is not None:
            if len(lora_names) > 0:
                techsuffix += "_lora"
        if used_ctrlnet:
            techsuffix += "_ctrlnet"
            lab_gen += " + ControlNet"
        if used_detdaemon:
            techsuffix += "_detdaemon"
            lab_gen += " + DetailDaemon"
        if used_redux:
            techsuffix += "_redux"
            lab_gen += " + Redux"

        if techsuffix == "(used": # need to erase suffix
            techsuffix = ""
        else:
            techsuffix += ")"

        if time_ctrl != "":
            lab_gen += f" ^ Elapsed time: {time_ctrl}"

        # imprint label to an image
        img_out = image
        if image is not None:
            lp = "Positive prompt: ^ " + lab_pos
            np = "Negative prompt: ^ " + lab_neg
            img_out = SubscribeImage(image, lab_tech, lp, np, lab_gen, font, font_size)

        # reformat line breaks for output
        lab_tech = lab_tech.replace(" ^ ", "\n")
        lab_gen  = lab_gen.replace (" ^ ", "\n")

        return img_out, lab_tech, lab_pos, lab_neg, lab_gen, techsuffix

# ###############################################################################################
# ###############################################################################################
# ###############################################################################################

class G_SaveImgInfo: # write image info to text file
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "tech_label": ("STRING", {"forceInput": True, "tooltip": "Tech info"}),
                "pos_label" : ("STRING", {"forceInput": True, "tooltip": "Positive prompt"}),
                "neg_label" : ("STRING", {"forceInput": True, "tooltip": "Negative prompt"}),
                "gen_label" : ("STRING", {"forceInput": True, "tooltip": "Generation info"}),
                "file_name" : ("STRING", {"forceInput": True,}),
            },
        }

    OUTPUT_NODE = True
    RETURN_TYPES = ()
    FUNCTION = "run"
    CATEGORY = "GU_Nodepack"
    DESCRIPTION = """Write TXT file with image info"""

    def run(self, tech_label, pos_label, neg_label, gen_label, file_name):
        if len(file_name) > 0:
            fpath = make_unique_filename(os.path.join(folder_paths.get_output_directory(), file_name + ".txt"))
            try:
                file = open(fpath, "w")
                file.flush()
                file.write(tech_label)
                file.write("\n\nPositive prompt:\n")
                file.write(pos_label)
                file.write("\n\nNegative prompt:\n")
                file.write(neg_label)
                file.write("\n\n")
                file.write(gen_label)
                file.close()
            except OSError:
                print(f"\033[91mERROR writing the file {fpath}\n\033[0m")

        return {}

# ###############################################################################################
# ###############################################################################################
# ###############################################################################################

class G_ConcatStr: # concat str for filename or prompt
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "inputs": ("INT",     {"default": 2, "min": 2, "max": 10, "step": 1}),
                "delim" : ("STRING",  {"default": "_", "forceInput": False,}),
                "isfile": ("BOOLEAN", {"default": False, "forceInput": False, "tooltip": "use output for filename?"}),
            },
        }

    RETURN_TYPES = ("STRING",)
    FUNCTION = "run"
    CATEGORY = "GU_Nodepack"
    DESCRIPTION = """Concat strings for filename or prompt.
WARNING! On earlier ComfyUI versions EXTRA inputs
`str_-2`, `str_-1`, `str_0` may appear - don`t use them!"""

    def run(self, inputs, delim, isfile, **kwargs):
        sout = ""
        if len(delim) != 0:
            delim, _ = safe_string(delim, isfile) # with switch for filename

        for c in range(1, inputs+1):
            s = str(kwargs[f"str_{c}"])
            if s != "":
                if c > 1 and len(sout) > 0:
                    sout += delim
                sout += s

        return (sout,)

# ###############################################################################################
# ###############################################################################################
# ###############################################################################################

class G_TimerOn: # start timer node
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "any_i" : (TAny,  {"forceInput": True,}),
            },
        }

    @classmethod
    def IS_CHANGED(s, **kwargs):
        return float("NaN")

    RETURN_TYPES = (TAny,)
    RETURN_NAMES = ("any_o",)
    FUNCTION = "run"
    CATEGORY = "GU_Nodepack"
    DESCRIPTION = """Runs internal timer for time check.
Place before sampler!"""

    def run(self, any_i):
        global TimeGlobal
        TimeGlobal = time.time() # init
        s = str(TimeGlobal)
        #print (f"\033[95m>>>>>>> G_TimerOn: {s} | {seed}\033[0m")
        return (any_i,)

# ###############################################################################################
# ###############################################################################################
# ###############################################################################################

class G_TimerOff: # stop timer node / retruns elapsed time string
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "any_i" : (TAny, {"forceInput": True,}),
            },
        }

    RETURN_TYPES = ("STRING", "INT")
    RETURN_NAMES = ("time", "time_raw")
    OUTPUT_NODE = True
    OUTPUT_TOOLTIPS = ("", "Elapsed time string `HH:MM:SS`")
    FUNCTION = "run"
    CATEGORY = "GU_Nodepack"
    DESCRIPTION = """Stops internal timer for time check.
Place before `GU Image Label`!"""

    def run(self, any_i):
        s = ""
        t = 0
        global TimeGlobal
        if TimeGlobal is not None:
            t = time.time() - TimeGlobal # get elapsed
            TimeGlobal = None # reset timer
            hours   = int(t // 3600)
            minutes = int((t % 3600) // 60)
            seconds = int(t % 60)
            s = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return (s, int(t))

# ###############################################################################################
# ###############################################################################################
# ###############################################################################################

class G_SeedList: # random seed with memory
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "seed"           : ("INT",     {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
                "reset_list"     : ("BOOLEAN", {"default": False, "tooltip": "Force clean previous seeds on next run (ignored if init_from_file)"}),
                "init_from_file" : ("BOOLEAN", {"default": True, "tooltip": "Load list from a text file (works only at first run!)"}),
                "store_to_file"  : ("BOOLEAN", {"default": True, "tooltip": "Store list to a text file (works at every run! file will be overwritten!)"}),
                "filename"       : ("STRING",  {"default": "seedfile", "tooltip": "Only name of file (no path or extension! incorrect name will be fixed internally!), will be stored in `tmp` folder"}),
            },
            "optional": {
                "project"    : ("STRING", {"default": "", "forceInput": True, "tooltip": "recommended to connect to `GU Project Name` node output"}),
            },
        }

    @classmethod
    def IS_CHANGED(s, **kwargs):
        return float("NaN")

    RETURN_TYPES = ("INT", "STRING")
    RETURN_NAMES = ("seed", "prev_seeds")
    OUTPUT_IS_LIST = (False, True)
    FUNCTION = "run"
    CATEGORY = "GU_Nodepack"
    DESCRIPTION = """Make seed number and store it to an internal list,
if not equal to previous value"""

    def run(self, seed, reset_list, init_from_file, store_to_file, filename, project=""):
        global SeedList

        fn, fix = safe_string(filename, True)
        tmp = folder_paths.get_output_directory()
        if len(project) > 0:
            tmp = os.path.join(tmp, "(work)", project)
            os.makedirs(tmp, exist_ok=True)
        fname = os.path.join(tmp, f"{fn}.txt") if (len(safe_string(filename, True)) > 0) else os.path.join(tmp, "seedfile.txt") # custom or default name
        fname = os.path.normpath(fname)

        if init_from_file and not GetSeedFileLoaded():
            try:
                file = open(fname, "r")
                arr = file.read().splitlines()
                SetSeedFileLoaded(True)
                file.close()
                SeedList.clear()
                for s in arr:
                    SeedList.append(int(s))
            except (OSError, ValueError):
                print(f"\033[33mERROR reading a seed file {fname}\n\033[0m")
        else:
            if reset_list: SeedList.clear()

        n = len(SeedList)
        if n > 0:
            if seed != SeedList[n-1]:
                SeedList.append(seed)
        else:
            SeedList.append(seed)

        if store_to_file:
            try:
                file = open(fname, "w")
                file.flush()
                for item in SeedList:
                    file.write("%s\n" % item)
                file.close()
            except OSError:
                print(f"\033[91mERROR writing a seed file {fname}\n\033[0m")

        return seed, SeedList

# ###############################################################################################
# ###############################################################################################
# ###############################################################################################

class G_ResSelect: # resolution selector: sdxl/flux/sd3.5 // implemented in JS
    @classmethod
    def INPUT_TYPES(self):
        return {
            "required": {
                "width"    : ("INT", {"default": 1024, "min": 256, "max": 3840, "step": 64}),
                "height"   : ("INT", {"default": 1024, "min": 256, "max": 3840, "step": 64}),
                "portrait" : ("BOOLEAN", {"default": False, "tooltip": "Swap width and height values = set orientation to 'Portrait' (default is 'Landscape')"}),
            },
        }

    RETURN_TYPES = ("INT", "INT")
    RETURN_NAMES = ("W", "H")
    FUNCTION = "run"
    CATEGORY = "GU_Nodepack"
    DESCRIPTION = """A lot of resolution presets"""
    
    def run(self, width, height, portrait):
        if portrait:
            return int(height), int(width)
        return int(width), int(height)

# ###############################################################################################
# ###############################################################################################
# ###############################################################################################

class G_TextEdit:  # text editor w/JS
    @classmethod
    def INPUT_TYPES(self):
        return {
            "required": {
                "only"    : ("STRING",  {"forceInput": False, "multiline": False, "default":" dynamic text edit !"}),
                "text"    : ("STRING",  {"forceInput": True, "multiline": True}),
                "protect" : ("BOOLEAN", {"forceInput": False, "default": False}),
            },
            "hidden": {
                "extra_pnginfo" : "EXTRA_PNGINFO",
                "prompt"        : "PROMPT",
            },
        }

    @classmethod
    def IS_CHANGED(s, **kwargs):
        return float("NaN")

    INPUT_IS_LIST = True
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("text_out",)
    OUTPUT_IS_LIST = (False,)
    OUTPUT_NODE = True
    FUNCTION = "run"
    CATEGORY = "GU_Nodepack"
    DESCRIPTION = """Edit incoming text and protect edited text
from refreshing on next Queue run"""

    def run(self, only, text, protect, extra_pnginfo, prompt):
        editor_widg = "text_ed"
        sout = text[0] # init output value

        #conclear()
        te_data = GetIncomingNodeWidContent(extra_pnginfo[0], prompt[0], "G_TextEdit", editor_widg)
        if te_data is not None: sout = te_data

        #print(f"out = {sout}\n")
        return {"ui": {"text": text}, "result": (sout,)}
        #return (sout,)

# ###############################################################################################
# ###############################################################################################
# ###############################################################################################

class G_ProjName:  # set project name
    @classmethod
    def INPUT_TYPES(self):

        return {
            "required": {
                "project" : ("STRING", {"default": "TEST", }),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("name",)
    FUNCTION = "run"
    CATEGORY = "GU_Nodepack"
    DESCRIPTION = """Set project name"""

    def run(self, project):
        sout = ""
        if len(project) > 0:
            sout = safe_string(project)[0]
        return (sout,)

# ###############################################################################################
# ###############################################################################################
# ###############################################################################################

class G_ProjPath:  # make project path
    @classmethod
    def INPUT_TYPES(self):
        proc_types = ["",
                      "i2i",    # image to image
                      "i2v",    # image to video
                      "i3d",    # image to 3d
                      "inp",    # inpaint
                      "otp",    # outpaint
                      "t2i",    # text to image
                      "t2v",    # text to video
                      "t3d",    # text to 3d
                      "v2v",    # video to video
                      "v3d"     # video to 3d
                      ]

        return {
            "required": {
                "custom_name"    : ("STRING",   {"default": "test", "tooltip": "manual filename"}),
                "use_custom_name": ("BOOLEAN",  {"default": True,}),
                "change_from"    : ("STRING",   {"default": "", "tooltip": "sub-name to change"}),
                "change_to"      : ("STRING",   {"default": "", "tooltip": "replacer for sub-name"}),
                "name_suffix"    : ("STRING",   {"default": "", }),
                "use_date"       : ("BOOLEAN",  {"default": False, }),
                "model_type"     : ("STRING",   {"default": "", "tooltip": "generative model type"}),
                "proc_type"      : (proc_types, {"default": "", "tooltip": "process type"}),
                "is_upscale"     : ("BOOLEAN",  {"default": False, "tooltip": "enable to add `_UP` sub-folder"}),
                "stub"           : ("STRING",   {"default": "", "label_on":False}),
                # here is model selector
            },
            "optional": {
                "up_factor"      : ("FLOAT",  {"forceInput": True, "tooltip": "adds `_up#x` to output name"}),
                "filename"       : ("STRING", {"forceInput": True, "tooltip": "filename defined outside"}),
                "tech_suffix"    : ("STRING", {"forceInput": True, "tooltip": "technical suffix string"}),
                "project"        : ("STRING", {"forceInput": True, "tooltip": "project codename"}),
                "seed"           : ("INT",    {"forceInput": True, "tooltip": "adds `_s###` seed number to output name"}),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("path",)
    FUNCTION = "run"
    CATEGORY = "GU_Nodepack"
    DESCRIPTION = """Make media file path with many parameters"""

    # [(work)/project/][_UP/][date/]name[_namesuffix][_upNx][_modeltype][_proctype][_techsuffix][_seed]_#####_.ext
    # (work) if project
    def run(self, custom_name, use_custom_name, change_from, change_to, name_suffix, use_date, model_type, proc_type, is_upscale, stub,
        project="", up_factor=1.0, filename="", tech_suffix="", seed=-1):

        fn = custom_name if use_custom_name else filename
        if (len(change_from) > 0) and (len(change_to) > 0):
            fn = fn.replace(change_from, change_to)
        if len(name_suffix) > 0:
            fn = f"{fn}_{name_suffix}"

        sout = ""
        if len(project) > 0:
            # prevent path break in case of project dir use
            prj = project
            prj = prj.replace("\\", "_")
            prj = prj.replace("/", "_")
            fn = fn.replace("\\", "_")
            fn = fn.replace("/", "_")

            sout += f"(work)/{prj}/" # project root dir

        if is_upscale:
            sout += "_UP/"
            if up_factor > 1.0:
                fn = f"{fn}_up{str(int(math.ceil(up_factor)))}x"

        if use_date:
            sout += f"{get_datetime_str(dateonly=True)}/" # date folder

        if len(model_type) > 0:
            fn = f"{fn}_{model_type}"
        if len(proc_type) > 0:
            fn = f"{fn}_{proc_type}"
        if len(tech_suffix) > 0:
            fn = f"{fn}_{tech_suffix}"
        if seed >= 0:
            fn = f"{fn}_s{seed}"
        # tail number is always automatic

        sout += fn # join dir and filename
        return (safe_string(sout)[0],) # file safe path

# ###############################################################################################
# ###############################################################################################
# ###############################################################################################

class G_GetMediaInName: # get media file name from incoming node
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
            },
            "optional": {
                "any"       : (TAny,      {"forceInput": True, }),
                "strip_ext" : ("BOOLEAN", {"default": True, }),
            },
            "hidden": {
                "extra_pnginfo" : "EXTRA_PNGINFO",
                "prompt"        : "PROMPT",
            },
        }

    @classmethod
    def IS_CHANGED(s, **kwargs):
        return float("NaN")

    INPUT_IS_LIST = True
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("filename",)
    FUNCTION = "run"
    CATEGORY = "GU_Nodepack"
    DESCRIPTION = """Get a media filename from incoming node"""

    def run(self, strip_ext, extra_pnginfo, prompt, any=None):
        name = "!unknown!"
        if any is None:
            return (name,)

        media_data = GetIncomingNodeWidContent(extra_pnginfo[0], prompt[0], "G_GetMediaInName")

        if is_media_file(media_data):
            name = os.path.basename(media_data)
            if strip_ext[0] == True: # because inputs are lists
                name = os.path.splitext(name)[0] # name only

        return (name,)

# ###############################################################################################
# ###############################################################################################
# ###############################################################################################

class G_SidesPack:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "top"    : ("INT", {"default": 0, "min": 0, "max": 8192, "step": 1}),
                "left"   : ("INT", {"default": 0, "min": 0, "max": 8192, "step": 1}),
                "bottom" : ("INT", {"default": 0, "min": 0, "max": 8192, "step": 1}),
                "right"  : ("INT", {"default": 0, "min": 0, "max": 8192, "step": 1}),
            },
        }
    INPUT_IS_LIST = False
    RETURN_TYPES = (TSides,)
    RETURN_NAMES = ("sides",)
    FUNCTION = "run"
    CATEGORY = "GU_Nodepack"
    DESCRIPTION = """Pack side integers"""

    def run(self, top, left, bottom, right):
        a = [top,left,bottom,right]
        return (a,)

# ###############################################################################################
# ###############################################################################################
# ###############################################################################################

class G_SidesUnpack:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "sides" : (TSides, {"forceInput": True, }),
            },
        }
    INPUT_IS_LIST = False
    RETURN_TYPES = ("INT", "INT", "INT", "INT")
    RETURN_NAMES = ("top", "left", "bottom", "right")
    FUNCTION = "run"
    CATEGORY = "GU_Nodepack"
    DESCRIPTION = """Unpack side integers"""

    def run(self, sides):
        return sides[0], sides[1], sides[2], sides[3]

# ###############################################################################################
# ###############################################################################################
# ###############################################################################################

class G_CalcFrameCount: # real frame count for video load
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "frames_total": ("INT", {"forceInput": True, "tooltip": "frames in src video"}),
                "load_frames" : ("INT", {"forceInput": True, }),
                "load_nth"    : ("INT", {"forceInput": True, }),
            },
        }
    INPUT_IS_LIST = False
    RETURN_TYPES = ("INT",)
    RETURN_NAMES = ("real_frames",)
    FUNCTION = "run"
    CATEGORY = "GU_Nodepack"
    DESCRIPTION = """Calculate real frame count w/respect to Nth count"""

    def run(self, frames_total, load_frames, load_nth):
        if load_nth < 1:
            d = 0
        else:
            d = load_frames/load_nth

        if (d > 0) and (d < frames_total):
            f = d
        else:
            f = frames_total
        return (int(f),)

# ###############################################################################################
# ###############################################################################################
# ###############################################################################################

class G_ExtractPrompt:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "meta": ("METADATA_RAW", {"forceInput": True, }),
            },
        }

    INPUT_IS_LIST = False
    RETURN_TYPES = ("STRING", "STRING", "STRING")
    RETURN_NAMES = ("pos_prompt", "neg_prompt", "unsure_prompt")
    FUNCTION = "run"
    CATEGORY = "GU_Nodepack"
    DESCRIPTION = """Extract prompt strings from image metadata"""

    def run(self, meta):
        # extract data
        if meta is not None and isinstance(meta, dict):
            if "workflow" in meta:
                prompt = meta["workflow"]["nodes"]
            else: return "", "", ""
        else: return "", "", ""

        # gather suspicious nodes
        nodes = []
        for n in prompt:
            title = ""
            tit_by_class = False
            try: # first get manual title of a node
                title = n["title"].lower()
            except (KeyError, AttributeError): pass

            if len(title) == 0: # alt: get class of a node
                try:
                    title = n["type"].lower()
                    tit_by_class = True
                except (KeyError, AttributeError): pass

            if n["mode"] != 0: continue # only enabled nodes allowed!

            titles_good = ["prompt", "encode", "string", "showtext", "showany", "displayany", "positive", "negative", "pos", "neg"]
            titles_bad  = ["openpose", "vaeencode", "joinstring", "get_", "set_"]
            if check_arr_elem_in_str(titles_good, title) and not check_arr_elem_in_str(titles_bad, title):
                s = 1 if ("pos" in title) else (-1 if ("neg" in title) else 0) # 1 = pos, -1 = neg, 0 = undefined
                nodes.append([n, title, s, tit_by_class]) # 0:node, 1:title, 2:sign, 3:found by node class

        #print("!!!!!!!!!!!!!!!!!!")
        #print(json.dumps(nodes, indent=4))
        #print("!!!!!!!!!!!!!!!!!!")

        # process
        p_p = ""
        n_p = ""
        u_p = ""
        #print("\n\n\n\n")
        for n in nodes:
            #print(f"\n\n{n[0]['id']} :: {n[1]} :: {n[2]} :: {('CLASS' if n[3] else 'TITLE')}") # id + title + sign + found by class
            #print("!!!!!!!! TRY WIDGET VAL !!!!!!!!")
            try:
                widgets_values = n[0]["widgets_values"]
                #print(f"widgets_values : {widgets_values}")
            except (KeyError, TypeError): continue
            try:
                if len(widgets_values) == 0:
                    #print("!!!!!!!! NO LEN")
                    continue
            except TypeError: continue

            # fill output by 1st widget value
            if isinstance(widgets_values[0], list):
                v = widgets_values[0][0]
            else:
                v = widgets_values[0]

            if type(v) is str: # only string values allowed
                #print(v)
                if n[2] > 0:
                    if len(p_p) > 0: p_p += "\n\n"
                    p_p += v
                elif n[2] < 0:
                    if len(n_p) > 0: n_p += "\n\n"
                    n_p += v
                else:
                    if len(u_p) > 0: u_p += "\n\n"
                    u_p += v

        #print("\n\n")
        return p_p, n_p, u_p

# ###############################################################################################
# ###############################################################################################
# ###############################################################################################

class G_LoraStackExt:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "model"      : ("MODEL",),
                "clip"       : ("CLIP",),
                "pos_prompt" : ("STRING", {"default": "", "multiline": True, "tooltip": "(optional) insert positive prompt here for tags appending"}),
                "append_tags": ("BOOLEAN", {"default": False, "tooltip": "append all enabled LoRA tags as tail of the prompt"}),
                "s0"         : ("STRING", {"default": "", "label_on":False}),

                # "display": "slider"   -2..2
                "lora1"    : (FillLoraList(),),
                "lora_str1": ("FLOAT", {"default": 1.0, "min": -100.0, "max": 100.0, "step": 0.05}),
                "clip_str1": ("FLOAT", {"default": 1.0, "min": -100.0, "max": 100.0, "step": 0.05}),
                "enable1"  : ("BOOLEAN", {"default": True,}),
                "s1"       : ("STRING", {"default": "", "label_on":False}),

                "lora2"    : (FillLoraList(),),
                "lora_str2": ("FLOAT", {"default": 1.0, "min": -100.0, "max": 100.0, "step": 0.05}),
                "clip_str2": ("FLOAT", {"default": 1.0, "min": -100.0, "max": 100.0, "step": 0.05}),
                "enable2"  : ("BOOLEAN", {"default": True, }),
                "s2"       : ("STRING", {"default": "", "label_on":False}),

                "lora3"    : (FillLoraList(),),
                "lora_str3": ("FLOAT", {"default": 1.0, "min": -100.0, "max": 100.0, "step": 0.05}),
                "clip_str3": ("FLOAT", {"default": 1.0, "min": -100.0, "max": 100.0, "step": 0.05}),
                "enable3"  : ("BOOLEAN", {"default": True, }),
                "s3"       : ("STRING", {"default": "", "label_on":False}),

                "lora4"    : (FillLoraList(),),
                "lora_str4": ("FLOAT", {"default": 1.0, "min": -100.0, "max": 100.0, "step": 0.05}),
                "clip_str4": ("FLOAT", {"default": 1.0, "min": -100.0, "max": 100.0, "step": 0.05}),
                "enable4"  : ("BOOLEAN", {"default": True, }),
                "s4"       : ("STRING", {"default": "", "label_on":False}),

                "lora5"    : (FillLoraList(),),
                "lora_str5": ("FLOAT", {"default": 1.0, "min": -100.0, "max": 100.0, "step": 0.05}),
                "clip_str5": ("FLOAT", {"default": 1.0, "min": -100.0, "max": 100.0, "step": 0.05}),
                "enable5"  : ("BOOLEAN", {"default": True,}),
                "s5"       : ("STRING", {"default": "", "label_on":False}),

                "lora6"    : (FillLoraList(),),
                "lora_str6": ("FLOAT", {"default": 1.0, "min": -100.0, "max": 100.0, "step": 0.05}),
                "clip_str6": ("FLOAT", {"default": 1.0, "min": -100.0, "max": 100.0, "step": 0.05}),
                "enable6"  : ("BOOLEAN", {"default": True,}),
            },
        }

    INPUT_IS_LIST = False
    RETURN_TYPES = ("MODEL", "CLIP", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("model", "clip", "lora_tags", "lora_list", "ready_prompt")
    OUTPUT_TOOLTIPS = ("", "", "trigger words for all used loras", "formatted lora string with weights", "from here take the positive prompt with appended LoRA tags")
    FUNCTION = "run"
    CATEGORY = "GU_Nodepack"
    DESCRIPTION = """Extended LoRAs loader"""

    def run(self, model, clip, pos_prompt, append_tags, s0,
                  lora1, lora_str1, clip_str1, enable1, s1,   lora2, lora_str2, clip_str2, enable2, s2,
                  lora3, lora_str3, clip_str3, enable3, s3,   lora4, lora_str4, clip_str4, enable4, s4,
                  lora5, lora_str5, clip_str5, enable5, s5,   lora6, lora_str6, clip_str6, enable6):
        model_lora = model
        clip_lora = clip
        lora_tags = ""
        lora_list = ""
        prompt = pos_prompt

        slots = [
            (lora1, lora_str1, clip_str1, enable1), (lora2, lora_str2, clip_str2, enable2),
            (lora3, lora_str3, clip_str3, enable3), (lora4, lora_str4, clip_str4, enable4),
            (lora5, lora_str5, clip_str5, enable5), (lora6, lora_str6, clip_str6, enable6),
        ]
        for lora, lora_str, clip_str, enable in slots:
            if lora != "None" and enable and lora_str != 0:
                model_lora, clip_lora, s = ProcessLora(model_lora, clip_lora, lora, lora_str, clip_str)
                lora_tags += s
                lora_list += f"<lora:{lora}:{lora_str:.2f}:{clip_str:.2f}> " # <lora:name:lstr:cstr>

        if len(lora_tags) > 0 and append_tags:
            prompt += f", {lora_tags}"

        return model_lora, clip_lora, lora_tags, lora_list, prompt

# ###############################################################################################
# ###############################################################################################
# ###############################################################################################

class G_LoraRandomizer:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "model"          : ("MODEL",),
                "clip"           : ("CLIP",),
                "pos_prompt"     : ("STRING", {"default": "", "tooltip": "(optional) insert positive prompt here for tags appending"}),
                "append_tags"    : ("BOOLEAN", {"default": False, "tooltip": "append all enabled LoRA tags as tail of the prompt"}),
                "lora_subfolder" : (GetLoraSubfolders(), {}),
                "loras_max"      : ("INT", {"display": "slider", "default": 1, "min": 1, "max": 6, "step": 1, "tooltip": "maximum LoRAs to load"}),
                "strength_min"   : ("FLOAT", {"default": 1.0, "min": -100.0, "max": 100.0, "step": 0.05, "tooltip": "min LoRA weight"}),
                "strength_max"   : ("FLOAT", {"default": 1.0, "min": -100.0, "max": 100.0, "step": 0.05, "tooltip": "max LoRA weight"}),
                "clip_min"       : ("FLOAT", {"default": 1.0, "min": -100.0, "max": 100.0, "step": 0.05, "tooltip": "min LoRA weight"}),
                "clip_max"       : ("FLOAT", {"default": 1.0, "min": -100.0, "max": 100.0, "step": 0.05, "tooltip": "max LoRA weight"}),
            },
        }

    @classmethod
    def IS_CHANGED(s, **kwargs):
        return float("NaN")

    INPUT_IS_LIST = False
    RETURN_TYPES = ("MODEL", "CLIP", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("model", "clip", "lora_tags", "lora_list", "ready_prompt")
    OUTPUT_TOOLTIPS = ("", "", "trigger words for all used loras", "formatted lora string with weights", "from here take the positive prompt with appended LoRA tags")
    #OUTPUT_IS_LIST = (False, False, False, True)
    FUNCTION = "run"
    CATEGORY = "GU_Nodepack"
    DESCRIPTION = """Random LoRAs loader"""

    def run(self, model, clip, pos_prompt, append_tags, lora_subfolder, loras_max, strength_min, strength_max, clip_min, clip_max):
        model_lora = model
        clip_lora = clip
        lora_tags = ""
        lora_list = ""
        prompt = pos_prompt

        s = GetLoraFolder()
        subcut = lora_subfolder.find(os.sep)
        if subcut >= 0:
            s += lora_subfolder[subcut:]
        lo = FillLoraList(s)
        loras = []
        for x in lo:
            if x.find(os.sep) == -1:
                loras.append(x) # only from specific subfolder, not from it's children!
        #print(json.dumps(loras, indent=4))

        loras_total = len(loras)
        count = loras_max if loras_total >= loras_max else loras_total
        idx = random.sample(range(0, loras_total), count) # unique random selection of 'count' indices
        for i in idx:
            #print("/////////")
            #print(subcut)
            if subcut >= 0:
                lora = lora_subfolder[subcut:] + os.sep + loras[i]
            else:
                lora = loras[i]
            lstr = random.uniform(strength_min, strength_max)
            cstr = random.uniform(clip_min, clip_max)
            model_lora, clip_lora, tags = ProcessLora(model_lora, clip_lora, lora, lstr, cstr)
            lora_tags += tags
            lora_list += f"<lora:{lora}:{lstr:.2f}:{cstr:.2f}> "

        if len(lora_tags) > 0 and append_tags:
            prompt += f", {lora_tags}"

        return model_lora, clip_lora, lora_tags, lora_list, prompt

# ###############################################################################################
# ###############################################################################################
# ###############################################################################################

class G_TurboLora:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "model"       : ("MODEL",),
                "clip"        : ("CLIP",),
                "turbo_lora"  : (FillLoraList(),),
                "steps_normal": ("INT", {"default": 25, "min": 1, "max": 100}),
                "steps_turbo" : ("INT", {"default": 8, "min": 1, "max": 100}),
                "enable"      : ("BOOLEAN", {"default": True, }),
            },
        }

    INPUT_IS_LIST = False
    RETURN_TYPES = ("MODEL", "CLIP", "INT", "STRING")
    RETURN_NAMES = ("model", "clip", "steps", "lora_list")
    FUNCTION = "run"
    CATEGORY = "GU_Nodepack"
    DESCRIPTION = """Turbo LoRA switcher + specify Normal or Turbo Sampler Steps"""

    def run(self, model, clip, turbo_lora, steps_normal, steps_turbo, enable):
        model_lora = model
        clip_lora = clip
        steps = steps_turbo if enable else steps_normal
        lora_list = ""

        if enable:
            model_lora, clip_lora, tags = ProcessLora(model_lora, clip_lora, turbo_lora, 1.0, 1.0)
            lora_list = f"<lora:{turbo_lora}:1.0:1.0> "

        return model_lora, clip_lora, steps, lora_list

# ###############################################################################################
# ###############################################################################################
# ###############################################################################################

class G_MotionLoraStack:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "name1"    : (GetAvailableMotionLoras(),),
                "strength1": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 10.0, "step": 0.001}),
                "enable1"  : ("BOOLEAN", {"default": True,}),
                "s1"       : ("STRING", {"default": "", "label_on":False}),

                "name2"    : (GetAvailableMotionLoras(),),
                "strength2": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 10.0, "step": 0.001}),
                "enable2"  : ("BOOLEAN", {"default": True,}),
                "s2"       : ("STRING", {"default": "", "label_on":False}),

                "name3"    : (GetAvailableMotionLoras(),),
                "strength3": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 10.0, "step": 0.001}),
                "enable3"  : ("BOOLEAN", {"default": True,}),
                "s3"       : ("STRING", {"default": "", "label_on":False}),

                "name4"    : (GetAvailableMotionLoras(),),
                "strength4": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 10.0, "step": 0.001}),
                "enable4"  : ("BOOLEAN", {"default": True,}),
                "s4"       : ("STRING", {"default": "", "label_on":False}),

                "name5"    : (GetAvailableMotionLoras(),),
                "strength5": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 10.0, "step": 0.001}),
                "enable5"  : ("BOOLEAN", {"default": True,}),
                "s5"       : ("STRING", {"default": "", "label_on":False}),

                "name6"    : (GetAvailableMotionLoras(),),
                "strength6": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 10.0, "step": 0.001}),
                "enable6"  : ("BOOLEAN", {"default": True,}),
            },
            "optional": {
                "prev_motion_lora": ("MOTION_LORA",),
            },
        }

    INPUT_IS_LIST = False
    RETURN_TYPES = ("MOTION_LORA", "STRING")
    RETURN_NAMES = ("new_motion_lora", "lora_list")
    OUTPUT_IS_LIST = (False, True)
    OUTPUT_TOOLTIPS = ("", "list of used lora names w/o extension")
    CATEGORY = "GU_Nodepack"
    FUNCTION = "run"
    DESCRIPTION = """Motion LoRAs stack"""

    def run(self, name1, strength1, enable1, s1, name2, strength2, enable2, s2, name3, strength3, enable3, s3,
                  name4, strength4, enable4, s4, name5, strength5, enable5, s5, name6, strength6, enable6,
                  prev_motion_lora=None):

        if prev_motion_lora is None:
            motion_lora = MotionLoraList()
        else:
            motion_lora = prev_motion_lora.clone()

        lora_list = []

        slots = [
            (name1, strength1, enable1), (name2, strength2, enable2), (name3, strength3, enable3),
            (name4, strength4, enable4), (name5, strength5, enable5), (name6, strength6, enable6),
        ]
        for name, strength, enable in slots:
            if name != "None" and enable:
                lora_path = GetMotionLoraPath(name)
                if not os.path.isfile(lora_path):
                    raise FileNotFoundError(f"Motion lora '{name}' not found!")
                lora_info = MotionLoraInfo(name=name, strength=strength)
                motion_lora.add_lora(lora_info)
                lora_list.append(os.path.splitext(os.path.basename(name))[0])

        return motion_lora, lora_list


# ###############################################################################################
# ###############################################################################################
# ###############################################################################################

class G_StringLines:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "str_in"   : ("STRING", {"default": "", "multiline": True}),
                "sel_index": ("INT", {"default": 0, "min": 0, "max": 9999, "step": 1}),
            },
        }

    INPUT_IS_LIST = False
    OUTPUT_IS_LIST = (True, False, False)
    RETURN_TYPES = ("STRING", "STRING", "INT")
    RETURN_NAMES = ("str_list", "str_selected", "lines_count")
    FUNCTION = "run"
    CATEGORY = "GU_Nodepack"
    DESCRIPTION = """Split text to separate strings.
Return strings array and specific string"""

    def run(self, str_in, sel_index):
        str_list = []
        str_sel = ""

        if len(str_in) > 0:
            stmp = str_in.split('\n')
            for s in stmp:
                st = s.strip() #remove start/end whitespace
                if len(st) > 0:
                    str_list.append(st)

        ln_count = len(str_list)

        if 0 <= sel_index < ln_count:
            str_sel = str_list[sel_index]

        return str_list, str_sel, ln_count

# ###############################################################################################
# ###############################################################################################
# ###############################################################################################

class G_GetNodeActive:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {},
            "optional": {
                "any_i" : (TAny,  {"forceInput": True,}),
            },
        }

    @classmethod
    def IS_CHANGED(s, **kwargs):
        return float("NaN")

    INPUT_IS_LIST = False
    OUTPUT_IS_LIST = (False,)
    RETURN_TYPES = ("BOOLEAN",)
    RETURN_NAMES = ("is_active",)
    FUNCTION = "run"
    CATEGORY = "GU_Nodepack"
    DESCRIPTION = """Get `node is enabled` state"""

    def run(self, any_i=None):
        return (any_i is not None, )

# ###############################################################################################
# ###############################################################################################
# ###############################################################################################

class G_SwitchAnyIndex:  # switch any by index
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "inputs": ("INT", {"default": 2, "min": 2, "max": 10, "step": 1, "tooltip": "1...10"}),
                "index" : ("INT", {"default": 1, "min": 1, "max": 10, "step": 1, "tooltip": "if index is out of range 1...inputs, then use the nearest correct value"}),
            },
        }

    RETURN_TYPES = (TAny,)
    FUNCTION = "run"
    CATEGORY = "GU_Nodepack"
    DESCRIPTION = """Switch any inputs by index.
WARNING! On earlier ComfyUI versions EXTRA inputs
`any_-1`, `any_0` may appear - don`t use them!"""

    def run(self, inputs, index, **kwargs):
        if index < 1:
            i = 1
        else:
            i = index if index <= inputs else inputs
        return (kwargs[f"any_{i}"], )

# ###############################################################################################
# ###############################################################################################
# ###############################################################################################

class G_SetFramesVideo:  # set frame count for LTX-type video
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "frames": ("INT", {"default": 9, "min": 9, "max": 1001, "step": 8, "tooltip": "N*8 + 1"}),
            },
        }

    RETURN_TYPES = ("INT",)
    FUNCTION = "run"
    CATEGORY = "GU_Nodepack"
    DESCRIPTION = """Set frames count by formula N*8 + 1"""

    def run(self, frames):
        return frames,

# ###############################################################################################
# ###############################################################################################
# ###############################################################################################

class G_GetSampIndex:  # get sampler name by index in all samplers list
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "s_list" : (SampList, {}),
                "index"  : ("INT",    {"default": 1, "min": 1, "max": SampListLen, "step": 1}),
                "total"  : ("STRING", {"default": f"{SampListLen}"}), # js-read-only
            },
        }

    RETURN_TYPES = (comfy.samplers.KSampler.SAMPLERS, "STRING", "INT")
    RETURN_NAMES = ("sampler", "sampler_name", "total")
    FUNCTION = "run"
    CATEGORY = "GU_Nodepack"
    DESCRIPTION = """Get sampler name by index in samplers list,
and total num of samplers"""

    def run(self, s_list, index, total):
        return SampList[index-1], SampList[index-1], SampListLen

# ###############################################################################################
# ###############################################################################################
# ###############################################################################################

class G_GetSchedIndex:  # get scheduler name by index in all schedulers list
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "s_list" : (SchedList, {}),
                "index"  : ("INT",    {"default": 1, "min": 1, "max": SchedListLen, "step": 1}),
                "total"  : ("STRING", {"default": f"{SchedListLen}"}), # js-read-only
            },
        }

    RETURN_TYPES = (comfy.samplers.KSampler.SCHEDULERS, "STRING", "INT")
    RETURN_NAMES = ("scheduler", "scheduler_name", "total")
    FUNCTION = "run"
    CATEGORY = "GU_Nodepack"
    DESCRIPTION = """Get scheduler name by index in schedulers list,
and total num of schedulers"""

    def run(self, s_list, index, total):
        return SchedList[index-1], SchedList[index-1], SchedListLen


# ###############################################################################################
# ###############################################################################################
# ###############################################################################################

class G_StringToVals:  # parse string to list of values
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "string"   : ("STRING", {"default": "1.1, 2.3, 3.7", "multiline": True, "tooltip": "string list of values, separated by commas"}),
                "out_type" : (["string", "float", "integer"], {"default": "", "tooltip": "output data type + use appropriate out slot"}),
            },
        }

    INPUT_IS_LIST = False
    OUTPUT_IS_LIST = (False, False, False)
    RETURN_TYPES = ("STRING", "FLOAT", "INT")
    RETURN_NAMES = ("string_list", "float_list", "int_list")
    FUNCTION = "run"
    CATEGORY = "GU_Nodepack"
    DESCRIPTION = """Break string to values.
If number are incorrect - return zeroes"""

    def run(self, string, out_type):
        delim = ","
        out_str = []
        out_float = []
        out_int = []

        if len(string) > 0:
            match out_type:
                case "string": out_str = string.split(delim)

                case "float":
                    for x in string.split(delim):
                        try: n = float(x.strip())
                        except ValueError: n = 0
                        out_float.append(n)

                case "integer":
                    for x in string.split(delim):
                        try: n = int(x)
                        except ValueError: n = 0
                        out_int.append(n)

        return out_str, out_float, out_int

# ###############################################################################################
# ###############################################################################################
# ######################################  INTERFACE  ############################################
# ###############################################################################################
# ###############################################################################################

NODE_CLASS_MAPPINGS = {
    "G_CalcFrameCount"  : G_CalcFrameCount,
    "G_ConcatStr"       : G_ConcatStr,
    "G_ExtractPrompt"   : G_ExtractPrompt,
    "G_GetMediaInName"  : G_GetMediaInName,
    "G_GetModelName"    : G_GetModelName,
    "G_GetNodeActive"   : G_GetNodeActive,
    "G_GetSampIndex"    : G_GetSampIndex,
    "G_GetSchedIndex"   : G_GetSchedIndex,
    "G_ImgLabel"        : G_ImgLabel,
    "G_LoraRandomizer"  : G_LoraRandomizer,
    "G_LoraStackExt"    : G_LoraStackExt,
    "G_MotionLoraStack" : G_MotionLoraStack,
    "G_ProjName"        : G_ProjName,
    "G_ProjPath"        : G_ProjPath,
    "G_ResSelect"       : G_ResSelect,
    "G_SaveImgInfo"     : G_SaveImgInfo,
    "G_SeedList"        : G_SeedList,
    "G_SetFramesVideo"  : G_SetFramesVideo,
    "G_SidesPack"       : G_SidesPack,
    "G_SidesUnpack"     : G_SidesUnpack,
    "G_StringLines"     : G_StringLines,
    "G_StringToVals"    : G_StringToVals,
    "G_SwitchAnyIndex"  : G_SwitchAnyIndex,
    "G_TextEdit"        : G_TextEdit,
    "G_TimerOn"         : G_TimerOn,
    "G_TimerOff"        : G_TimerOff,
    "G_TurboLora"       : G_TurboLora,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "G_CalcFrameCount"  : "GU Calculate Frame Count",
    "G_ConcatStr"       : "GU Concat Strings",
    "G_ExtractPrompt"   : "GU Extract Prompt",
    "G_GetMediaInName"  : "GU Get Media Input Name",
    "G_GetModelName"    : "GU Get Model Filename",
    "G_GetNodeActive"   : "GU Get Node Active",
    "G_GetSampIndex"    : "GU Get Sampler Indexed",
    "G_GetSchedIndex"   : "GU Get Scheduler Indexed",
    "G_ImgLabel"        : "GU Image Label",
    "G_LoraRandomizer"  : "GU Lora Randomizer",
    "G_LoraStackExt"    : "GU Lora Stack Extended",
    "G_MotionLoraStack" : "GU Motion Lora Stack",
    "G_ProjName"        : "GU Project Name",
    "G_ProjPath"        : "GU Project Path",
    "G_ResSelect"       : "GU Resolution Select",
    "G_SaveImgInfo"     : "GU Save Image Info",
    "G_SeedList"        : "GU Seed List",
    "G_SetFramesVideo"  : "GU Set Frames Video",
    "G_SidesPack"       : "GU Sides Pack",
    "G_SidesUnpack"     : "GU Sides Unpack",
    "G_StringLines"     : "GU String Lines",
    "G_StringToVals"    : "GU String To Values",
    "G_SwitchAnyIndex"  : "GU Switch Any by Index",
    "G_TextEdit"        : "GU Text Edit",
    "G_TimerOn"         : "GU TimerON",
    "G_TimerOff"        : "GU TimerOFF",
    "G_TurboLora"       : "GU Turbo Lora",
}
