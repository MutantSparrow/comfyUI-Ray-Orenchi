# FastVLM reliability update

The shared Qwen3-VL 4B encoder loaded with `type=krea2` is retained. No second model, checkpoint conversion, or core ComfyUI change is introduced.

## Findings

Using the user's long caption prompt, same 4B/Krea2 CLIPLoader and same preview image, the unmodified native generation path also repeated a sentence until the 1024-token ceiling. The issue is therefore reproducible without FastVLM graphs. Both paths described image-specific content in this test; the separate “I cannot see the image” response was not reproduced.

The previous node delegated `thinking=false` to Comfy's tokenizer, which appends an artificial completed `<think>` block. Qwen3-VL Instruct's [official chat template](https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct/blob/main/chat_template.json) instead ends the generation prefix at the assistant header. Removing that block in an isolated live comparison eliminated the exact repeated tail for that test, although it did not eliminate all verbosity or invented details.

## Changes

- Use the official simple image/user/assistant layout for Instruct, without an invented reasoning prefill. Native image placeholder replacement and image preprocessing are retained.
- Verify that every supplied image has a corresponding image embedding token before generation. If not, fail clearly instead of silently generating a text-only answer.
- Add device-side presence and repetition penalties to the fast loop, retaining native block graphs and the shared model. There is no slow fallback to the original loop when penalties are requested.
- Default presence penalty to 1.5 and repetition penalty to 1.0, following the Qwen team's [Instruct generation settings](https://github.com/QwenLM/Qwen3-VL#evaluation-reproduction). For Thinking checkpoints, set presence penalty to 0.
- Add an optional exact-loop guard in fast mode: if an identical phrase of 8–256 tokens repeats three times, stop and keep its first copy. This is a truncation safeguard, not a guarantee of a complete answer or an accuracy check.
- Log image attachment count and whether the answer ended on EOS, hit the token ceiling, or was stopped by the loop guard.
- Resolve original dynamic block registration through the original patcher, avoiding repeated wrapping of a prior FastVLM patch.

## Use

Restart ComfyUI to load the updated module. Keep the 4B CLIPLoader set to `krea2` and use the same CLIP output for Krea conditioning and FastVLM. Suggested Instruct settings: temperature 0.7, top-p 0.8, top-k 20, presence penalty 1.5, repetition penalty 1.0, thinking false, repeat guard true. Existing temperature/top-p/top-k widget values are not overwritten by the update.

`max_tokens=1024` remains a ceiling. EOS can finish the response sooner. The node cannot force a model to emit EOS naturally or make every visual claim accurate. The long checklist prompt requests details that may not be visible or applicable (for example human skin/face anatomy on a pixel-art skeleton); omitting inapplicable details should be stated directly, and a shorter prompt can reduce pressure to invent them.

The update passed 18 tests, including real Krea2 tokenizer attachment for two images, exact Instruct prefix, dropped-image rejection, penalty math, stopping far below a 1024-token limit, loop stopping, cancellation and graph-buffer cleanup. New full-model penalty performance has not yet been benchmarked; the earlier 8B speed measurements are not a new measurement of this revision. The user's running ComfyUI session was not restarted automatically.
