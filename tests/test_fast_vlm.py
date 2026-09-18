"""Run with ComfyUI on PYTHONPATH and its Python environment."""
import unittest
import weakref
from types import SimpleNamespace
from unittest.mock import patch

import torch
import ray_fast_vlm as fast


class FakeModel:
    graph_dynamic_vbar_blocks = False
    config = SimpleNamespace(stop_tokens=[2])
    def __init__(self):
        self.calls = []
    def embed_tokens(self, ids):
        return ids.float().unsqueeze(-1).expand(-1, -1, 4)
    def forward(self, unused, **kwargs):
        pos = kwargs['position_ids']
        self.calls.append({**kwargs, 'position_ids': pos.clone() if pos is not None else None})
        return kwargs['embeds'], None, kwargs['past_key_values']


class FakeTransformer:
    def __init__(self, ids):
        self.model = FakeModel()
        self.ids = iter(ids)
        self.cache_calls = 0
    def init_kv_cache(self, *args):
        self.cache_calls += 1
        return []
    def logits(self, x):
        return torch.zeros(1, 1, 12)
    def sample_token(self, *args, **kwargs):
        return torch.tensor([[next(self.ids)]])


class FastVLMTests(unittest.TestCase):
    def test_repetition_guard_stops_long_loop(self):
        phrase = list(range(3, 11))
        t = FakeTransformer(phrase * 128)
        self.assertEqual(self.call(t, max_length=1024), phrase)
        self.assertEqual(len(t.model.calls), 24)

    def test_repetition_guard_can_be_disabled(self):
        phrase = list(range(3, 11))
        self.assertEqual(self.call(FakeTransformer(phrase * 4), max_length=32, repeat_guard=False), phrase * 4)

    def test_eos_does_not_fill_large_limit(self):
        t = FakeTransformer([4, 5, 2, 6, 7, 8, 9, 10])
        self.assertEqual(self.call(t, max_length=1024), [4, 5, 2])
        self.assertEqual(len(t.model.calls), 8)

    def test_penalties_apply_only_to_seen_tokens(self):
        logits = torch.tensor([[-4., 4., -4., 4.]])
        seen = torch.tensor([[True, True, False, False]])
        actual = fast.penalize_seen(logits, seen, 2.0, 1.5)
        torch.testing.assert_close(actual, torch.tensor([[-9.5, 0.5, -4., 4.]]))

    def test_images_attached_and_no_fake_think_block(self):
        from comfy.text_encoders.krea2 import Krea2Tokenizer
        tokenizer = Krea2Tokenizer()
        clip = SimpleNamespace(tokenize=tokenizer.tokenize_with_weights)
        image = torch.zeros(2, 32, 32, 3)
        tokens = fast.image_tokens(clip, image, 'Describe the picture.', False)
        flattened = [t[0] for batches in tokens.values() for batch in batches for t in batch]
        self.assertEqual(sum(isinstance(t, dict) for t in flattened), 2)
        ids = [t for t in flattened if isinstance(t, int)]
        text = tokenizer.decode(ids, skip_special_tokens=False)
        self.assertNotIn('<think>', text)
        self.assertTrue(text.endswith('<|im_start|>assistant\n'), text)

    def test_missing_image_tokens_fail_before_generation(self):
        clip = SimpleNamespace(tokenize=lambda *a, **kw: {'qwen3vl_4b': [[(42, 1.0)]]})
        with self.assertRaisesRegex(ValueError, 'attached 0 of 1 images'):
            fast.image_tokens(clip, torch.zeros(1,32,32,3), 'Describe.', False)

    def call(self, transformer, **kwargs):
        with patch.object(fast.mm, 'should_use_bf16', return_value=False):
            return fast.fast_generate(transformer, torch.zeros(1, 3, 4), do_sample=False, **kwargs)

    def test_eos_trims_chunk(self):
        t = FakeTransformer([4, 5, 2, 6, 7, 8, 9, 10])
        self.assertEqual(self.call(t, max_length=8, sync_interval=8), [4, 5, 2])
        self.assertEqual(len(t.model.calls), 8)
        self.assertEqual(t.cache_calls, 1)

    def test_immediate_stop(self):
        t = FakeTransformer([2])
        self.assertEqual(self.call(t, max_length=20, sync_interval=1), [2])
        self.assertEqual(len(t.model.calls), 1)

    def test_partial_last_chunk_and_one_token(self):
        for length in (1, 9):
            t = FakeTransformer([4] * length)
            self.assertEqual(self.call(t, max_length=length), [4] * length)

    def test_mrope_and_deepstack_only_on_prefill(self):
        t = FakeTransformer([4] * 4)
        pos = torch.tensor([[1, 2, 4], [1, 5, 8], [1, 3, 6]])
        ds = [torch.ones(1)]
        self.call(t, max_length=4, position_ids=pos, deepstack_embeds=ds, visual_pos_masks=torch.ones(1,3,dtype=torch.bool))
        self.assertIs(t.model.calls[0]['deepstack_embeds'], ds)
        self.assertNotIn('deepstack_embeds', t.model.calls[1])
        self.assertEqual([c['position_ids'].item() for c in t.model.calls[1:]], [9, 10, 11])

    def test_cancellation_checked_each_step(self):
        t = FakeTransformer([4] * 8)
        with patch.object(fast.mm, 'throw_exception_if_processing_interrupted', side_effect=[None, RuntimeError('cancelled')]):
            with self.assertRaisesRegex(RuntimeError, 'cancelled'):
                self.call(t, max_length=8)
        self.assertEqual(len(t.model.calls), 1)

    def test_graph_cleanup_on_error(self):
        t = FakeTransformer([])
        t.model.graph_dynamic_vbar_blocks = True
        with patch.object(fast.prefetch, 'malloc_graph_enabled', return_value=False), patch.object(fast.prefetch, 'cleanup_prefetch_queues') as cleanup:
            with self.assertRaises(StopIteration):
                self.call(t, max_length=1)
            cleanup.assert_called_once()

    def test_graph_cleanup_on_success(self):
        t = FakeTransformer([4])
        t.model.graph_dynamic_vbar_blocks = True
        with patch.object(fast.prefetch, 'malloc_graph_enabled', return_value=False), patch.object(fast.prefetch, 'cleanup_prefetch_queues') as cleanup:
            self.call(t, max_length=1)
            cleanup.assert_called_once()

    def test_invalid_inputs(self):
        node = fast.RayFastQwen3VL()
        for options in ({'max_tokens':0}, {'sync_interval':0}):
            with self.assertRaises(ValueError):
                node.infer(None, torch.zeros(1,32,32,3), 'test', **options)

    def test_wrong_model_reports_detected_encoder(self):
        stage = SimpleNamespace(clip='qwen25_7b', qwen25_7b=SimpleNamespace(transformer=SimpleNamespace()))
        clip = SimpleNamespace(cond_stage_model=stage)
        for mode in ('fast', 'native'):
            with self.assertRaisesRegex(ValueError, "encoder='qwen25_7b'.*qwen3vl_8b_fp8_scaled"):
                fast.RayFastQwen3VL().infer(clip, torch.zeros(1,32,32,3), 'Describe.', mode=mode)

    def test_missing_encoder_reports_useful_error(self):
        with self.assertRaisesRegex(ValueError, 'not a native Qwen3-VL'):
            fast.qwen3vl_model(SimpleNamespace(cond_stage_model=SimpleNamespace()))

    def test_native_qwen3vl_accepted_and_truncated_rejected(self):
        transformer = fast.Qwen3VL.__new__(fast.Qwen3VL)
        torch.nn.Module.__init__(transformer)
        stage = SimpleNamespace(clip='qwen3vl_8b', qwen3vl_8b=SimpleNamespace(transformer=transformer))
        clip = SimpleNamespace(cond_stage_model=stage)
        for model_type in ('qwen3vl_8b', 'qwen3vl_4b'):
            transformer.model_type = model_type
            self.assertIs(fast.qwen3vl_model(clip)[1], transformer)
        transformer.model_type = 'qwen3vl_32b'
        with self.assertRaisesRegex(ValueError, 'truncated for conditioning'):
            fast.qwen3vl_model(clip)

    def test_buffers_live_until_graph_cleanup(self):
        t = FakeTransformer([])
        t.model.graph_dynamic_vbar_blocks = True
        refs = []
        def generate(self, *, _request_buffers):
            tensor = torch.empty(1)
            refs.append(weakref.ref(tensor))
            _request_buffers.append(tensor)
            return [4]
        def cleanup():
            self.assertIsNotNone(refs[0]())
        with patch.object(fast, '_generate_tokens', generate), patch.object(fast.prefetch, 'cleanup_prefetch_queues', cleanup):
            self.assertEqual(fast.fast_generate(t), [4])
        self.assertIsNone(refs[0]())


if __name__ == '__main__':
    unittest.main()
