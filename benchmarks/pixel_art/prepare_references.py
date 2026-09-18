"""Explicit benchmark setup; never imported or run by the ComfyUI node."""
import hashlib,io,zipfile
from pathlib import Path
import requests

root=Path(__file__).resolve().parent/'.references'
root.mkdir(exist_ok=True)
commit='ef376e57e1c272633ca2dbf5f29ec3fcf6596465'
r=requests.get(f'https://codeload.github.com/Retro-Diffusion/pixel-art-fixer/zip/{commit}',timeout=60)
r.raise_for_status()
with zipfile.ZipFile(io.BytesIO(r.content)) as archive:
    for member in archive.infolist():
        relative=Path(*Path(member.filename).parts[1:])
        if not relative.parts or member.is_dir(): continue
        if relative.parts[0]!='python' and relative.name!='LICENSE': continue
        target=(root/'pixel-art-fixer-main'/relative).resolve()
        if not target.is_relative_to(root.resolve()): raise ValueError('Unsafe archive path')
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(archive.read(member))
assets=[
 ('snapper_worker.js','https://www.spritefusion.com/_app/immutable/workers/worker-CVhXJnTr.js','c9d904afbd7f5c710f8c4104b702a4dcacad4c1f15f19d4cc3bb7166465fc488'),
 ('snapper.wasm','https://www.spritefusion.com/_app/immutable/workers/assets/spritefusion_pixel_snapper_bg-DfSbmZKz.wasm','f8533cecd6eaa8dd45d489d77a9502ba90403bd14f6154c41900666cb656798d')]
for name,url,expected in assets:
    r=requests.get(url,timeout=30);r.raise_for_status()
    if hashlib.sha256(r.content).hexdigest()!=expected: raise ValueError(f'{name} changed; review benchmark version before updating')
    (root/name).write_bytes(r.content)
print('Pinned reference engines ready. No ComfyUI runtime files or packages were changed.')
