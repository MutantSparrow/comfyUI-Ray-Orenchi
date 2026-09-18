import unittest
import numpy as np
import torch
from ray_pixel_detector import make_palette, quantize, RayPixelArtDetector


class ColorFamilyTests(unittest.TestCase):
    def fixture(self):
        bases=np.array([[.93,.79,.42],[.93,.68,.57],[.32,.46,.20],
                        [.44,.26,.12],[.56,.57,.59],[.005,.005,.005]],np.float32)
        tiles=[]
        for base in bases:
            ramp=np.linspace(.60,1.12,48,dtype=np.float32)
            tile=np.clip(base[None,None,:]*ramp[None,:,None],0,1)
            tiles.append(np.broadcast_to(tile,(24,48,3)).copy())
        return bases,np.concatenate(tiles,axis=0)

    def test_six_shaded_groups_remain_separate_at_eight_colors(self):
        bases,rgb=self.fixture()
        p=make_palette(rgb,8,42,strategy='color_families')
        mapped=quantize(bases[None],p,'none',0,True)[0]
        self.assertEqual(len(np.unique(mapped,axis=0)),6)
        self.assertLessEqual(len(p),8)
        # Gray must remain achromatic, not become skin, leather or foliage.
        self.assertLess(np.ptp(mapped[4]),.07)
        self.assertLess(mapped[5].max(),.03)
        self.assertGreater(mapped[0,0]-mapped[0,2],.2)
        self.assertGreater(mapped[2,1]-mapped[2,0],.05)
        self.assertGreater(mapped[1].mean()-mapped[3].mean(),.2)

    def test_budget_determinism_and_range(self):
        _,rgb=self.fixture()
        for count in (2,3,4,6,8,16,32):
            a=make_palette(rgb,count,5,strategy='color_families')
            b=make_palette(rgb,count,5,strategy='color_families')
            np.testing.assert_array_equal(a,b)
            self.assertLessEqual(len(a),count)
            self.assertTrue(np.isfinite(a).all())
            self.assertTrue(((a>=0)&(a<=1)).all())

    def test_grayscale_has_no_invented_hues(self):
        rgb=np.broadcast_to(np.linspace(0,1,64,dtype=np.float32)[None,:,None],(16,64,3)).copy()
        p=make_palette(rgb,8,2,strategy='color_families')
        self.assertLess(np.ptp(p,axis=-1).max(),1e-6)

    def test_dither_keeps_flat_family_areas_and_palette(self):
        bases,rgb=self.fixture()
        p=make_palette(rgb,8,42,strategy='color_families')
        for mode in ('ordered','error_diffusion'):
            flat=np.broadcast_to(bases[1],(16,16,3)).copy()
            np.testing.assert_array_equal(quantize(flat,p,mode,1,True),quantize(flat,p,'none',0,True))
            out=quantize(rgb,p,mode,1,True)
            self.assertTrue(np.all(np.any(np.all(out.reshape(-1,1,3)==p,axis=-1),axis=-1)))

    def test_node_preserves_supplied_palette_and_dimensions(self):
        _,rgb=self.fixture()
        node=RayPixelArtDetector()
        swatches=torch.tensor([[[[.1,.2,.3],[.8,.8,.8]]]])
        out,preview=node.process(torch.from_numpy(rgb[None]),target_resolution=72,
                                 sampling='nearest',palette_strategy='color_families',palette_image=swatches)
        self.assertEqual(out.shape,(1,72,24,3))
        self.assertEqual(preview.shape,(1,*rgb.shape))
        p=swatches.numpy().reshape(-1,3)
        self.assertTrue(np.all(np.any(np.all(out.numpy().reshape(-1,1,3)==p,axis=-1),axis=-1)))

if __name__=='__main__': unittest.main()
