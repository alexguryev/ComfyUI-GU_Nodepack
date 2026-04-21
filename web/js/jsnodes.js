// GU_Nodepack (C) Alexander Guryev, 2026 | https://alexguryev.com

import { app } from "../../../scripts/app.js";
import { ComfyWidgets } from "../../../scripts/widgets.js";
import { api } from "../../../scripts/api.js";

// /////////////////////////////////////////////////////////////////////////////////////

const AspectsIn = [ // formatted for convenient view in dropbox
        ["img 1:1 #1 ······", "512", "512"],
        ["img 1:1 #2 ······", "1024", "1024"],
        ["img 1:1 #3 ······", "1536", "1536"],
        ["img 1:1 #4 ······", "2176", "2176"],
        ["img 3:2 #1 ······", "1248",  "832"],
        ["img 3:2 #2 ······", "1536", "1024"],
        ["img 3:2 MJ6 ·····", "1344", "896"],
        ["img 4:3 #1 ······", "1176", "888"],
        ["img 4:3 MJ6 ·····", "1232", "928"],
        ["img 7:5 #1 ······", "1216", "880"],
        ["img 7:5 #2 ······", "1920", "1360"],
        ["img 7:5 MJ6 ·····", "1312", "928"],
        ["img 1.43:1 ······", "1224", "856"],
        ["img 1.618:1 ····", "1296", "800"],
        ["img 1.66:1 ······", "1312", "792"],
        ["img 16:9 #1 ····", "1360", "768"],
        ["img 16:9 #2 ····", "1920", "1088"],
        ["img 16:9 #3 ····", "2176", "1216"],
        ["img 16:9 MJ6 ···", "1456", "816"],
        ["img 1.85:1 ······", "1392", "752"],
        ["img 2:1 #1 ······", "2048", "1024"],
        ["img 2:1 MJ6 ·····", "1536", "768"],
        ["img 2.35:1 ······", "1568", "664"],
        ["img 2.39:1 ······", "1576", "656"],
        ["vid AI 16:9 #1 ·", "1280", "720"],
        ["vid AI 16:9 #2 ·", "960", "544"],
        ["vid AI 16:9 #3 ·", "832", "480"],
        ["vid AI 16:9 #4 ·", "800", "448"],
        ["vid AI 16:9 #5 ·", "400", "224"],
        ["vid AI 3:2 #1 ···", "768", "512"],
        ["vid AI 3:2 #2 ···", "720", "480"],
        ["vid 360 SD #1 ··", "640", "360"],
        ["vid 480 SD #2 ··", "854", "480"],
        ["vid 480 SD #3 ··", "720", "480"],
        ["vid 3_8 HD ······", "480", "270"],
        ["vid 3_4 HD ······", "960", "540"],
        ["vid HD ············", "1280", "720"],
        ["vid FHD ··········", "1920", "1080"],
        ["vid 2k ············", "2560", "1440"],
        ["vid 4k ············", "3840", "2160"]
];

function getAspectStr(i) { // make dropbox string
	return AspectsIn[i][0] + "··· " + AspectsIn[i][1] + " x " + AspectsIn[i][2];
}

function fillAspectsDisp() { // make aspects array for dropbox display
	let items = [""];
	for (let i = 0; i < AspectsIn.length; i++) {
	    items.push(getAspectStr(i));
	}
	return items;
}

let AspectsDisp = fillAspectsDisp(); // aspect combobox content

// /////////////////////////////////////////////////////////////////////////////////////

async function fillProjCodes() {
    try {
        // resolve against current document — handles default localhost AND path-prefix reverse proxies
        const response = await fetch(new URL("extensions/ComfyUI-GU_Nodepack/proj_codes.txt", document.baseURI));
        if (!response.ok) throw new Error(`>>>>>>> Error loading project codes file: ${response.statusText}`);
        const text = await response.text();
        const lines = text.split(/\r?\n/); // \n + \r\n
        const validLines = lines.filter(line => !line.trimStart().startsWith("#")); // ignore #-commented lines
        return validLines;
    } catch (error) {
        console.error(">>>>>>> Error reading project codes: ", error);
        return [];
    }
}

let ProjCodes = [""];
fillProjCodes().then(lines => ProjCodes = lines);

// /////////////////////////////////////////////////////////////////////////////////////

