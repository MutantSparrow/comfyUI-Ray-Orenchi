"""Local comparison harness. No private images or network requests."""
import json, sys, time, subprocess
from pathlib import Path
import numpy as np
import torch
from PIL import Image
from threadpoolctl import threadpool_limits

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]))
sys.path.insert(0,str(HERE/'.references/pixel-art-fixer-main/python'))
from pixelfixer import detect
from pixelfixer.reconstruct import two_stage_pack
import previous_pixel as old
import ray_pixel_detector as new


def rgb(path): return np.array(Image.open(path).convert('RGB'),dtype=np.float32)/255
def metrics(out, truth):
    same=out.shape==truth.shape
    aligned=out if same else np.asarray(Image.fromarray(np.rint(out*255).astype(np.uint8)).resize((truth.shape[1],truth.shape[0]),Image.Resampling.NEAREST),dtype=np.float32)/255
    a,b=old.oklab(aligned),old.oklab(truth)
    edges=lambda x: np.concatenate([np.linalg.norm(np.diff(x,axis=i),axis=-1).ravel()>.04 for i in [0,1]])
    ea,eb=edges(a),edges(b); tp=(ea&eb).sum()
    return {'exact_size':same,'oklab_error':float(np.linalg.norm(a-b,axis=-1).mean()),
            'edge_f1':float(2*tp/max(ea.sum()+eb.sum(),1)), 'width':out.shape[1], 'height':out.shape[0]}


def main():
    from fixtures import write_fixtures
    import cv2
    jobs=write_fixtures(HERE/'fixtures')
    (HERE/'jobs.json').write_text(json.dumps(jobs))
    folder=HERE/'baseline_outputs'; folder.mkdir(exist_ok=True)
    results=[]; snapper_jobs=[]
    for job in jobs:
        for kind in ['auto','known']:
            snapper_jobs.append({'id':job['id']+'-'+kind,'input':job['input'],
                'output':str(folder/(job['id']+'-spritefusion-'+kind+'.png')),
                'colors':32,'step':None if kind=='auto' else Image.open(job['input']).width/job['size'][0]})
    (HERE/'snapper_jobs.json').write_text(json.dumps(snapper_jobs))
    r=subprocess.run(['node',str(HERE/'run_snapper.cjs'),str(HERE/'snapper_jobs.json')],capture_output=True,text=True)
    if r.returncode:
        raise RuntimeError('Spritefusion runner failed; no cached outputs will be scored.\n'+r.stderr)
    snapper_times={x['id']:x for line in r.stdout.splitlines() if line.startswith('{') for x in [json.loads(line)]}
    for job in jobs:
        x,truth=rgb(job['input']),rgb(job['original']); tensor=torch.from_numpy(x)[None]
        rgba=np.dstack([np.rint(x*255).astype(np.uint8),np.full(x.shape[:2],255,np.uint8)])
        print(job['id'],flush=True)
        methods={
          'nearest-known':lambda: old.sample_image(x,truth.shape[:2],'nearest'),
          'area16-known':lambda: old.RayPixelArtDetector().process(tensor,target_resolution=max(job['size']),sampling='area',max_colors=16,seed=42)[0][0].numpy(),
          'previous-known':lambda: old.RayPixelArtDetector().process(tensor,target_resolution=max(job['size']),reduce_palette=False,seed=42)[0][0].numpy(),
          'previous-auto':lambda: old.RayPixelArtDetector().process(tensor,mode='auto_pixel_size',target_resolution=128,reduce_palette=False,seed=42)[0][0].numpy(),
          'ray-known':lambda: new.RayPixelArtDetector().process(tensor,target_resolution=max(job['size']),reduce_palette=False,seed=42)[0][0].numpy(),
          'ray-auto':lambda: new.RayPixelArtDetector().process(tensor,mode='auto_pixel_size',target_resolution=128,reduce_palette=False,seed=42)[0][0].numpy(),
          'pixelfixer-known':lambda: two_stage_pack(rgba,*job['size'])[...,:3].astype(np.float32)/255,
        }
        for name,fn in methods.items():
            start=time.perf_counter()
            cv2.setRNGSeed(42)
            with threadpool_limits(limits=1): out=fn()
            results.append({'id':job['id'],'kind':job['kind'],'method':name,'seconds':time.perf_counter()-start,**metrics(out,truth)})
            Image.fromarray(np.clip(np.rint(out*255),0,255).astype(np.uint8)).save(folder/(job['id']+'-'+name+'.png'))
        start=time.perf_counter()
        try:
            with threadpool_limits(limits=1):
                grid=detect(rgba,mode='full',low_memory=True)
                cv2.setRNGSeed(42)
                out=two_stage_pack(rgba,grid['cols'],grid['rows'])[...,:3].astype(np.float32)/255
            results.append({'id':job['id'],'kind':job['kind'],'method':'pixelfixer-auto','seconds':time.perf_counter()-start,**metrics(out,truth),'consensus':grid['consensus']})
            Image.fromarray(np.rint(out*255).astype(np.uint8)).save(folder/(job['id']+'-pixelfixer-auto.png'))
        except Exception as e: results.append({'id':job['id'],'method':'pixelfixer-auto','error':str(e)})
        for kind in ['known','auto']:
            path=folder/(job['id']+'-spritefusion-'+kind+'.png')
            timing=snapper_times.get(job['id']+'-'+kind,{})
            if path.exists() and 'seconds' in timing and 'error' not in timing:
                results.append({'id':job['id'],'kind':job['kind'],'method':'spritefusion-'+kind,
                                'seconds':timing['seconds'],**metrics(rgb(path),truth)})
            else:
                results.append({'id':job['id'],'kind':job['kind'],'method':'spritefusion-'+kind,
                                'error':timing.get('error','No current successful output')})
        (HERE/'baseline_results.json').write_text(json.dumps(results,indent=2))
    for name in sorted({r['method'] for r in results}):
        items=[r for r in results if r['method']==name and 'exact_size' in r]
        print(name, len(items), sum(r['exact_size'] for r in items), np.mean([r['oklab_error'] for r in items]),flush=True)


if __name__=='__main__': main()
