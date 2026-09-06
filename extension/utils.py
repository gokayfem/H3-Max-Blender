from __future__ import annotations

import base64
import mimetypes
import os
import re
import tempfile
import time
import warnings
from collections.abc import Iterator
from contextlib import contextmanager
from functools import wraps
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from .preferences import get_api_key, get_output_dir

if TYPE_CHECKING:
    import bpy
    from PIL import ImageFont

__all__ = [
    "snake_case",
    "path_to_data_uri",
    "download_file",
    "upload_file",
    "upload_blender_image",
    "snapshot_compositor",
    "restore_compositor",
    "snapshot_compositor_context",
    "get_world_color",
    "set_world_color",
    "disconnect_world_color_links",
    "restore_world_color_links",
    "get_default_font",
    "get_endpoint_pricing",
    "get_endpoint_description",
    "get_playground_url",
    "get_request_playground_url",
    "open_folder",
    "get_eevee_engine",
    "get_compositor_node_tree",
    "ensure_compositor_enabled",
    "create_compositor_output_node",
]


def snake_case(name: str) -> str:
    """
    Convert a name to snake case.
    :param name: name to convert
    :return: snake case name
    """
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def path_to_data_uri(path: str, mime_type: str | None = None) -> str:
    """
    Convert a file path to a data URI.
    :param path: path to the file
    :param mime_type: MIME type of the file
    :return: data URI of the file
    """
    if not mime_type:
        mime_type, _ = mimetypes.guess_type(path)
        if not mime_type:
            warnings.warn(
                f"Could not determine MIME type for {path}, using application/octet-stream"
            )
            mime_type = "application/octet-stream"
    with open(path, "rb") as f:
        return f"data:{mime_type};base64,{base64.b64encode(f.read()).decode('utf-8')}"


# ---------------------------------------------------------------------------
# Compliance helpers
# ---------------------------------------------------------------------------


def internet_access_allowed() -> bool:
    """
    Check if internet access is allowed.
    :see: https://developer.blender.org/docs/handbook/extensions/addon_guidelines/
    """
    import bpy

    return bpy.app.online_access


def requires_internet_access(fn: Callable) -> Callable:
    """Decorator to check if the function requires internet access."""

    @wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        if not internet_access_allowed():
            raise RuntimeError("This function requires internet access.")
        return fn(*args, **kwargs)

    return wrapper


# ---------------------------------------------------------------------------
# File download/upload helpers
# ---------------------------------------------------------------------------


@requires_internet_access
def download_file(url: str, suffix: str = ".bin", to_temp: bool = False) -> str:
    """
    Download a URL to the output directory (or temp if specified).

    :param url: URL of the file
    :param suffix: suffix/extension of the file
    :param to_temp: if True, save to temp directory instead of output dir
    :return: local path of the downloaded file
    """
    import urllib.request
    import uuid

    ext = Path(url.split("?")[0]).suffix or suffix
    filename = f"fal_{uuid.uuid4().hex[:8]}{ext}"

    if to_temp:
        filepath = os.path.join(tempfile.gettempdir(), filename)
    else:
        output_dir = get_output_dir()
        filepath = os.path.join(output_dir, filename)

    urllib.request.urlretrieve(url, filepath)
    print(f"fal.ai: Downloaded {url} -> {filepath}")
    return filepath


@requires_internet_access
def upload_file(filepath: str) -> str:
    """
    Upload a file to fal CDN and return the URL.
    :param filepath: path to the file
    :return: URL of the uploaded file
    """
    import fal_client

    key = get_api_key()
    if not key:
        raise RuntimeError(
            "No fal.ai API key configured. Set it in Edit > Preferences > Add-ons > fal.ai, or set the FAL_KEY environment variable."
        )

    client = fal_client.SyncClient(key=key)
    url = client.upload_file(filepath)
    print(f"fal.ai: Uploaded video {filepath} -> {url}")
    return url


@requires_internet_access
def upload_blender_image(image: bpy.types.Image) -> str:
    """
    Save a Blender image to temp file and upload to fal CDN.
    :param image: bpy.types.Image instance
    :return: URL of the uploaded file
    """
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        old_path = image.filepath_raw
        old_format = image.file_format
        image.filepath_raw = f.name
        image.file_format = "PNG"
        image.save()
        image.filepath_raw = old_path
        image.file_format = old_format
        return upload_file(f.name)


