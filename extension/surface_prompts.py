"""Appearance controls independent of the accepted camera/geometry guidance."""
TEMPORAL = (
    'One continuous view of the CURRENT assembly with its surface treatment already applied. The current object at exactly its current construction stage and its environment '
    'are already visible at time 0 and remain the same scene through time 5 seconds. '
    'No transition, cut, dissolve, crossfade, wipe, reveal, morph, material transformation, '
    'lighting change, weather change or background replacement anywhere in the clip. '
    'Reference pictures are simultaneous conditioning inputs, NOT a sequence of shots. '
    'Never display a reference picture or animate from a reference picture into the scene. '
    'The STYLE input is a nonspatial material swatch, never sky, ocean, mist or moving scenery. '
    'Keep illumination, exposure, palette, material finish and sea color constant for the entire clip. '
    'Only tiny local water ripples move; no traveling reflections, fog or clouds sweeping across the frame. '
)
REALISM = (
    'Give the existing vessel rich, physically plausible construction detail expressed in the chosen visual medium. '
    'Refine only existing parts with thin welded joints, precise fitting interfaces, subtle wear and believable material response. '
    'Preserve the accepted component layout, proportions and silhouette. '
    'Remove unintentional polygon bands and blockout shading. '
    'Detail only components listed in CURRENT VISIBLE GEOMETRY; never add a missing assembly. '
)
STYLES = (
    'CARTOON ONLY: polished 2D feature-animation cel rendering with crisp intentional outer contours, '
    'two-step shadow shapes and flat opaque painted colors. Petrol-blue main surface, warm ivory secondary surfaces, coral-orange existing small parts, turquoise illustrated water. '
    'Draw fine construction details as clean designed graphic accents. No photographic shading or gray clay. '
    'Every pixel of the ship AND water is an intentional 2D drawing: clean flat color shapes, graphic highlights and illustrated ripple lines. No 3D render and no photographic ocean. Keep the drawing and contour thickness consistent from first frame to last. ',
    'CLAYMATION ONLY: handcrafted plasticine surface treatment at exactly the input object scale, terracotta main surfaces, warm cream secondary surfaces, slate-blue existing small parts, seafoam clay water. '
    'Visible subtle fingerprints, tool marks, rounded hand-smoothed clay edges and tiny modeled fittings. '
    'Small existing recesses are dark inset clay. Soft stable diffuse light, matte tactile clay, no shiny plastic. '
    'The sea is physically sculpted plasticine with handcrafted ripple ridges, not liquid photographic water. Keep the current object completely still. No assembly or clay morphing. ',
    'PHOTOREALISTIC ONLY: the exact currently visible steel assembly photographed in neutral natural daylight. '
    'Deep navy marine enamel on main surfaces, ivory paint on secondary surfaces, stainless finish on existing small parts, dark teal ocean. '
    'Layered paint roughness, fine weld beads, realistic glazing reflections, rubber seals, subtle salt residue, '
    'waterline staining, exposed bolt heads on existing joints and carefully weathered machinery. '
    'High-frequency photographic surface detail and physically based light; no illustration, miniature, toy or plastic blockout appearance. ',
    'STYLIZED GOUACHE ONLY: sophisticated painted maritime illustration with indigo shadows, burnt-copper main surfaces, ivory secondary surfaces and dusty turquoise water. '
    'Confident dry-brush marks, opaque pigment, subtle paper tooth and precise painted mechanical accents. '
    'Represent welds, fittings, glazing and weathering through fine deliberate brushwork. '
    'The painted textures stay attached to each surface, with no animated brushstrokes or paint spreading. '
    'The entire frame is ONE finished gouache illustration of this boat on a painted sea. The sea has coherent painted waves, not random paint patches. No color chart, material sample, swatch, abstract panel or collage is visible. Never dissolve into photography. ',
)
DETAILS = (
    'Keep the entire top closed and solid. Limit detail to paint, faint welded joints and a subtle waterline stain. ',
    'Keep the entire top closed and solid. Limit detail to paint, faint welded joints and a subtle waterline stain. ',
    'The plain enclosure remains closed: fine weld beads at its existing corners and realistic enamel on its blank walls. ',
    'Existing window interiors are dark reflective glass with thin rubber gaskets and precise metal frames. '
    'Existing roof edges have realistic thin metal flashing and subtle water streaks. ',
    'Existing glazing has depth and reflections; the existing mast has small attachment collars and metal fasteners. '
    'The existing exhaust has heat-discolored metal around its modeled cap. ',
    'Existing glazing has depth and reflections. Within the existing crane arm add realistic pivot pins, '
    'hydraulic fittings, a narrow hose and worn metal at joints, without moving or enlarging the arm. ',
    'Existing glazing has dark reflections and thin gaskets. The existing crane has fine pivot pins and hydraulic fittings. '
    'Existing rail posts have small welded mounting feet and metal fasteners. Existing tenders have believable rubber and fabric finish. ',
)


def appearance(style_index, stage_index):
    return TEMPORAL + REALISM + STYLES[style_index] + DETAILS[stage_index]
