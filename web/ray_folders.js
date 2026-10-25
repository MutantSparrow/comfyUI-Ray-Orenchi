import { app } from "../../scripts/app.js";
import { setWidgetHidden } from "./_common.js";
import { createGallery } from "./folders_gallery.js";
import { installOutputLane } from "./output_lane.js";

app.registerExtension({
    name:"Ray.Folders",
    async beforeRegisterNodeDef(nodeType,nodeData) {
        if(nodeData.name!=="RayFolders")return;
        const proto=nodeType.prototype,created=proto.onNodeCreated;
        proto.onNodeCreated=function(){
            const result=created?.apply(this,arguments);this.color=this.bgcolor="#000000";
            if(!this.addDOMWidget)return result;
            this._rayFolders=createGallery(this);
            for(const name of ["folder","name_filter","selected_files","settings_json"])setWidgetHidden(this,this.widgets?.find(w=>w.name===name),true);
            this.addDOMWidget("ray_folders_gallery","RAY_FOLDERS",this._rayFolders.root,{
                serialize:false,hideOnZoom:false,margin:4,getMinHeight:()=>260,getHeight:()=>480,
            });
            this._rayFoldersOutputLane=installOutputLane(this,this._rayFolders.root);
            this.setSize?.([Math.max(this.size?.[0]||0,460),Math.max(this.size?.[1]||0,570)]);
            return result;
        };
        for(const event of ["onConfigure","onConnectionsChange"]) {
            const prior=proto[event];proto[event]=function(){const result=prior?.apply(this,arguments);this._rayFolders?.sync(event==="onConfigure");this._rayFoldersOutputLane?.refresh();return result;};
        }
        const executed=proto.onExecuted;
        proto.onExecuted=function(message){const result=executed?.apply(this,arguments);if(message.ray_folders?.[0])this._rayFolders?.executed(message.ray_folders[0]);return result;};
        const removed=proto.onRemoved;
        proto.onRemoved=function(){this._rayFoldersOutputLane?.destroy();this._rayFolders?.destroy();return removed?.apply(this,arguments);};
    },
});
