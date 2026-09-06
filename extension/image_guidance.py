"""Image-only geometry guidance, prepared once per scene revision without bpy."""
import base64
import hashlib
import io


def image_uri(data):
    mime = 'image/jpeg' if data.startswith(b'\xff\xd8') else 'image/png'
    return f'data:{mime};base64,' + base64.b64encode(data).decode('ascii')


def detail_sheet(image_bytes):
    """Keep one full view and eight central-object crops, without stretching."""
    from PIL import Image, ImageDraw, ImageOps
    source = Image.open(io.BytesIO(image_bytes)).convert('RGB')
    w, h = source.size
    # Normalized coordinates from the measured central-object ship fixture.
    # The separate full-frame image remains authoritative for arbitrary layouts.
    boxes = [(200,70,430,240),(350,65,540,240),(400,175,640,355),
             (210,180,430,350),(0,0,832,480),(230,120,380,290),
             (310,155,535,260),(255,185,520,300),(260,230,590,360)]
    sheet = Image.new('RGB', (1248,798), '#252525')
    draw = ImageDraw.Draw(sheet)
    for i, box in enumerate(boxes):
        crop = source if i == 4 else source.crop(tuple(round(v * (w/832 if j%2 == 0 else h/480)) for j,v in enumerate(box)))
        crop = ImageOps.contain(crop, (416,240))
        x, y = i%3*416, i//3*266
        sheet.paste(crop, (x+(416-crop.width)//2, y+26+(240-crop.height)//2))
        draw.text((x+8,y+5), 'TARGET CAMERA / FULL FRAME' if i == 4 else f'DETAIL {i+1}', fill='white')
    output = io.BytesIO()
    sheet.save(output, format='JPEG', quality=94)
    return output.getvalue()


def prepare(image_bytes, style_images, mode, buffers=None):
    if mode not in {'IMAGE', 'DETAIL', 'MATERIAL', 'PER_STYLE', 'PER_STYLE_TEXT'}:
        raise ValueError('Unsupported image guidance mode')
    if mode == 'PER_STYLE_TEXT':
        style_images = []
    detail = detail_sheet(image_bytes) if mode in {'DETAIL','MATERIAL','PER_STYLE', 'PER_STYLE_TEXT'} else None
    common = [image_uri(image_bytes)]
    if detail is not None:
        common.append(image_uri(detail))
    if mode in {'PER_STYLE','PER_STYLE_TEXT'} and (not buffers or len(buffers) != 2):
        raise ValueError('Per-style mode requires fresh normals and silhouette')
    return dict(mode=mode, buffers=[image_uri(b) for b in buffers] if buffers else [], common=common, styles=[image_uri(data) for data in style_images],
                source_sha256=hashlib.sha256(image_bytes).hexdigest(),
                detail_sha256=hashlib.sha256(detail).hexdigest() if detail else None,
                style_sha256=[hashlib.sha256(data).hexdigest() for data in style_images])


def payload(bundle, prompt, resolution, seed, style_index):
    if resolution not in {'480P','768P'}:
        raise ValueError('Unsupported resolution')
    images = list(bundle['common'])
    if bundle.get('mode') in {'PER_STYLE','PER_STYLE_TEXT'}:
        full = bundle['common'][0]
        images = ([full]*3 if style_index == 0 else
                  [full, *bundle['buffers']] if style_index == 1 else
                  [full] if style_index == 2 else list(bundle['common']))
    if bundle['styles'] and bundle.get('mode') != 'PER_STYLE_TEXT':
        images.append(bundle['styles'][style_index])
    # Deliberately no video references: all grid guidance is image-only.
    return dict(prompt=prompt, duration=5, resolution=resolution, aspect_ratio='16:9',
                seed=seed, prompt_expansion_mode='balanced', enable_safety_checker=True,
                sync_mode=False, reference_image_urls=images)