async function fillModelCodes() {
    try {
        // resolve against current document — handles default localhost AND path-prefix reverse proxies
        const response = await fetch(new URL("extensions/ComfyUI-GU_Nodepack/model_codes.txt", document.baseURI));
        if (!response.ok) throw new Error(`>>>>>>> Error loading model codes file: ${response.statusText}`);
        const emp = [""];
        const text = await response.text();
        const validLines = text
            .split(/\r?\n/) // \n + \r\n
            .map(line => line.split('#', 1)[0].trimEnd())  // only before first #
            .filter(line => line.trimStart() !== "");
        return emp.concat(validLines);
    } catch (error) {
        console.error(">>>>>>> Error reading project codes: ", error);
        return [""];
    }
}

let ModelCodes = [""];
fillModelCodes().then(lines => ModelCodes = lines);

// /////////////////////////////////////////////////////////////////////////////////////
// /////////////////////////////////////////////////////////////////////////////////////
// /////////////////////////////////////////////////////////////////////////////////////

app.registerExtension({
	name: "GU_Nodepack.jsnodes",
	async beforeRegisterNodeDef(nodeType, nodeData, app) {
		if(!nodeData?.category?.startsWith("GU_Nodepack")) {
			return;
		}

        const originalOnNodeCreated = nodeType.prototype.onNodeCreated || function() {};
        const originalOnRemoved = nodeType.prototype.onRemoved;

		switch (nodeData.name) {
			case "G_ConcatStr": // /////////////////////////////////////////////////////////////////////////////////////
				nodeType.prototype.onNodeCreated = function () {
				    if (!this.inputs) this.inputs = [];

                    this.InUpdate = function() {
                        const init_inputs = this.inputs.length;
                        const target_inputs = this.widgets.find(w => w.name === "inputs")["value"] + 3; // !!! fix for ver 2d6805c

                        if (target_inputs === init_inputs) return; // already set, do nothing

                        if (target_inputs < init_inputs) {
                            for(let i = init_inputs; i >= target_inputs; i--)
                                this.removeInput(i);
                        }
                        else {
                            for(let i = init_inputs + 1; i <= target_inputs; ++i)
                                this.addInput(`str_${i - 3}`, "STRING"); // !!! fix for 2d6805c
                        }
                    }

				    this.addWidget("button", "Update inputs", null, () => {this.InUpdate();});
                    this.InUpdate(); // first call on creation
				};
				break;

			case "G_ResSelect": // /////////////////////////////////////////////////////////////////////////////////////
				nodeType.prototype.onNodeCreated = function () {
					originalOnNodeCreated.apply(this, arguments);

                    //getAspectStr(0)
                    const wAspect = this.addWidget("combo", "aspect", "", (e) => {this.onChangeAspect();}, {
                        values: AspectsDisp,
                    });

                    this.onChangeAspect = function() {
					    let w = 1024;
					    let h = 1024;
                        for (let i = 0; i < AspectsIn.length; i++) {
                            if (this.widgets.find(w => w.name === "aspect")["value"] == AspectsDisp[i+1]) { //+1 because blank str
                                w = AspectsIn[i][1];
                                h = AspectsIn[i][2];
                            }
                        }
                        this.widgets.find(x => x.name === "width")["value"] = w;
                        this.widgets.find(x => x.name === "height")["value"] = h;
                    }
				};
				break;

			case "G_TextEdit": // /////////////////////////////////////////////////////////////////////////////////////
                nodeType.prototype.onNodeCreated = function () {
                    const info = this.widgets.find(w => w.name === "only");
                    if (info) info.disabled = true;

                    const widgetEdit = "text_ed";

                    const populate = (textArr) => {
                        const protectWidget = this.widgets.find(w => w.name === "protect");
                        const isProtected = protectWidget?.value === true;
                        if (isProtected) return; // don't restore protected text!

                        // remove previous text_ed
                        this.widgets = this.widgets.filter(w => w.name !== widgetEdit);
                        if (Array.isArray(this.widgets_values)) {
                            this.widgets_values = this.widgets_values.filter((_, i) => this.widgets[i]?.name !== widgetEdit);
                        }

                        for (const txt of textArr) {
                            const widget = ComfyWidgets["STRING"](this, widgetEdit, ["STRING", { multiline: true }], app).widget;
                            widget.value = txt;
                        }

                        requestAnimationFrame(() => {
                            const sz = this.computeSize();
                            this.onResize?.(sz);
                            app.graph.setDirtyCanvas(true, false);
                        });
                    };

                    // intercept execution
                    const originalExecuted = nodeType.prototype.onExecuted;
                    nodeType.prototype.onExecuted = function (message) {
                        originalExecuted?.apply(this, arguments);
                        if (message.text) {
                            populate.call(this, message.text);
                        }
                    };

                    // intercept recovery
                    const originalConfigure = nodeType.prototype.onConfigure;
                    nodeType.prototype.onConfigure = function () {
                        originalConfigure?.apply(this, arguments);
                        if (Array.isArray(this.widgets_values)) {
                            const textWidgets = this.widgets_values
                                .map((v, i) => ({ name: this.widgets[i]?.name, value: v }))
                                .filter(w => w.name === widgetEdit)
                                .map(w => w.value);
                            if (textWidgets.length > 0) {
                                populate.call(this, textWidgets);
                            }
                        }
                    };

                    // cleanup ?
                    nodeType.prototype.onRemoved = function () {
                        if (this._textEditInterval) {
                            clearInterval(this._textEditInterval);
                            this._textEditInterval = null;
                        }
                        originalOnRemoved?.apply(this, arguments);
                    };
                };
				break;

			case "G_ProjName": // /////////////////////////////////////////////////////////////////////////////////////
				nodeType.prototype.onNodeCreated = function () {
					originalOnNodeCreated.apply(this, arguments);

                    const wAspect = this.addWidget("combo", "actual_proj_code", "", (e) => {this.onChangeProj();}, {
                        values: ProjCodes,
                    });

                    this.onChangeProj = function() {
                        for (let i = 0; i < ProjCodes.length; i++) {
                            if (this.widgets.find(w => w.name === "actual_proj_code")["value"] == ProjCodes[i]) {
                                this.widgets.find(x => x.name === "project")["value"] = ProjCodes[i];
                            }
                        }
                    }
				};
				break;

			case "G_ProjPath": // /////////////////////////////////////////////////////////////////////////////////////
				nodeType.prototype.onNodeCreated = function () {
					originalOnNodeCreated.apply(this, arguments);

                    var s = this.widgets.find(w => w.name === "stub");
                    if (s) {
                        s.hidden = true;
                    }

                    const wAspect = this.addWidget("combo", "model_type_select", "", (e) => {this.onChangeModel();}, {
                        values: ModelCodes,
                    });

                    this.onChangeModel = function() {
                        for (let i = 0; i < ModelCodes.length; i++) {
                            if (this.widgets.find(w => w.name === "model_type_select")["value"] == ModelCodes[i]) {
                                this.widgets.find(x => x.name === "model_type")["value"] = ModelCodes[i];
                            }
                        }
                    }
				};
				break;

            case "G_LoraStackExt": // /////////////////////////////////////////////////////////////////////////////////////
			case "G_MotionLoraStack": // similar structure!
				nodeType.prototype.onNodeCreated = function () {
					originalOnNodeCreated.apply(this, arguments);

                    //console.log("Список атрибутов s:", Object.keys(s));
                    //0: "linkedWidgets"
                    //1: "name"
                    //2: "options"
                    //3: "label"
                    //4: "type"
                    //5: "y"
                    //6: "last_y"
                    //7: "width"
                    //8: "disabled"
                    //9: "computedDisabled"
                    //10: "hidden"
                    //11: "advanced"
                    //12: "tooltip"
                    //13: "element"
                    //14: "callback"
                    //15: "dynamicPrompts"
                    // turn s0..s5 into silent vertical spacers between lora blocks.
                    // modern ComfyUI collapses widgets with .hidden=true fully (no layout slot),
                    // so we leave them visible but override draw=noop and computeSize=fixed height.
                    for (let i = 0; i <= 5; i++) {
                        const s = this.widgets.find(w => w.name === `s${i}`);
                        if (s) {
                            s.hidden = false;
                            s.draw = function() {};  // render nothing
                            s.computeSize = function() { return [0, 10]; };  // reserve 10px gap
                        }
                    }
				};
				break;

			case "G_SwitchAnyIndex": // /////////////////////////////////////////////////////////////////////////////////////
				nodeType.prototype.onNodeCreated = function () {
				    if (!this.inputs) this.inputs = [];

                    this.InUpdate = function() {
                        const init_inputs = this.inputs.length;
                        const target_inputs = this.widgets.find(w => w.name === "inputs")["value"] + 2; // !!! fix for ver 2d6805c

                        if (target_inputs === init_inputs) return; // already set, do nothing

                        if (target_inputs < init_inputs) {
                            for(let i = init_inputs; i >= target_inputs; i--)
                                this.removeInput(i);
                        }
                        else {
                            for(let i = init_inputs + 1; i <= target_inputs; ++i)
                                this.addInput(`any_${i - 2}`, "*"); // !!! fix for 2d6805c
                        }
                    }

				    this.addWidget("button", "Update inputs", null, () => {this.InUpdate();});
                    this.InUpdate(); // first call on creation
				};
				break;

			case "G_GetSampIndex": // /////////////////////////////////////////////////////////////////////////////////////
            case "G_GetSchedIndex": // similar structure!
				nodeType.prototype.onNodeCreated = function () {
					originalOnNodeCreated.apply(this, arguments);

                    const total = this.widgets.find(w => w.name === "total");
                    if (total) total.disabled = true;

                    const s_list = this.widgets.find(w => w.name === "s_list");
                    const index = this.widgets.find(w => w.name === "index");

                    //console.log(">>>>>>>>>>>>>>>");
                    //console.log("s_list:", s_list);  // s_list: Object { linkedWidgets: undefined, name: "s_list", options: {…}, label: "s_list", type: "combo", y: 0, last_y: undefined, width: undefined, disabled: undefined, computedDisabled: undefined, … }
                    //console.log("s_list.options:", s_list.options);  // s_list.options: Object { values: (38) […], advanced: undefined, hidden: undefined }
                    //console.log("s_list.widget:", s_list.widget);  // s_list.widget: undefined
                    if (!s_list || !index) {
                        console.warn(">>>>>>> s_list or index not found or invalid!");
                        return;
                    }

                    const optionsArray = s_list.options?.values;
                    if (!Array.isArray(optionsArray)) {
                        console.warn(">>>>>>> s_list.options.values is not an array!");
                        return;
                    }

                    let updating = false; // prevent cycles!
                    let lastIndexValue = index.value;

                    // sync: s_list -> index
                    const syncListToIndex = () => {
                        //console.log(">>>>>>> 1a");
                        if (updating) return;
                        //console.log(">>>>>>> 1b");
                        updating = true;
                        const i = optionsArray.indexOf(s_list.value);
                        if (i !== -1) {
                            index.value = i + 1; // for UI
                            lastIndexValue = index.value;
                        }
                        updating = false;
                        //console.log(">>>>>>> 1c");
                    };

                    // sync: index -> s_list
                    const syncIndexToList = () => {
                        //console.log(">>>>>>> 2a");
                        if (updating) return;
                        //console.log(">>>>>>> 2b");
                        updating = true;
                        const i = parseInt(index.value);
                        if (!isNaN(i) && i >= 1 && i <= optionsArray.length) {
                            const newValue = optionsArray[i - 1];
                            if (s_list.value !== newValue) {
                                s_list.value = newValue;
                            }
                        }
                        updating = false;
                        //console.log(">>>>>>> 2c");
                    };

                    s_list.callback = syncListToIndex; // s_list change

                    // index change — use callback instead of setInterval polling
                    const origIndexCallback = index.callback;
                    index.callback = (...args) => {
                        if (origIndexCallback) origIndexCallback.apply(this, args);
                        syncIndexToList();
                    };

                    syncListToIndex();
				};
                nodeType.prototype.onRemoved = function () {
                    //console.log(">>>>>>> rem1");
                    if (originalOnRemoved) {
                        //console.log(">>>>>>> rem2");
                        originalOnRemoved.apply(this, arguments);
                    }
                };
				break;

            /**/
			case "": // /////////////////////////////////////////////////////////////////////////////////////
				break;
            /**/
		}
	},

	async setup() {
		const originalComputeVisibleNodes = LGraphCanvas.prototype.computeVisibleNodes;
		LGraphCanvas.prototype.computeVisibleNodes = function () {
			const visibleNodesSet = new Set(originalComputeVisibleNodes.apply(this, arguments));
			return Array.from(visibleNodesSet);
		};
	},
});

