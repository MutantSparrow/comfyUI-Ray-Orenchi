# Pixel Art Fixer detector

Vendored from https://github.com/Retro-Diffusion/pixel-art-fixer
at revision `ef376e57e1c272633ca2dbf5f29ec3fcf6596465`.

Copyright (c) 2026 Astropulse, LLC. MIT license; see LICENSE.

Only the detector and its required modules are included. The CLI, server API
and reconstruction code are not included. Ray's node supplies its own input
handling, exact-aspect sizing, reconstruction, palette/effects and output.

Local modification: `quantize.py` assigns labels in chunks of 16,384 pixels
instead of 1,048,576, limiting temporary allocation without changing the
distance calculation. No remote service or model is used at runtime.
