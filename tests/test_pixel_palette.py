import unittest
import numpy as np
import torch
from ray_pixel_detector import make_palette, quantize, RayPixelArtDetector
from ray_pixel_palette import cie_lab


class PaletteRegressionTests(unittest.TestCase):
    def test_rare_neutral_and_warm_highlights_all_methods(self):
        rng=np.random.default_rng(8)
        rgb=rng.uniform(.02,.6,(192,192,3)).astype(np.float32)
        rgb[0,0]=[1,1,1]
        rgb[0,1]=[1,.96,.65]
        for strategy in ('kmeans_lab','kmeans_rgb','oklab_source','ramps_oklab','quantize_simple'):
            palette=make_palette(rgb,16,7,strategy=strategy)
            self.assertLessEqual(len(palette),16)
            self.assertTrue(np.any(np.linalg.norm(palette-[1,1,1],axis=-1)<.001),strategy)
            self.assertTrue(np.any(np.linalg.norm(palette-[1,.96,.65],axis=-1)<.01),strategy)

    def test_threshold_is_cie_lightness(self):
        self.assertAlmostEqual(float(cie_lab(np.array([[.5,.5,.5]],np.float32))[0,0]),53.39,places=1)

    def test_palette_budget_seed_and_ramp_remainders(self):
        rgb=np.random.default_rng(4).random((24,24,3),dtype=np.float32)
        for count in (2,3,5,8,17):
            a=make_palette(rgb,count,8,strategy='ramps_oklab')
            b=make_palette(rgb,count,8,strategy='ramps_oklab')
            self.assertLessEqual(len(a),count)
            np.testing.assert_array_equal(a,b)

    def test_flat_and_nearly_flat_noise_are_not_dithered(self):
        rng=np.random.default_rng(8)
        palette=np.array([[.2,.2,.2],[.6,.6,.6]],np.float32)
        for rgb in (np.full((48,48,3),.4,np.float32),
                    np.full((48,48,3),.4,np.float32)+rng.uniform(-.002,.002,(48,48,3)).astype(np.float32)):
            base=quantize(rgb,palette,'none',1)
            for mode in ('ordered','error_diffusion'):
                np.testing.assert_array_equal(quantize(rgb,palette,mode,1),base)

    def test_flat_plateaus_next_to_ramp_stay_clean(self):
        line=np.r_[np.full(32,.3),np.linspace(.3,.7,64),np.full(32,.7)].astype(np.float32)
        rgb=np.broadcast_to(line[None,:,None],(24,128,3)).copy()
        palette=np.array([[.1]*3,[.5]*3,[.9]*3],np.float32)
        base=quantize(rgb,palette,'none',1)
        for mode in ('ordered','error_diffusion'):
            out=quantize(rgb,palette,mode,1)
            np.testing.assert_array_equal(out[:,:28],base[:,:28])
            np.testing.assert_array_equal(out[:,100:],base[:,100:])
            self.assertTrue(np.any(out[:,36:92]!=base[:,36:92]))

    def test_external_palette_overrides_highlight_reservation(self):
        image=torch.ones((1,16,16,3))
        swatches=torch.tensor([[[[.2,.1,.1],[.6,.5,.2]]]])
        out,_=RayPixelArtDetector().process(image,target_resolution=16,palette_image=swatches,
                                           protect_highlights=True,palette_style='distinct')
        colors=swatches.numpy().reshape(-1,3)
        self.assertTrue(np.all(np.any(np.all(out.numpy().reshape(-1,1,3)==colors,axis=-1),axis=-1)))

    def test_distinct_style_keeps_neutral_highlight(self):
        rgb=np.random.default_rng(2).uniform(.1,.7,(1,32,32,3)).astype(np.float32)
        rgb[0,4,4]=1
        out,_=RayPixelArtDetector().process(torch.from_numpy(rgb),target_resolution=32,
                                          sampling='nearest',max_colors=8,palette_style='distinct',seed=2)
        np.testing.assert_allclose(out[0,4,4],1,atol=.001)

    def test_coherent_color_areas_survive_busy_texture(self):
        rgb=np.random.default_rng(9).uniform(.05,.8,(96,96,3)).astype(np.float32)
        anchors=np.array([[.8,.57,.43],[.22,.35,.16],[.85,.7,.28]],np.float32)
        for i,color in enumerate(anchors):
            rgb[8:32,8+i*28:32+i*28]=color
        for strategy in ('kmeans_lab','quantize_simple'):
            palette=make_palette(rgb,16,2,strategy=strategy,protect_highlights=False)
            output=quantize(rgb,palette,'none',0)
            for i,color in enumerate(anchors):
                np.testing.assert_allclose(output[12:28,12+i*28:28+i*28].mean((0,1)),color,atol=.015)

    def test_simple_original_bucket_path(self):
        rgb=np.random.default_rng(5).random((32,32,3),dtype=np.float32)
        for allocation in ('frequency','area_preserving'):
            palette=make_palette(rgb,16,4,strategy='quantize_simple',palette_allocation=allocation)
            self.assertLessEqual(len(palette),16)
            self.assertTrue(np.isfinite(palette).all())

if __name__ == '__main__': unittest.main()
