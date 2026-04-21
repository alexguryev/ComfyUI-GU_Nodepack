// GU_Nodepack (C) Alexander Guryev, 2026 | https://alexguryev.com

import { app } from "../../../scripts/app.js";

app.registerExtension({
    name: "GU_Nodepack.appearance",
        async nodeCreated(node) {
            if (node.comfyClass.startsWith("G_")) {
                node.color = "#31496d";
                node.bgcolor = "#273a58";
            }
        }
});
