"""Literal stage descriptions for the fixed-camera ship experiment."""
COMMON = (
    'Render the exact existing solid geometry in Image 1 with finished surface materials. '
    'Treat Image 1 as the final approved shape and camera, not a sketch to redesign. '
    'Keep every visible corner, surface boundary, overlap and empty region in its original pixel position. '
    'Apply smooth paint, realistic roughness, soft lighting and reflections to these existing surfaces. '
    'Do not replace a solid surface with a cavity or opening. Do not add new major components. '
    'The object is rigid and motionless throughout all five seconds. '
    'The camera projection, lens, angle, framing and magnification remain identical to Image 1 in every frame. '
    'The gray ground becomes calm water; keep its reflections subdued and below the object. '
    'Only very faint water ripples move. '
    'STYLE controls surface palette and lighting only; keep geometry, camera and scene layout from Image 1. '
)
INVENTORIES = (
    'Exactly one low closed solid hull. Its entire visible top is a continuous flat solid surface. '
    'Retain that top surface intact, with nothing attached above it. This is a sealed hull blank.',
    'Exactly one elongated closed solid hull. Its entire visible top is a continuous flat solid surface. '
    'Retain the longer proportions and intact top, with nothing attached above it. This is a sealed hull blank.',
    'Exactly one closed hull and one low rectangular solid enclosure on its top. '
    'The enclosure has plain continuous walls and a solid top. Preserve all uncovered deck regions.',
    'Exactly the visible hull, lower enclosure, upper enclosure and thin projecting roof. '
    'Only the existing small rectangular face frames receive dark glass inside their current borders. '
    'Retain all roof edges and the uncovered deck.',
    'Retain the visible hull, two enclosures, glazing and roof. The visible thin vertical rod and crossbar '
    'are a mast; the short solid stack is an exhaust. Preserve their exact heights and locations.',
    'Retain all existing visible assemblies. The bent arm and hanging line at the rear are the crane '
    'and cable. Preserve their exact joints, lengths and silhouette.',
    'Retain every existing visible assembly. The newly visible perimeter rods are slender metal rails; '
    'the small side solids are compact tenders. Finish their surfaces without changing any outline.',
)


def for_stage(index):
    try:
        from . import surface_prompts
    except ImportError:
        import surface_prompts
    return COMMON + surface_prompts.DETAILS[index] + 'CURRENT VISIBLE GEOMETRY — HIGHEST PRIORITY: ' + INVENTORIES[index]