# ---------------------------------------------------------------------------
# Compositor snapshot/restore helpers
# ---------------------------------------------------------------------------


def snapshot_compositor(tree: bpy.types.NodeTree) -> list[dict]:
    """Snapshot compositor node tree for later restoration."""
    snapshot = []
    for node in tree.nodes:
        info = {
            "type": node.bl_idname,
            "name": node.name,
            "location": (node.location.x, node.location.y),
        }
        snapshot.append(info)
    links = []
    for link in tree.links:
        links.append(
            {
                "from_node": link.from_node.name,
                "from_socket": link.from_socket.name,
                "to_node": link.to_node.name,
                "to_socket": link.to_socket.name,
            }
        )
    return [{"nodes": snapshot, "links": links}]


def restore_compositor(tree: bpy.types.NodeTree, saved: list[dict]) -> None:
    """Restore compositor node tree from snapshot."""
    if not saved or not saved[0].get("nodes"):
        return

    data = saved[0]
    node_map = {}

    for info in data["nodes"]:
        try:
            node = tree.nodes.new(info["type"])
            node.name = info["name"]
            node.location = info["location"]
            node_map[info["name"]] = node
        except Exception as e:
            print(f"fal.ai: Could not restore compositor node {info['name']}: {e}")

    for link_info in data.get("links", []):
        try:
            from_node = node_map.get(link_info["from_node"])
            to_node = node_map.get(link_info["to_node"])
            if from_node and to_node:
                from_sock = from_node.outputs.get(link_info["from_socket"])
                to_sock = to_node.inputs.get(link_info["to_socket"])
                if from_sock and to_sock:
                    tree.links.new(from_sock, to_sock)
        except Exception as e:
            print(f"fal.ai: Could not restore compositor link: {e}")


@contextmanager
def snapshot_compositor_context(tree: bpy.types.NodeTree) -> Iterator[None]:
    """Context manager for snapshotting and restoring compositor node tree."""
    saved = snapshot_compositor(tree)
    try:
        yield
    finally:
        restore_compositor(tree, saved)


# ---------------------------------------------------------------------------
# World color helpers (handle node tree vs simple color)
# ---------------------------------------------------------------------------


def get_world_color(world: bpy.types.World) -> tuple[float, float, float]:
    """Get current world background color, from nodes or fallback."""
    if world.use_nodes and world.node_tree:
        for node in world.node_tree.nodes:
            if node.type == "BACKGROUND":
                c = node.inputs["Color"].default_value
                return (c[0], c[1], c[2])
    return tuple(world.color)


def set_world_color(world: bpy.types.World, color: tuple[float, float, float]) -> None:
    """Set world background color, updating nodes if present."""
    if world.use_nodes and world.node_tree:
        for node in world.node_tree.nodes:
            if node.type == "BACKGROUND":
                node.inputs["Color"].default_value = (
                    color[0],
                    color[1],
                    color[2],
                    1.0,
                )
                return
    world.color = color


def disconnect_world_color_links(
    world: bpy.types.World,
) -> list[tuple[bpy.types.NodeSocket, bpy.types.NodeSocket]]:
    """Remove links into Background node Color input, return them for later restore.

    This ensures ``set_world_color`` actually takes effect when an Environment
    Texture (HDRI) is connected to the Background node.
    """
    saved: list[tuple[bpy.types.NodeSocket, bpy.types.NodeSocket]] = []
    if not (world and world.use_nodes and world.node_tree):
        return saved
    tree = world.node_tree
    for node in tree.nodes:
        if node.type == "BACKGROUND":
            color_input = node.inputs["Color"]
            for link in list(color_input.links):
                saved.append((link.from_socket, link.to_socket))
                tree.links.remove(link)
    return saved


def restore_world_color_links(
    world: bpy.types.World,
    saved_links: list[tuple[bpy.types.NodeSocket, bpy.types.NodeSocket]],
) -> None:
    """Re-create links previously removed by :func:`disconnect_world_color_links`."""
    if not (world and world.use_nodes and world.node_tree) or not saved_links:
        return
    tree = world.node_tree
    for from_socket, to_socket in saved_links:
        tree.links.new(from_socket, to_socket)


