"""Pixel Art behavior regressions; no ComfyUI server or GPU required."""
import unittest
import numpy as np
import torch
import torch.nn.functional as F
from ray_pixel_detector import (RayPixelArtDetector, exact_size, oklab,
                                quantize, outline_image, sample_image)


class PixelArtTests(unittest.TestCase):
    def setUp(self):
        self.node = RayPixelArtDetector()
        self.palette = np.array([[.05, .08, .15], [.3, .45, .65], [.8, .65, .3], [.95, .95, .85]], np.float32)

    def test_exact_aspect_all_dimensions(self):
        for h, w in [(768, 1024), (720, 1280), (667, 1001), (17, 31), (64, 64), (1, 70)]:
            for target in [1, 32, 128, 256, 4096]:
                oh, ow = exact_size(h, w, target)
                self.assertEqual(oh * w, ow * h)
                self.assertTrue(1 <= oh <= h and 1 <= ow <= w)
        self.assertEqual(exact_size(667, 1001, 128), (667, 1001))
        self.assertEqual(exact_size(768, 1024, 128), (96, 128))

    def test_oklab_reference_values(self):
        np.testing.assert_allclose(oklab([[1, 0, 0]])[0], [.627955, .224863, .125846], atol=1e-5)
        np.testing.assert_allclose(oklab([[1, 1, 1]])[0], [1, 0, 0], atol=1e-6)
        np.testing.assert_allclose(oklab([[0, 0, 0]])[0], [0, 0, 0], atol=1e-6)

    def test_crisp_grid_roundtrip_and_auto_batch(self):
        ids = np.random.default_rng(4).integers(0, 4, (2, 24, 32))
        source = torch.from_numpy(self.palette[ids])
        enlarged = F.interpolate(source.permute(0, 3, 1, 2), scale_factor=8, mode="nearest").permute(0, 2, 3, 1)
        out, preview = self.node.process(enlarged, mode="auto_pixel_size", reduce_palette=False)
        torch.testing.assert_close(out, source, rtol=0, atol=0)
        torch.testing.assert_close(preview, enlarged, rtol=0, atol=0)

    def test_nearest_is_unmodified_source_sample(self):
        rgb = np.random.default_rng(2).random((16, 24, 3), dtype=np.float32)
        out, preview = self.node.process(torch.from_numpy(rgb), target_resolution=6, sampling="nearest", reduce_palette=False)
        np.testing.assert_array_equal(out[0], rgb[2::4, 2::4])
        self.assertEqual(tuple(preview.shape), (1, 16, 24, 3))
        expected = F.interpolate(out.permute(0, 3, 1, 2), size=(16, 24), mode="nearest").permute(0, 2, 3, 1)
        torch.testing.assert_close(preview, expected, rtol=0, atol=0)

    def test_cell_vote_rejects_center_noise_better_than_nearest(self):
        original = self.palette[np.indices((16, 16)).sum(0) % 4]
        enlarged = original.repeat(8, 0).repeat(8, 1)
        corrupted = enlarged.copy()
        corrupted[4::8, 4::8] = [1, 0, 1]
        snapped = sample_image(corrupted, (16, 16), "grid_snap")
        nearest = sample_image(corrupted, (16, 16), "nearest")
        np.testing.assert_array_equal(snapped, original)
        self.assertGreater(np.mean(abs(nearest - original)), .1)

    def test_flat_auto_falls_back(self):
        from ray_pixel_structure import detect_size
        self.assertEqual(detect_size(np.ones((24,32,3),np.float32),(6,8))[0], (6,8))
        out, _ = self.node.process(torch.ones(2, 96, 128, 3), mode="auto_pixel_size", target_resolution=32)
        self.assertEqual(tuple(out.shape), (2, 24, 32, 3))

    def test_fixed_palette_exact_even_when_reduce_disabled(self):
        colors = torch.tensor([[[[.013, .141, .275], [.4, .6, .8], [.95, .23, .01]]]])
        image = torch.rand(1, 24, 32, 3)
        for dither in ("none", "ordered", "error_diffusion"):
            out, _ = self.node.process(image, target_resolution=32, palette_image=colors,
                                       reduce_palette=False, max_colors=2, dither=dither)
            allowed = {tuple(x.tolist()) for x in colors.reshape(-1, 3)}
            self.assertTrue(all(tuple(x.tolist()) in allowed for x in out.reshape(-1, 3)))

    def test_palette_budget_and_seed_reproducibility(self):
        image = torch.from_numpy(np.random.default_rng(5).random((2, 24, 32, 3), dtype=np.float32))
        a, _ = self.node.process(image, target_resolution=32, max_colors=7, seed=123)
        b, _ = self.node.process(image, target_resolution=32, max_colors=7, seed=123)
        torch.testing.assert_close(a, b, rtol=0, atol=0)
        self.assertLessEqual(len(torch.unique(a.reshape(-1, 3), dim=0)), 7)

    def test_dither_does_not_touch_palette_pixels(self):
        rgb = self.palette[np.indices((12, 12)).sum(0) % 4]
        for mode in ("none", "ordered", "error_diffusion"):
            np.testing.assert_array_equal(quantize(rgb, self.palette, mode, 1), rgb)

    def test_dither_reduces_low_frequency_gradient_error(self):
        # Judge local tone, not pointwise RGB error (dither deliberately trades it).
        ramp = np.broadcast_to(np.linspace(.1, .9, 64, dtype=np.float32)[None, :, None], (32, 64, 3)).copy()
        palette = np.array([[0, 0, 0], [.5, .5, .5], [1, 1, 1]], np.float32)
        def tone(x):
            return F.avg_pool2d(torch.from_numpy(x).permute(2, 0, 1)[None], 8).numpy()
        base = np.mean((tone(quantize(ramp, palette, "none", 1)) - tone(ramp))**2)
        for mode in ("ordered", "error_diffusion"):
            error = np.mean((tone(quantize(ramp, palette, mode, 1)) - tone(ramp))**2)
            self.assertLess(error, base)

    def test_outline_preserves_background_and_inner_detail(self):
        palette = np.array([[1, 1, 1], [.7, .25, .1], [.3, .1, .05]], np.float32)
        rgb = np.ones((20, 20, 3), np.float32)
        rgb[4:16, 4:16] = palette[1]
        rgb[9:11, 9:11] = palette[0]  # Interior matching background remains interior.
        out = outline_image(rgb, palette, "silhouette")
        np.testing.assert_array_equal(out[:4], rgb[:4])
        np.testing.assert_array_equal(out[8:12, 8:12], rgb[8:12, 8:12])
        np.testing.assert_array_equal(out[4, 5], palette[2])

    def test_input_formats(self):
        for channels in [1, 3, 4]:
            out, preview = self.node.process(torch.full((16, 24, channels), 128, dtype=torch.uint8),
                                             target_resolution=12, reduce_palette=False)
            self.assertEqual(tuple(out.shape), (1, 8, 12, 3))
            self.assertEqual(tuple(preview.shape), (1, 16, 24, 3))
            self.assertEqual(out.dtype, torch.float32)
            self.assertTrue(torch.isfinite(out).all())

    def test_fractional_grid_recovery(self):
        from PIL import Image
        source=self.palette[np.random.default_rng(8).integers(0,4,(16,24))]
        u8=np.rint(source*255).astype(np.uint8)
        enlarged=np.asarray(Image.fromarray(u8).resize((150,100),Image.Resampling.NEAREST),dtype=np.float32)/255
        out,_=self.node.process(torch.from_numpy(enlarged),mode="auto_pixel_size",reduce_palette=False)
        self.assertEqual(tuple(out.shape),(1,16,24,3))
        np.testing.assert_allclose(out[0],u8/255,atol=1e-6)

    def test_center_tie_uses_spatial_center(self):
        rgb=np.zeros((4,4,3),np.float32);rgb[:,:2,0]=1;rgb[:,2:,2]=1
        out=sample_image(rgb,(1,1),"grid_snap")
        np.testing.assert_array_equal(out[0,0],[0,0,1])

    def test_random_noise_reconstruction_improves_over_nearest(self):
        source=self.palette[np.random.default_rng(8).integers(0,4,(12,16))]
        large=source.repeat(8,0).repeat(8,1)
        noise=np.random.default_rng(91).normal(0,.035,large.shape)
        damaged=np.clip(large+noise,0,1).astype(np.float32)
        out=sample_image(damaged,source.shape[:2],"grid_snap")
        nearest=sample_image(damaged,source.shape[:2],"nearest")
        self.assertLess(np.mean((out-source)**2),np.mean((nearest-source)**2)*.5)

    def test_flat_fill_does_not_get_dither_texture(self):
        image=np.full((32,32,3),.37,np.float32)
        palette=np.array([[.2,.2,.2],[.5,.5,.5]],np.float32)
        for mode in ("ordered","error_diffusion"):
            out=quantize(image,palette,mode,1)
            self.assertEqual(len(np.unique(out.reshape(-1,3),axis=0)),1)

    def test_distinct_palette_merges_only_generated_shades(self):
        from ray_pixel_structure import distinct_palette
        from ray_pixel_detector import nearest_indices
        colors=np.array([[0,0,0],[.5,.5,.5],[.501,.501,.501],[1,1,1]],np.float32)
        reduced=distinct_palette(colors,colors[None],oklab,nearest_indices)
        self.assertEqual(len(reduced),3)
        out,_=self.node.process(torch.from_numpy(colors[None]),palette_image=torch.from_numpy(colors[None]),
                                palette_style="distinct",target_resolution=4)
        self.assertEqual(len(np.unique(out.numpy().reshape(-1,3),axis=0)),4)

    def test_cluster_cleanup_preserves_eye_and_thin_stroke(self):
        from ray_pixel_structure import clean_clusters
        from ray_pixel_detector import nearest_indices
        palette=np.array([[.5,.5,.5],[.53,.53,.53],[0,0,0],[1,1,1]],np.float32)
        im=np.full((12,12,3),.5,np.float32)
        im[3,3]=palette[1];im[7,7]=palette[3];im[1:8,10]=palette[2]
        cleaned=clean_clusters(im,im,palette,oklab,nearest_indices)
        np.testing.assert_array_equal(cleaned[3,3],palette[0])
        np.testing.assert_array_equal(cleaned[7,7],palette[3])
        np.testing.assert_array_equal(cleaned[1:8,10],im[1:8,10])

    def test_masked_selective_outline_preserves_background(self):
        image=np.random.default_rng(32).random((20,20,3),dtype=np.float32)
        image[4:16,4:16]=[.8,.5,.3]
        palette=np.array([[.1,.08,.06],[.45,.25,.15],[.8,.5,.3]],np.float32)
        mask=np.zeros((20,20),np.float32);mask[4:16,4:16]=1
        out=outline_image(image,palette,"selective",mask)
        np.testing.assert_array_equal(out[mask==0],image[mask==0])
        np.testing.assert_array_equal(out[6:14,6:14],image[6:14,6:14])
        self.assertTrue(np.isfinite(out).all())

    def test_illustration_pipeline_palette_mask_and_repeatability(self):
        y,x=np.indices((64,96),dtype=np.float32)
        rgb=np.stack([x/96,y/64,(x+y)/160],axis=-1)
        image=torch.from_numpy(rgb)[None]
        mask=torch.ones(1,64,96)
        a,p=self.node.process(image,input_kind="illustration_photo",target_resolution=24,max_colors=8,
                              palette_style="distinct",foreground_mask=mask,outline="selective",seed=42)
        b,_=self.node.process(image,input_kind="illustration_photo",target_resolution=24,max_colors=8,
                              palette_style="distinct",foreground_mask=mask,outline="selective",seed=42)
        torch.testing.assert_close(a,b,atol=0,rtol=0)
        self.assertEqual(tuple(a.shape),(1,16,24,3))
        self.assertEqual(tuple(p.shape),(1,64,96,3))
        self.assertLessEqual(len(torch.unique(a.reshape(-1,3),dim=0)),8)

    def test_blurred_grid_is_not_mistaken_for_native_pixels(self):
        from PIL import Image,ImageFilter
        from ray_pixel_structure import native_grid_evidence
        rgb=self.palette[np.random.default_rng(18).integers(0,4,(16,24))]
        u8=np.rint(rgb*255).astype(np.uint8).repeat(6,0).repeat(6,1)
        blurred=np.asarray(Image.fromarray(u8).filter(ImageFilter.GaussianBlur(1)),dtype=np.float32)/255
        self.assertFalse(native_grid_evidence(blurred))

    def test_auto_detection_is_independent_of_prior_opencv_rng(self):
        import cv2
        from PIL import Image
        from ray_pixel_structure import detect_size
        rgb=self.palette[np.random.default_rng(118).integers(0,4,(16,24))]
        u8=np.rint(rgb*255).astype(np.uint8)
        input_image=np.asarray(Image.fromarray(u8).resize((150,100),Image.Resampling.BILINEAR),dtype=np.float32)/255
        sizes=[]
        for rng_seed in [1,777,123456]:
            cv2.setRNGSeed(rng_seed)
            sizes.append(detect_size(input_image,(64,96))[0])
        self.assertEqual(sizes[0],sizes[1])
        self.assertEqual(sizes[1],sizes[2])


if __name__ == "__main__":
    unittest.main()
