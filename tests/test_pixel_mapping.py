import unittest
import numpy as np
import torch
from ray_pixel_detector import quantize, oklab, RayPixelArtDetector
from ray_pixel_mapping import legacy_oklab


class PaletteMappingTests(unittest.TestCase):
    def test_original_formula_reference(self):
        # Independent double-precision implementation of original Torch mapper.
        rgb=np.array([[0,0,0],[.015,.025,.03],[.08,.06,.1],[.8,.5,.2],[1,1,1]],np.float32)
        x=torch.from_numpy(rgb).double()
        linear=torch.where(x<=.04045,x/12.92,((x+.055)/1.055)**2.4)
        m1=torch.tensor([[.4122214708,.5363325363,.0514459929],[.2119034982,.6806995451,.1073969566],[.0883024619,.2817188376,.6299787005]],dtype=torch.float64)
        m2=torch.tensor([[.2104542553,.7936177850,-.0040720468],[1.9779984951,-2.4285922050,.4505937099],[.0259040371,.7827717662,-.8086757660]],dtype=torch.float64)
        lms=linear@m1.T
        transformed=torch.where(lms>(6/29)**3,lms**(1/3),lms/(3*(6/29)**2)+4/29)
        expected=transformed@m2.T
        expected[:,0]=(expected[:,0]-4/29)/(1-4/29)
        np.testing.assert_allclose(legacy_oklab(rgb),expected.numpy(),atol=2e-7)
        self.assertFalse(np.allclose(legacy_oklab(rgb),oklab(rgb)))

    def test_rgb_distance_and_explicit_mapping_change_assignments(self):
        rng=np.random.default_rng(42)
        rgb=rng.random((16,16,3),dtype=np.float32)
        p=rng.random((8,3),dtype=np.float32)
        expected=p[((rgb[:,:,None]-p)**2).sum(-1).argmin(-1)]
        out=quantize(rgb,p,'none',0,mapping_strategy='rgb')
        np.testing.assert_array_equal(out,expected)
        self.assertTrue(np.any(out!=quantize(rgb,p,'none',0,mapping_strategy='oklab')))

    def test_auto_preserves_existing_mapping(self):
        rng=np.random.default_rng(3)
        rgb=rng.random((8,8,3),dtype=np.float32)
        p=rng.random((8,3),dtype=np.float32)
        for family in (True,False):
            np.testing.assert_array_equal(quantize(rgb,p,'none',0,family),
                quantize(rgb,p,'none',0,mapping_strategy='color_families' if family else 'oklab'))

    def test_supplied_palette_exact_for_all_mappings_and_dithers(self):
        rng=np.random.default_rng(8)
        rgb=np.broadcast_to(np.linspace(.1,.9,40,dtype=np.float32)[None,:,None],(8,40,3)).copy()
        palette=np.array([[.05,.1,.2],[.4,.4,.4],[.7,.5,.3],[.95,.95,.9]],np.float32)
        node=RayPixelArtDetector()
        for mapping in ('auto','legacy_oklab','oklab','lab','rgb','color_families'):
            for dither in ('none','ordered','error_diffusion'):
                out,_=node.process(torch.from_numpy(rgb[None]),target_resolution=40,sampling='nearest',
                    palette_image=torch.from_numpy(palette[None,None]),reduce_palette=False,
                    palette_mapping=mapping,dither=dither,seed=1)
                self.assertTrue(np.all(np.any(np.all(out.numpy().reshape(-1,1,3)==palette,axis=-1),axis=-1)))

    def test_grid_applies_same_explicit_mapping(self):
        image=torch.from_numpy(np.random.default_rng(4).random((1,8,8,3),dtype=np.float32))
        node=RayPixelArtDetector()
        settings=dict(target_resolution=8,sampling='nearest',max_colors=4,seed=4,palette_mapping='rgb')
        output,grid=node.process(image,color_grid=True,**settings)
        for index,method in enumerate(node.INPUT_TYPES()['required']['palette_strategy'][0],start=1):
            expected,_=node.process(image,palette_strategy=method,**settings)
            x=12+(index%3)*252+116
            y=12+(index//3)*68+48
            torch.testing.assert_close(grid[:,y:y+8,x:x+8],torch.round(expected*255)/255,rtol=0,atol=0)

if __name__=='__main__': unittest.main()