# ---------------------------------------------------------------------------
# Font loading for label overlay
# ---------------------------------------------------------------------------
def get_default_font(size: int) -> ImageFont.ImageFont:
    """Load a readable font cross-platform. Falls back gracefully."""
    from PIL import ImageFont

    font_candidates = [
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/SFNSMono.ttf",
        "/Library/Fonts/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibri.ttf",
    ]

    for path in font_candidates:
        try:
            return ImageFont.truetype(path, size)
        except (IOError, OSError):
            continue

    print("fal.ai: No system fonts found, using default (labels may be small)")
    return ImageFont.load_default()


# ---------------------------------------------------------------------------
# Pricing helpers
# ---------------------------------------------------------------------------

_PRICE_LINE_PREFIXES = ("- **Price**: ", "- Price: ")


def _strip_markdown_for_display(text: str) -> str:
    """Turn llms.txt-style markdown into plain text for Blender UI labels."""
    lines_out: list[str] = []
    for line in text.splitlines():
        s = line
        s = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", s)
        s = re.sub(r"`([^`]+)`", r"\1", s)
        while "**" in s:
            next_s = re.sub(r"\*\*(.+?)\*\*", r"\1", s, count=1)
            if next_s == s:
                break
            s = next_s
        while "__" in s:
            next_s = re.sub(r"__(.+?)__", r"\1", s, count=1)
            if next_s == s:
                break
            s = next_s
        s = re.sub(r"(?<![*`])\*([^*\n]+)\*(?![*`])", r"\1", s)
        s = re.sub(r"^#+\s*", "", s)
        lines_out.append(s)
    return "\n".join(lines_out)


@requires_internet_access
def get_endpoint_pricing(endpoint: str, max_retries: int = 3) -> str:
    """
    Returns the pricing for a model.
    :param model: model name
    :return: pricing for the model
    """
    import urllib.request

    url = f"https://fal.ai/models/{endpoint.strip('/')}/llms.txt"
    for retry_num in range(max_retries):
        try:
            with urllib.request.urlopen(url) as response:
                llms_txt = response.read().decode("utf-8")
                break
        except Exception as e:
            print(f"fal.ai: Could not get pricing for {endpoint}: {e}")
            if retry_num == max_retries - 1:
                raise
            time.sleep(0.5 * 2**retry_num)

    # Look for text between '## Pricing' and 'For more details, see [fal.ai pricing]'
    needle_start = "## Pricing"
    needle_end = "For more details, see [fal.ai pricing]"
    pricing_start = llms_txt.find(needle_start) + len(needle_start)
    pricing_end = llms_txt.find(needle_end)
    if pricing_start == -1 or pricing_end == -1:
        raise ValueError(f"Could not find pricing for {endpoint}")
    pricing_text = llms_txt[pricing_start:pricing_end].strip()
    for prefix in _PRICE_LINE_PREFIXES:
        if pricing_text.startswith(prefix):
            pricing_text = pricing_text[len(prefix) :].strip()
            break

    return _strip_markdown_for_display(pricing_text)


# Cache for endpoint descriptions (avoid repeated fetches)
_endpoint_descriptions: dict[str, str] = {}


@requires_internet_access
def get_endpoint_description(endpoint: str, max_retries: int = 3) -> str:
    """
    Returns the description for a model from llms.txt.

    :param endpoint: model endpoint ID
    :return: description text (blockquote section after title)
    """
    if endpoint in _endpoint_descriptions:
        return _endpoint_descriptions[endpoint]

    import urllib.request

    url = f"https://fal.ai/models/{endpoint.strip('/')}/llms.txt"
    for retry_num in range(max_retries):
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                llms_txt = response.read().decode("utf-8")
                break
        except Exception as e:
            if retry_num == max_retries - 1:
                return ""
            time.sleep(0.3 * 2**retry_num)

    # Look for blockquote after title (> description...)
    lines = llms_txt.splitlines()
    description_lines = []
    in_description = False
    for line in lines:
        if line.startswith("> "):
            in_description = True
            description_lines.append(line[2:].strip())
        elif in_description:
            if line.strip() == "" or line.startswith("#"):
                break
            if line.startswith("> "):
                description_lines.append(line[2:].strip())

    description = " ".join(description_lines)
    _endpoint_descriptions[endpoint] = description
    return description


def get_playground_url(endpoint: str) -> str:
    """
    Get the playground URL for an endpoint.

    :param endpoint: model endpoint ID (e.g. fal-ai/flux-2/klein/9b/edit)
    :return: playground URL
    """
    return f"https://fal.ai/models/{endpoint.strip('/')}/playground"


