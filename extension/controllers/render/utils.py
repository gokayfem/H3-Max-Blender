from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ...utils import get_default_font

if TYPE_CHECKING:
    import bpy

__all__ = [
    "get_dimensions",
    "overlay_labels",
    "is_occluded",
    "render_to_sketch",
    "render_to_canny",
]


def get_dimensions(
    context: bpy.types.Context, props: bpy.types.PropertyGroup
) -> tuple[int, int]:
    """Get render dimensions — from scene settings or manual override."""
    if props.use_scene_resolution:
        scene = context.scene
        scale = scene.render.resolution_percentage / 100.0
        w = int(scene.render.resolution_x * scale)
        h = int(scene.render.resolution_y * scale)
        print(
            f"fal.ai: Using scene resolution: {w}x{h} (from {scene.render.resolution_x}x{scene.render.resolution_y} @ {scene.render.resolution_percentage}%)"
        )
        return (w, h)
    print(f"fal.ai: Using manual resolution: {props.width}x{props.height}")
    return (props.width, props.height)


_MESH_VERTEX_SAMPLES = 25


def _iter_anchor_candidates(
    obj: bpy.types.Object, depsgraph: bpy.types.Depsgraph
) -> Any:
    """Yield world-space candidate anchor points for an object, in priority order.

    Origin → bound-box center → bound-box face centers → bound-box corners →
    evenly-spaced mesh vertex samples. The caller picks the first candidate
    that is both visible (projects in-frame) and not occluded.
    """
    from mathutils import Vector  # type: ignore[import-not-found]

    matrix = obj.matrix_world
    yield matrix.translation

    if not hasattr(obj, "bound_box"):
        return

    corners_local = [Vector(c) for c in obj.bound_box]
    if not corners_local:
        return

    min_x = min(c.x for c in corners_local)
    max_x = max(c.x for c in corners_local)
    min_y = min(c.y for c in corners_local)
    max_y = max(c.y for c in corners_local)
    min_z = min(c.z for c in corners_local)
    max_z = max(c.z for c in corners_local)
    mid_x = (min_x + max_x) / 2.0
    mid_y = (min_y + max_y) / 2.0
    mid_z = (min_z + max_z) / 2.0

    yield matrix @ Vector((mid_x, mid_y, mid_z))

    for face_center in (
        Vector((min_x, mid_y, mid_z)),
        Vector((max_x, mid_y, mid_z)),
        Vector((mid_x, min_y, mid_z)),
        Vector((mid_x, max_y, mid_z)),
        Vector((mid_x, mid_y, min_z)),
        Vector((mid_x, mid_y, max_z)),
    ):
        yield matrix @ face_center

    for corner in corners_local:
        yield matrix @ corner

    if getattr(obj, "type", None) == "MESH":
        try:
            mesh = obj.evaluated_get(depsgraph).data
            verts = mesh.vertices
            n = len(verts)
        except (AttributeError, RuntimeError):
            return
        if n == 0:
            return
        stride = max(1, n // _MESH_VERTEX_SAMPLES)
        for i in range(0, n, stride):
            yield matrix @ verts[i].co


def overlay_labels(
    context: bpy.types.Context,
    image_path: str,
    width: int,
    height: int,
    auto_label: bool = False,
) -> None:
    """Overlay text labels on the rendered image using Pillow.

    Finds objects with 'fal_ai_label' custom property, projects their
    world position to 2D screen coordinates, and draws labels.

    :param auto_label: If True, automatically label objects without explicit labels.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("fal.ai: Pillow not available, skipping label overlay")
        return

    scene = context.scene
    camera = scene.camera
    if not camera:
        return

    # Collect labeled objects
    labeled = []

    _skip_types = {"CAMERA", "LIGHT", "EMPTY", "ARMATURE"}
    _skip_names = {"Camera", "Light", "Sun", "Point", "Spot", "Area"}

    for obj in scene.objects:
        if obj.type in _skip_types:
            continue
        if not obj.visible_get():
            continue

        label = obj.get("fal_ai_label")
        if label and isinstance(label, str):
            labeled.append((obj, label))
        elif auto_label:
            name = obj.name
            if name in _skip_names:
                continue
            if len(name) > 4 and name[-4] == "." and name[-3:].isdigit():
                name = name[:-4]
            labeled.append((obj, name))

    if not labeled:
        return

    from mathutils import Vector  # type: ignore[import-not-found]

    depsgraph = context.evaluated_depsgraph_get()
    cam_obj = camera.evaluated_get(depsgraph)
    cam_data = cam_obj.data

    view_matrix = cam_obj.matrix_world.normalized().inverted()
    projection_matrix = cam_obj.calc_matrix_camera(depsgraph, x=width, y=height)

    def project_3d_to_2d(world_pos: Any) -> tuple[int, int] | None:
        """Project a 3D world position to 2D pixel coordinates, clamped to image bounds."""
        co = (
            projection_matrix
            @ view_matrix
            @ Vector((world_pos[0], world_pos[1], world_pos[2], 1.0))
        )
        if co.w <= 0:
            return None
        ndc_x = co.x / co.w
        ndc_y = co.y / co.w
        px = int((ndc_x * 0.5 + 0.5) * width)
        py = int((1.0 - (ndc_y * 0.5 + 0.5)) * height)
        if 0 <= px < width and 0 <= py < height:
            return (px, py)
        return None

    img = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(img)

    base_font_size = max(20, int(height * 0.03))
    font = get_default_font(base_font_size)
    padding = 6
    margin = int(height * 0.04)
    line_width = max(1, base_font_size // 12)

    placed_labels = []

    for obj, label in labeled:
        anchor = None

        for world_pt in _iter_anchor_candidates(obj, depsgraph):
            if camera and is_occluded(
                scene,
                depsgraph,
                camera,
                obj,
                width,
                height,
                override_pos=world_pt,
            ):
                continue
            candidate = project_3d_to_2d(world_pt)
            if candidate is not None:
                anchor = candidate
                break

        if anchor is None:
            continue

        ax, ay = anchor

        bbox = draw.textbbox((0, 0), label, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]

        candidates = [
            (ax + margin, ay - margin - th),
            (ax + margin, ay + margin),
            (ax - margin - tw, ay - margin - th),
            (ax - margin - tw, ay + margin),
            (ax - tw // 2, ay - margin * 2 - th),
            (ax - tw // 2, ay + margin * 2),
        ]

        best = None
        for cx, cy in candidates:
            cx = max(padding, min(cx, width - tw - padding * 2))
            cy = max(padding, min(cy, height - th - padding * 2))
            rect = (cx - padding, cy - padding, cx + tw + padding, cy + th + padding)

            overlaps = False
            for pr in placed_labels:
                if (
                    rect[0] < pr[2]
                    and rect[2] > pr[0]
                    and rect[1] < pr[3]
                    and rect[3] > pr[1]
                ):
                    overlaps = True
                    break
            if not overlaps:
                best = (cx, cy, rect)
                break

        if best is None:
            cx, cy = candidates[0]
            cx = max(padding, min(cx, width - tw - padding * 2))
            cy = max(padding, min(cy, height - th - padding * 2))
            rect = (cx - padding, cy - padding, cx + tw + padding, cy + th + padding)
            best = (cx, cy, rect)

        lx, ly, label_rect = best
        placed_labels.append(label_rect)

        label_center_x = lx + tw // 2
        label_center_y = ly + th // 2
        dist = ((label_center_x - ax) ** 2 + (label_center_y - ay) ** 2) ** 0.5
        if dist > margin * 0.5:
            draw.line(
                [(ax, ay), (label_center_x, label_center_y)],
                fill=(0, 0, 0),
                width=line_width,
            )
            r = max(2, line_width + 1)
            draw.ellipse([ax - r, ay - r, ax + r, ay + r], fill=(0, 0, 0))

        draw.rectangle(
            [label_rect[0], label_rect[1], label_rect[2], label_rect[3]],
            fill=(255, 255, 255),
            outline=(0, 0, 0),
            width=line_width,
        )
        draw.text((lx, ly), label, fill=(0, 0, 0), font=font)

    img.save(image_path)


# ---------------------------------------------------------------------------
# Occlusion testing for labels
# ---------------------------------------------------------------------------
def is_occluded(
    scene: bpy.types.Scene,
    depsgraph: bpy.types.Depsgraph,
    camera: bpy.types.Object,
    obj: bpy.types.Object,
    width: int,
    height: int,
    override_pos: Any = None,
) -> bool:
    """Check if a point (default: object origin) is occluded from camera's view."""

    cam_loc = camera.matrix_world.translation
    obj_loc = override_pos if override_pos is not None else obj.matrix_world.translation

    direction = (obj_loc - cam_loc).normalized()
    distance = (obj_loc - cam_loc).length

    result, location, normal, index, hit_obj, matrix = scene.ray_cast(
        depsgraph, cam_loc + direction * 0.01, direction, distance=distance + 0.01
    )

    if not result:
        return False
    if hit_obj == obj:
        return False
    if hit_obj.parent == obj:
        return False

    hit_dist = (location - cam_loc).length
    obj_dist = distance
    if hit_dist < obj_dist - 0.1:
        return True

    return False


# ---------------------------------------------------------------------------
# Edge detection from render passes (PIL-based)
# ---------------------------------------------------------------------------
def render_to_sketch(render_path: str, width: int, height: int) -> None:
    """Convert a shaded render with freestyle lines into a clean sketch."""
    from PIL import Image, ImageChops, ImageFilter

    img = Image.open(render_path)
    gray = img.convert("L")

    edges = gray.filter(ImageFilter.FIND_EDGES)

    edges2 = gray.filter(
        ImageFilter.Kernel(
            size=(3, 3),
            kernel=[-1, -1, -1, -1, 8, -1, -1, -1, -1],
            scale=1,
            offset=0,
        )
    )

    edges_combined = ImageChops.lighter(edges, edges2)

    threshold = 12
    edge_lines = edges_combined.point(lambda p: 0 if p > threshold else 255)

    freestyle_mask = gray.point(lambda p: 0 if p < 40 else 255)

    combined = ImageChops.multiply(edge_lines, freestyle_mask)

    combined.convert("RGB").save(render_path)


# ---------------------------------------------------------------------------
# Scene depth analysis
# ---------------------------------------------------------------------------
def calc_scene_depth_bounds(
    scene: bpy.types.Scene, camera: bpy.types.Object
) -> tuple[float | None, float | None]:
    """Calculate the actual near/far depth of scene geometry from camera."""
    from mathutils import Vector  # type: ignore[import-not-found]

    cam_loc = camera.matrix_world.translation
    cam_forward = camera.matrix_world.to_3x3() @ Vector((0, 0, -1))
    cam_forward.normalize()

    min_dist = float("inf")
    max_dist = float("-inf")
    found = False

    for obj in scene.objects:
        if obj.type not in {"MESH", "CURVE", "SURFACE", "META", "FONT"}:
            continue
        if not obj.visible_get():
            continue

        bbox = obj.bound_box
        for corner in bbox:
            world_point = obj.matrix_world @ Vector(corner)
            to_point = world_point - cam_loc
            dist = to_point.dot(cam_forward)
            if dist > 0:
                min_dist = min(min_dist, dist)
                max_dist = max(max_dist, dist)
                found = True

    if not found:
        return (None, None)

    return (min_dist, max_dist)


# ---------------------------------------------------------------------------
# Canny edge detection (pure NumPy — no OpenCV / scikit-image)
# ---------------------------------------------------------------------------
def render_to_canny(
    render_path: str,
    width: int,
    height: int,
    low_threshold: int = 100,
    high_threshold: int = 200,
    sigma: float = 1.0,
) -> None:
    """Convert a rendered image to Canny edge detection output.

    Pure NumPy implementation — no OpenCV or scikit-image needed.
    Overwrites the image at render_path with white edges on black background.
    """
    import numpy as np
    from PIL import Image

    img = Image.open(render_path).convert("L")
    pixels = np.array(img, dtype=np.float64)

    # 1. Optional Gaussian blur (separable convolution with reflect padding —
    #    zero-padding here was producing a strong edge ring around the image)
    if sigma > 0:
        size = int(2 * np.ceil(2 * sigma) + 1)
        x = np.arange(size) - size // 2
        kernel = np.exp(-(x**2) / (2 * sigma**2))
        kernel /= kernel.sum()
        pad = size // 2

        padded_h = np.pad(pixels, ((0, 0), (pad, pad)), mode="reflect")
        blurred = np.apply_along_axis(
            lambda row: np.convolve(row, kernel, mode="valid"), axis=1, arr=padded_h
        )
        padded_v = np.pad(blurred, ((pad, pad), (0, 0)), mode="reflect")
        blurred = np.apply_along_axis(
            lambda col: np.convolve(col, kernel, mode="valid"), axis=0, arr=padded_v
        )
    else:
        blurred = pixels

    # 2. Sobel gradients via array slicing
    Gx = (
        -1 * blurred[:-2, :-2]
        + 1 * blurred[:-2, 2:]
        - 2 * blurred[1:-1, :-2]
        + 2 * blurred[1:-1, 2:]
        - 1 * blurred[2:, :-2]
        + 1 * blurred[2:, 2:]
    )
    Gy = (
        1 * blurred[:-2, :-2]
        + 2 * blurred[:-2, 1:-1]
        + 1 * blurred[:-2, 2:]
        - 1 * blurred[2:, :-2]
        - 2 * blurred[2:, 1:-1]
        - 1 * blurred[2:, 2:]
    )

    # L1 magnitude (matches cv2 default; recovers low-contrast edges that L2 misses)
    magnitude = np.abs(Gx) + np.abs(Gy)
    direction = np.arctan2(Gy, Gx)

    # 3. Non-maximum suppression (vectorized)
    angle = direction * 180.0 / np.pi
    angle[angle < 0] += 180

    # Quantize to 4 directions: 0=horiz, 1=diag45, 2=vert, 3=diag135
    d = np.round(angle / 45.0) % 4

    h, w = magnitude.shape
    suppressed = np.zeros_like(magnitude)

    # Pad magnitude with edge replication so border pixels aren't auto-suppressed
    mag_pad = np.pad(magnitude, 1, mode="edge")

    # Direction 0 (horizontal): compare with left/right neighbors
    mask0 = d == 0
    q0 = mag_pad[1 : h + 1, 2 : w + 2]  # right
    r0 = mag_pad[1 : h + 1, 0:w]  # left

    # Direction 1 (diagonal 45°): compare with bottom-left/top-right
    mask1 = d == 1
    q1 = mag_pad[2 : h + 2, 0:w]  # bottom-left
    r1 = mag_pad[0:h, 2 : w + 2]  # top-right

    # Direction 2 (vertical): compare with top/bottom neighbors
    mask2 = d == 2
    q2 = mag_pad[2 : h + 2, 1 : w + 1]  # below
    r2 = mag_pad[0:h, 1 : w + 1]  # above

    # Direction 3 (diagonal 135°): compare with top-left/bottom-right
    mask3 = d == 3
    q3 = mag_pad[0:h, 0:w]  # top-left
    r3 = mag_pad[2 : h + 2, 2 : w + 2]  # bottom-right

    for mask, q, r in [
        (mask0, q0, r0),
        (mask1, q1, r1),
        (mask2, q2, r2),
        (mask3, q3, r3),
    ]:
        keep = mask & (magnitude >= q) & (magnitude >= r)
        suppressed[keep] = magnitude[keep]

    # 4. Double threshold + hysteresis
    strong_val = 255.0
    weak_val = 50.0
    result = np.zeros_like(suppressed)
    strong_mask = suppressed >= high_threshold
    weak_mask = (suppressed >= low_threshold) & (~strong_mask)
    result[strong_mask] = strong_val
    result[weak_mask] = weak_val

    # Hysteresis: iteratively promote weak pixels adjacent to strong ones
    # using morphological dilation of the strong mask
    promoted = strong_mask.copy()
    while True:
        # Dilate: any weak pixel with a strong neighbor becomes strong
        dilated = np.zeros_like(promoted)
        dilated[1:, :] |= promoted[:-1, :]
        dilated[:-1, :] |= promoted[1:, :]
        dilated[:, 1:] |= promoted[:, :-1]
        dilated[:, :-1] |= promoted[:, 1:]
        dilated[1:, 1:] |= promoted[:-1, :-1]
        dilated[1:, :-1] |= promoted[:-1, 1:]
        dilated[:-1, 1:] |= promoted[1:, :-1]
        dilated[:-1, :-1] |= promoted[1:, 1:]

        new_strong = weak_mask & dilated & (~promoted)
        if not new_strong.any():
            break
        promoted |= new_strong

    result[promoted] = strong_val
    result[~promoted] = 0

    # Pad result back to original size (Sobel shrinks by 1 on each edge);
    # replicate the outermost row/col into the 1-pixel border so it doesn't
    # show up as a dark frame.
    res = result.astype(np.uint8)
    full = np.zeros((height, width), dtype=np.uint8)
    full[1 : 1 + res.shape[0], 1 : 1 + res.shape[1]] = res
    full[0, 1 : 1 + res.shape[1]] = res[0, :]
    full[-1, 1 : 1 + res.shape[1]] = res[-1, :]
    full[:, 0] = full[:, 1]
    full[:, -1] = full[:, -2]

    Image.fromarray(full).convert("RGB").save(render_path)
