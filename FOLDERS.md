# Ray - Folders

`📁 Ray - Folders` (`RayFolders`) lives under `👑 Ray/🔧 Tools`.
Restart ComfyUI and refresh its browser after installing the feature.

Choose a local folder using the pack's folder picker, paste a path, or connect a
STRING to **folder**. **name_filter** accepts a fuzzy filename query, either typed
or connected. Multiple query words must match. A connected value is resolved on
the next workflow run and displayed in the field.

The resizable gallery only mounts visible tiles plus two buffer rows above and
below the viewport. A folder spinner appears during directory scanning; individual
tiles show spinners until their previews and active filters finish. At most four
previews load concurrently (two when color/NSFW checks are active). Scrolling
cancels obsolete requests and loads the next window. A bounded session cache
retains recently visited thumbnails across scrolling and folder refreshes; the
server also caches generated JPEGs by file revision.
Images and video posters are generated on demand; audio tiles show artwork or a waveform. Full-size files are
loaded only for viewing, copying, dragging, or selected workflow outputs. The
quiet bottom note reports total images, videos and audio files, independently of
the filename and media-type filters. With recursion on, totals include subfolders.

## Selection and outputs

Click selects one file; Ctrl-click (Cmd-click on macOS) toggles additional files.
Clicking the sole selected file again clears it. Selection follows gallery sort
order, is saved with the workflow, and is pruned when files disappear or a filter
excludes them. Changing folders does not carry selections to the new folder.

All outputs are ComfyUI **lists**, not concatenated tensors:

| Output | Contents |
|---|---|
| `images` · IMAGE | Selected images at their original dimensions, one image per list item. |
| `videos` · VIDEO | Selected native ComfyUI video objects, including their original embedded audio. |
| `audio` · AUDIO | Selected audio waveforms with original sample rates. |
| `prompt` · STRING | One prompt per successfully loaded selected file, blank when no prompt exists. |
| `paths` · STRING | The corresponding absolute file paths. With no selection, a single folder path. |

For mixed selections each media output contains only its own type; `prompt` and
`paths` contain the entire selection in gallery order. Their lengths therefore
need not match an individual media output. Empty media outputs are empty lists;
there is no dummy black image or silent audio. All sockets can remain disconnected.

The node is an output node and refreshes the listing on every workflow execution.
Files added, removed or renamed outside ComfyUI appear on the next refresh or run.
The refresh icon also rescans immediately. Deleted/unreadable files are skipped;
an unavailable folder or disconnected drive clears media outputs and shows a
recoverable error. Reconnect the drive and press refresh. Thumbnail and metadata
cache keys include modification time and size; text sidecar changes also invalidate
metadata. Symbolic links outside the opened folder are not followed.

## Settings

The cog opens settings for images/video/audio, name/date-modified/file-size sorting
in either direction, recursion, 2–7 thumbnail columns, color groups, NSFW filtering,
best-prompt extraction, and single-line/multiline prompt formatting. Settings are
saved per node in the workflow.

Prompt extraction reuses Prompt Scraper's PNG generation parameters, ComfyUI graphs,
EXIF and `.txt` sidecar heuristics. Best match keeps the longest valid positive
prompt. With best match off, candidates are joined into one string for that file.
Video/audio container tags and `.txt` sidecars are checked too. The scraper's
random-selection and repeat-skipping behavior does not apply to manual selections.

Color and NSFW checks are lazy too: only the scrolling window is checked.
Unvisited files appear as concealed placeholders and the status reports the
remaining pending count. Files rejected by the active filters disappear as their
checks finish. Files awaiting classification are excluded from workflow outputs
until they qualify. Saved selections reuse cached analysis when available.
If an entire window is filtered out, checking pauses rather than scanning the
rest of the folder automatically. Scroll or press **Load more** to continue.

Color filtering adapts FastGallery's centre-weighted 32×32 HSL groups. NSFW filtering
uses a locally served NSFWJS MobileNet V2 Mid quantized model, loaded only when
enabled. It can hide NSFW or show only NSFW, with a 1–99% score threshold. Lower
thresholds hide more files, including more false positives. The Sexy category is
included by default; workflows that explicitly disabled it retain that setting.
Regional checks are enabled by default: the full thumbnail and five overlapping
70% crops are classified, using the highest combined Porn + Hentai (+ Sexy, when
enabled) score from any view. This costs up to six inferences per uncached image;
turn off **Check image regions** for the faster full-thumbnail pass. Scores are
model estimates, not a guarantee that content is safe. Hover details show the
score used by the filter. Press Apply to use changed settings.
Classification runs in the browser and results are cached
in IndexedDB by file revision. Images and **video poster frames** are analyzed;
this is not a scan of every video frame. Audio is controlled by the media-type
checkbox. No media is sent to an outside classification service.

## Interactions

- Double-click opens a viewer centered at 75% of the viewport's width and height.
  Click anywhere to close an image; video/audio expose playback controls and close
  on backdrop click or Escape.
- Hover shows filename, modification date, dimensions/duration and prompt presence.
  Hold Shift to see the prompt, then release to return to file details.
- Right-click offers Copy image, Copy prompt and Copy ComfyUI workflow. Missing
  metadata disables the corresponding action. Clipboard access uses the browser's
  normal clipboard permissions.
- Drag an image onto the canvas to create Load Image, or onto an existing Load
  Image to replace it. A copy is imported into ComfyUI's input directory; the source
  file is not moved. Source generation metadata is retained in the imported file.

## Development checks

Run `tests/test_folders.py` using pytest and ComfyUI's Python environment.
`tests/serve_folders.py [port]` serves the real HTTP routes with generated disposable
image/video/audio fixtures; open `/tests/folders_browser.html` for interaction,
virtualization, error recovery and real local model-inference checks. It does not
modify the user's media folders.

Offline classifier rebuilding and license information are in
`scripts/build_folders_nsfw.cjs` and `web/vendor/nsfw/NOTICE.md`.
