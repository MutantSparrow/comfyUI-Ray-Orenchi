import unittest
import numpy as np
import torch
from ray_pixel_detector import RayPixelArtDetector


class ColorGridTests(unittest.TestCase):
    def test_position_and_default(self):
        inputs=RayPixelArtDetector.INPUT_TYPES()['required']
        keys=list(inputs)
        self.assertEqual(keys[keys.index('highlight_threshold')+1],'color_grid')
        self.assertFalse(inputs['color_grid'][1]['default'])

    def test_comparison_tiles_match_methods_and_main_stays_identical(self):
        node=RayPixelArtDetector()
        image=torch.from_numpy(np.random.default_rng(3).random((2,16,24,3),dtype=np.float32))
        settings=dict(target_resolution=24,sampling='nearest',max_colors=8,seed=42)
        normal,_=node.process(image,**settings)
        actual,grid=node.process(image,color_grid=True,**settings)
        torch.testing.assert_close(actual,normal,rtol=0,atol=0)
        self.assertEqual(grid.shape[0],2)
        self.assertTrue(torch.isfinite(grid).all())
        methods=node.INPUT_TYPES()['required']['palette_strategy'][0]
        for i,method in enumerate(methods):
            expected,_=node.process(image,palette_strategy=method,**settings)
            x=12+(i%3)*252+(240-24)//2
            y=12+(i//3)*(16+48+12)+48
            pixels=grid[:,y:y+16,x:x+24]
            torch.testing.assert_close(pixels,torch.round(expected*255)/255,rtol=0,atol=0)
        self.assertGreater(torch.unique(grid[0,12:60,:]).numel(),1)  # labels are rendered

    def test_external_palette_and_disabled_reduction_only_affect_main(self):
        node=RayPixelArtDetector()
        image=torch.from_numpy(np.random.default_rng(5).random((1,8,8,3),dtype=np.float32))
        palette=torch.tensor([[[[0.,0.,0.],[1.,1.,1.]]]])
        settings=dict(target_resolution=8,sampling='nearest',reduce_palette=False,
                      palette_image=palette,seed=6,max_colors=4)
        normal,_=node.process(image,**settings)
        out,grid=node.process(image,color_grid=True,**settings)
        torch.testing.assert_close(out,normal,rtol=0,atol=0)
        self.assertTrue(((out==0)|(out==1)).all())
        tile=grid[:,60:68,120:128]
        self.assertTrue(((tile>0)&(tile<1)).any())

if __name__=='__main__': unittest.main()
