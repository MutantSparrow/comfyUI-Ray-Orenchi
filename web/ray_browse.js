import { app } from "../../scripts/app.js";
import { addBrowseButton, IMAGE_FILTERS } from "./browse_common.js";

// A Browse button under every folder or file path in the pack that does not need special handling. (Save
// Image and the Prompt Scraper add theirs themselves.)
const BROWSE = {
    RayVLMFolder: [["folder", { kind: "folder", title: "Choose a folder of images" }]],
    RayTextFolder: [["directory", { kind: "folder", title: "Choose a folder of .txt prompts" }]],
    RayFilmStock: [["assets_folder", { kind: "folder", title: "Choose a folder of LUTs and XMP presets" }]],
    RayMetaInspect: [["path", { kind: "file", title: "Choose an image", filters: IMAGE_FILTERS }]],
};

app.registerExtension({
    name: "Ray.Browse",
    async beforeRegisterNodeDef(nodeType, nodeData) {
        const buttons = BROWSE[nodeData.name];
        if (!buttons) return;
        const created = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function (...args) {
            const result = created?.apply(this, args);
            for (const [name, options] of buttons) addBrowseButton(this, name, options);
            return result;
        };
    },
});
