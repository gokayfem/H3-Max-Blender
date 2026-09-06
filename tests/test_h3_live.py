"""Run with Blender --background --factory-startup --python this_file."""
import importlib.util
import json
import queue
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

import bpy

root = Path(__file__).resolve().parents[1] / 'extension'
spec = importlib.util.spec_from_file_location("fal_ai", root / "__init__.py", submodule_search_locations=[str(root)])
addon = importlib.util.module_from_spec(spec)
sys.modules["fal_ai"] = addon
spec.loader.exec_module(addon)
from fal_ai import live_preview as live
from fal_ai import live_stream as stream
from fal_ai import live_grid as grid
from fal_ai.stream_buffer import ClipBuffer


class LiveTests(unittest.TestCase):
    def test_early_stage_prompts_do_not_prime_future_components(self):
        from fal_ai import stage_prompts
        for stage in (0, 1, 2):
            for prompt in grid.prompts_for(stage_prompts.for_stage(stage), False, 'PER_STYLE_TEXT'):
                for absent in ('mast', 'crane', 'window', 'roof', 'tender'):
                    self.assertNotIn(absent, prompt.lower())

    def test_per_style_payload_keeps_geometry_and_style_roles_separate(self):
        from fal_ai import image_guidance
        bundle = dict(mode='PER_STYLE', common=['full', 'detail'],
                      buffers=['normals', 'mask'], styles=['day', 'storm', 'space', 'mini'])
        expected = [['full']*3+['day'], ['full','normals','mask','storm'],
                    ['full','space'], ['full','detail','mini']]
        for index, images in enumerate(expected):
            payload = image_guidance.payload(bundle, 'prompt', '480P', 112358, index)
            self.assertEqual(payload['reference_image_urls'], images)
            self.assertNotIn('reference_video_urls', payload)
        bundle['mode'] = 'PER_STYLE_TEXT'
        for index in range(4):
            payload = image_guidance.payload(bundle, 'prompt', '768P', 112358, index)
            self.assertEqual(payload['reference_image_urls'], expected[index][:-1])

    def test_style_reference_is_second_and_geometry_stays_first(self):
        payload = live.build_payload(b'geometry', 'render', '480P', reference_mode=True, style_image_bytes=b'\xff\xd8style')
        self.assertEqual(payload['reference_image_urls'][0], live._image_uri(b'geometry'))
        self.assertEqual(payload['reference_image_urls'][1], live._image_uri(b'\xff\xd8style'))
        with self.assertRaises(ValueError):
            live.build_payload(b'geometry', 'render', '480P', style_image_bytes=b'style')

    def test_frozen_style_manifest_rejects_changed_images(self):
        import hashlib
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            image = b'\xff\xd8fixed-style'
            (folder/'style.jpg').write_bytes(image)
            manifest = dict(styles=[dict(id=i,file='style.jpg',sha256=hashlib.sha256(image).hexdigest()) for i in ['expedition','storm','orbital','miniature']])
            path = folder/'manifest.json'
            path.write_text(json.dumps(manifest),encoding='utf-8')
            self.assertEqual(grid.load_style_references(str(path)), [image]*4)
            (folder/'style.jpg').write_bytes(b'\xff\xd8changed')
            with self.assertRaises(ValueError):grid.load_style_references(str(path))

    def test_grid_launches_four_concurrent_requests_from_one_capture(self):
        addon.register()
        scene = bpy.context.scene
        barrier = threading.Barrier(5)
        requests = []
        grid._session = dict(scene=scene, window=SimpleNamespace(scene=scene),
            area=SimpleNamespace(type='VIEW_3D'), areas=[SimpleNamespace(type='CLIP_EDITOR') for _ in range(4)],
            observed='same', submitted=None, changed=0, events=queue.Queue(), busy=False,
            count=0, key='test', folder=tempfile.gettempdir())
        def generation(key, payload, folder, events, token, capture_seconds, endpoint):
            requests.append((payload, endpoint))
            barrier.wait(timeout=3)
        try:
            with patch.object(live, '_signature', return_value='same'), patch.object(live, '_capture', return_value=b'\xff\xd8jpeg') as capture, patch.object(live, 'generate', side_effect=generation):
                grid._tick()
                barrier.wait(timeout=3)
                for worker in grid._workers:worker.join(timeout=3)
            self.assertEqual(capture.call_count, 1)
            self.assertEqual(len(requests), 4)
            self.assertEqual(len({r[0]['prompt'] for r in requests}), 4)
            self.assertEqual(len({r[0]['reference_image_urls'][0] for r in requests}), 1)
            self.assertTrue(all(r[1] == grid.ENDPOINT for r in requests))
        finally:
            addon.unregister()

    def test_grid_maps_out_of_order_results_to_their_style_panes(self):
        addon.register()
        scene = bpy.context.scene
        events = queue.Queue()
        for index in [3, 1, 2, 0]:
            events.put((('batch', index), 'complete', {'video_path': f'{index}.mp4'}))
        grid._session = dict(scene=scene, window=SimpleNamespace(scene=scene),
            area=SimpleNamespace(type='VIEW_3D'), areas=[SimpleNamespace(type='CLIP_EDITOR') for _ in range(4)],
            observed='same', submitted='same', changed=0, events=events, busy=True,
            count=1, pending=set(range(4)), batch_token='batch', results={}, errors={},
            completed=0, history=[], batch_started=time.perf_counter())
        try:
            with patch.object(live, '_signature', return_value='same'), patch.object(grid, '_play') as play:
                grid._tick()
            self.assertEqual([(c.args[0],c.args[1]) for c in play.call_args_list], [(i,f'{i}.mp4') for i in [3,1,2,0]])
            self.assertEqual(scene.fal_h3_live.last_video, '0.mp4')
            self.assertEqual(grid._session['completed'], 1)
            self.assertFalse(grid._session['busy'])
        finally:
            addon.unregister()

    def test_edit_during_generation_does_not_display_obsolete_clip(self):
        addon.register()
        scene = bpy.context.scene
        events = queue.Queue()
        events.put(('session', 'complete', {'video_path': 'obsolete.mp4'}))
        live._session = dict(scene=scene, window=SimpleNamespace(scene=scene),
            area=SimpleNamespace(type='VIEW_3D', tag_redraw=lambda: None),
            token='session', events=events, busy=True, count=1, auto=True,
            submitted='old geometry', observed='old geometry', changed=0)
        try:
            with patch.object(live, '_signature', return_value='new geometry'), patch.object(live, '_play') as play:
                live._tick()
                play.assert_not_called()
            self.assertEqual(scene.fal_h3_live.last_video, '')
            self.assertFalse(live._session['busy'])
        finally:
            addon.unregister()

    def test_geometry_digest_ignores_invalidation_but_detects_vertex_edits(self):
        scene = bpy.context.scene
        obj = next(o for o in scene.objects if o.type == 'MESH')
        before = live._geometry_digest(scene)
        obj.update_tag(refresh={'DATA'})
        bpy.context.view_layer.update()
        self.assertEqual(before, live._geometry_digest(scene))
        original = obj.data.vertices[0].co.copy()
        try:
            obj.data.vertices[0].co.x += .25
            obj.data.update()
            bpy.context.view_layer.update()
            self.assertNotEqual(before, live._geometry_digest(scene))
        finally:
            obj.data.vertices[0].co = original
            obj.data.update()

    def test_gray_jpeg_reference_payload(self):
        payload = live.build_payload(b"\xff\xd8jpeg", "interpret geometry", "480P", reference_mode=True)
        self.assertTrue(payload["reference_image_urls"][0].startswith("data:image/jpeg;base64,"))
        self.assertEqual(payload["aspect_ratio"], "16:9")
        self.assertNotIn("image_url", payload)
        with self.assertRaises(ValueError):
            live.build_payload(b"first", "geometry", "480P", b"last", reference_mode=True)

    def test_paired_base64(self):
        payload = live.build_payload(b"first", "motion", "480P", b"last")
        self.assertEqual(payload["image_url"], "data:image/png;base64,Zmlyc3Q=")
        self.assertEqual(payload["end_image_url"], "data:image/png;base64,bGFzdA==")

    def test_buffer_preserves_order_and_waits_for_prefill(self):
        buffer = ClipBuffer(2)
        buffer.put(1, "second")
        self.assertIsNone(buffer.pop())
        buffer.put(0, "first")
        self.assertEqual(buffer.pop(), "first")
        self.assertEqual(buffer.pop(), "second")
        self.assertIsNone(buffer.pop())
        buffer.put(3, "fourth")
        self.assertIsNone(buffer.pop())
        buffer.put(2, "third")
        self.assertEqual(buffer.pop(), "third")
        self.assertEqual(buffer.pop(), "fourth")

    def test_short_stream_can_drain_and_rejects_duplicates(self):
        buffer = ClipBuffer(2)
        buffer.put(0, "one")
        self.assertIsNone(buffer.pop())
        self.assertEqual(buffer.pop(final=True), "one")
        with self.assertRaises(ValueError): buffer.put(0, "duplicate")

    def test_pair_reuses_boundary_and_restores_timeline(self):
        scene = bpy.context.scene
        scene.frame_set(42)
        session = {"scene": scene}
        with patch.object(live, "_capture", side_effect=[b"first", b"boundary", b"last"]) as capture:
            first, last, _ = stream.capture_pair(session, 1, 121)
            second_first, second_last, _ = stream.capture_pair(session, 121, 241)
        self.assertEqual(capture.call_count, 3)
        self.assertEqual(last, second_first)
        self.assertEqual(scene.frame_current, 42)
        with patch.object(live, "_capture", side_effect=RuntimeError("capture failed")):
            with self.assertRaises(RuntimeError): stream.capture_pair(session, 241, 361)
        self.assertEqual(scene.frame_current, 42)

    def test_registration_and_defaults(self):
        addon.register()
        self.assertEqual(bpy.context.scene.fal_h3_live.resolution, "480P")
        self.assertTrue(bpy.app.timers.is_registered(live._tick))
        addon.unregister()
        self.assertFalse(hasattr(bpy.types.Scene, "fal_h3_live"))
        self.assertFalse(bpy.app.timers.is_registered(live._tick))

    def test_payload_and_validation(self):
        payload = live.build_payload(b"png", " test motion ", "480P")
        self.assertEqual(payload["image_url"], "data:image/png;base64,cG5n")
        self.assertEqual(payload["duration"], 5)
        self.assertNotIn("aspect_ratio", payload)
        self.assertTrue(payload["enable_safety_checker"])
        with self.assertRaises(ValueError):
            live.build_payload(b"png", "", "480P")

    def test_network_failure_never_retries_or_exposes_key(self):
        events = queue.Queue()
        with patch.object(live.urllib.request, "urlopen", side_effect=TimeoutError("SECRET")) as call:
            live.generate("SECRET", {}, tempfile.gettempdir(), events, "token", 0)
        self.assertEqual(call.call_count, 1)
        token, kind, message = events.get_nowait()
        self.assertEqual(kind, "error")
        self.assertNotIn("SECRET", message)

    def test_worker_saves_timing_and_result(self):
        class Response:
            headers = {"x-fal-request-id": "test-request"}
            def __init__(self, data): self.data = data
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self): return self.data
        events = queue.Queue()
        result = {"video": {"url": "https://example.com/test.mp4"}, "timings": {"inference": 0.49},
                  "expanded_prompt": "Static camera after expansion", "seed": 73419}
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(live.urllib.request, "urlopen", side_effect=[Response(json.dumps(result).encode()), Response(b"movie")]):
                live.generate("SECRET", live.build_payload(b"png", "motion", "480P"), folder, events, "token", 0.1)
            events.get_nowait()
            _, kind, data = events.get_nowait()
            self.assertEqual(kind, "complete")
            self.assertEqual(Path(data["video_path"]).read_bytes(), b"movie")
            self.assertEqual(data["provider_timings"]["inference"], 0.49)
            self.assertEqual(data["expanded_prompt"], result["expanded_prompt"])
            self.assertEqual(data["seed"], 73419)
            self.assertNotIn("SECRET", Path(data["video_path"]).with_suffix(".json").read_text())


suite = unittest.defaultTestLoader.loadTestsFromTestCase(LiveTests)
result = unittest.TextTestRunner(verbosity=2).run(suite)
if not result.wasSuccessful():
    raise RuntimeError("H3 Live tests failed")
