Ray - Folders uses NSFWJS 4.4.0 (MIT) and TensorFlow.js 4.22.0 (Apache-2.0).
The locally served MobileNet V2 Mid model is the quantized ~4.2 MB variant
distributed by NSFWJS, not the substantially larger Inception model.

Runtime source: https://github.com/infinitered/nsfwjs
TensorFlow.js: https://github.com/tensorflow/tfjs
Model source: nsfwjs@4.4.0/dist/models/mobilenet_v2_mid from the npm package.
License texts are included alongside these assets.

The model and runtime load only when an NSFW filter is enabled. Classification
runs inside the browser; media is not sent to an external classification service.
Video classification uses the thumbnail frame, not every frame of the video.

To rebuild from pinned registry packages, use scripts/build_folders_nsfw.cjs.