def get_request_playground_url(endpoint: str, request_id: str) -> str:
    """
    Get the playground URL for a specific request.

    :param endpoint: model endpoint ID
    :param request_id: request UUID from fal API
    :return: playground URL with request preloaded
    """
    base = get_playground_url(endpoint)
    return f"{base}?requestId={request_id}"


def open_folder(path: str) -> None:
    """
    Open a folder in the system file browser.

    Works cross-platform: macOS (open), Windows (explorer), Linux (xdg-open).
    """
    import subprocess
    import sys

    path = os.path.abspath(os.path.expanduser(path))

    if sys.platform == "darwin":
        subprocess.run(["open", path])
    elif sys.platform == "win32":
        subprocess.run(["explorer", path])
    else:
        subprocess.run(["xdg-open", path])


def get_eevee_engine() -> str:
    """
    Get the correct EEVEE engine name for the current Blender version.

    Blender 4.x uses 'BLENDER_EEVEE_NEXT' (transitional name).
    Blender 5.x dropped the '_NEXT' suffix — it's just 'BLENDER_EEVEE'.
    """
    import bpy

    # Check Blender version (bpy.app.version is a tuple like (5, 2, 0))
    if bpy.app.version >= (5, 0, 0):
        return "BLENDER_EEVEE"
    return "BLENDER_EEVEE_NEXT"


def get_compositor_node_tree(scene: bpy.types.Scene) -> bpy.types.NodeTree | None:
    """
    Get the compositor node tree for a scene, handling API changes.

    Blender 4.x: scene.node_tree (when scene.use_nodes is True)
    Blender 5.x: scene.compositing_node_group
    """
    import bpy

    if bpy.app.version >= (5, 0, 0):
        return getattr(scene, "compositing_node_group", None)
    # Blender 4.x
    if scene.use_nodes:
        return scene.node_tree
    return None


def ensure_compositor_enabled(scene: bpy.types.Scene) -> bpy.types.NodeTree:
    """
    Ensure the compositor is enabled and return the node tree.

    Blender 4.x: sets scene.use_nodes = True, returns scene.node_tree
    Blender 5.x: creates compositing_node_group if needed, returns it

    In Blender 5, scene.use_nodes is deprecated (always returns True).
    Use scene.render.use_compositing to enable/disable compositing in renders.
    """
    import bpy

    if bpy.app.version >= (5, 0, 0):
        # Blender 5.x
        tree = scene.compositing_node_group
        if tree is None:
            tree = bpy.data.node_groups.new("Compositing", "CompositorNodeTree")
            scene.compositing_node_group = tree
        return tree
    else:
        # Blender 4.x
        scene.use_nodes = True
        return scene.node_tree


def has_usable_compositor(scene: bpy.types.Scene) -> bool:
    """Return True when the scene's compositor can produce an image.

    Blender refuses to render with ``use_compositing=True`` when the tree is
    empty or missing an output node, and the error only surfaces at render
    time. Check up front so we can skip compositing for fresh 5.x scenes
    (which default to ``use_compositing=True`` with an empty group).
    """

    tree = get_compositor_node_tree(scene)
    if tree is None:
        return False
    output_types = {
        "NodeGroupOutput",
        "CompositorNodeComposite",
        "CompositorNodeOutputFile",
    }
    return any(node.bl_idname in output_types for node in tree.nodes)


def create_compositor_output_node(
    tree: bpy.types.NodeTree,
) -> bpy.types.Node:
    """
    Create the compositor output node, handling API changes.

    Blender 4.x: CompositorNodeComposite (has 'Image' input)
    Blender 5.x: NodeGroupOutput (need to create socket via interface)

    Returns the created node. In Blender 5, also sets up the 'Image' socket.
    """
    import bpy

    if bpy.app.version >= (5, 0, 0):
        # Blender 5.x: compositor is now a node group
        output = tree.nodes.new(type="NodeGroupOutput")
        # Create an 'Image' input socket on the node group interface
        tree.interface.new_socket(
            name="Image", in_out="OUTPUT", socket_type="NodeSocketColor"
        )
        return output
    else:
        # Blender 4.x: traditional compositor output
        return tree.nodes.new("CompositorNodeComposite")
