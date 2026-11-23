"""Reletter the native status tabs with the game's bitmap font."""
import json
from PIL import Image, ImageFilter
from title_version import METRICS, line, load_font

TABS = (
    ((65, 10, 370, 69), 63, "Unit Stats", True),
    ((530, 14, 781, 74), 525, "Weapon Stats", False),
    ((65, 98, 370, 158), 63, "Unit Stats", False),
    ((530, 98, 781, 158), 525, "Weapon Stats", True),
    ((66, 182, 489, 244), 65, "Intermission", True),
)


def reletter(original, font_path):
    if original.size != (1024, 272):
        raise ValueError("Unexpected status-tab texture size")
    result = original.copy()
    font = load_font(font_path)
    metrics = json.loads(METRICS.read_text())
    for box, sample_x, label, active in TABS:
        left, top, right, bottom = box
        field = original.crop((sample_x, top, sample_x + 1, bottom))
        field = field.resize((right - left, bottom - top), Image.Resampling.NEAREST)
        mask = line(label, font, metrics, size=32)
        mask.thumbnail((field.width - 24, 32), Image.Resampling.LANCZOS)
        layer = Image.new("L", field.size)
        layer.paste(mask, ((field.width - mask.width) // 2, (field.height - mask.height) // 2))
        if active:
            field.paste((52, 173, 214, 255), (0, 0, *field.size),
                        layer.filter(ImageFilter.GaussianBlur(4)))
        field.paste((241, 253, 255, 255) if active else (180, 202, 225, 255),
                    (0, 0, *field.size), layer)
        result.paste(field, (left, top))
    return result


def roster_label(font_path):
    font = load_font(font_path)
    metrics = json.loads(METRICS.read_text())
    return glowing_label("Ally Roster", (280, 64), font, metrics)


def glowing_label(text, size, font, metrics):
    mask = line(text, font, metrics, size=39)
    mask.thumbnail((size[0] - 18, size[1] - 16), Image.Resampling.LANCZOS)
    sprite = Image.new("RGBA", size)
    alpha = Image.new("L", sprite.size)
    alpha.paste(mask, ((sprite.width - mask.width) // 2, (sprite.height - mask.height) // 2))
    glow = alpha.filter(ImageFilter.GaussianBlur(4))
    sprite.paste((120, 236, 251, 255), (0, 0, *sprite.size), glow)
    sprite.paste((244, 253, 255, 255), (0, 0, *sprite.size), alpha)
    return sprite


def upgrade_labels(font_path):
    font = load_font(font_path)
    metrics = json.loads(METRICS.read_text())
    for top, text in ((576, "Upgrade Unit"), (640, "Upgrade Item")):
        yield (0, top, 512, top + 64), glowing_label(text, (512, 64), font, metrics)


def report_and_level(atlas, font_path):
    """Fit the level-up sprite in one native tile and letter the Situation header."""
    if atlas.size != (512, 512):
        raise ValueError("Unexpected battle notification texture size")
    result = atlas.copy()
    font = load_font(font_path)
    metrics = json.loads(METRICS.read_text())

    # Clear the previous lettering, including the fragments outside each visible tile.
    result.paste((0, 0, 0, 0), (272, 128, 512, 192))
    result.paste((0, 0, 0, 0), (272, 192, 352, 256))
    level_tile = Image.new("RGBA", (224, 64))
    level = line("Level Up!", font, metrics, size=43)
    level.thumbnail((level_tile.width - 26, 43), Image.Resampling.LANCZOS)
    layer = Image.new("L", level_tile.size)
    layer.paste(level, ((layer.width - level.width) // 2, (layer.height - level.height) // 2))
    bold = layer.filter(ImageFilter.MaxFilter(3))
    level_tile.paste((255, 208, 17, 255), (0, 0, *level_tile.size), bold.filter(ImageFilter.MaxFilter(7)))
    level_tile.paste((22, 16, 12, 255), (0, 0, *level_tile.size), bold)
    result.paste(level_tile, (272, 128))

    # The remaining part of the gradient and the outer banner frame stay native.
    left, top, right, bottom = (64, 289, 304, 340)
    field = atlas.crop((300, top, 301, bottom)).resize((right - left, bottom - top))
    label = line("Battle Report", font, metrics, size=39)
    label.thumbnail((field.width - 16, 39), Image.Resampling.LANCZOS)
    layer = Image.new("L", field.size)
    layer.paste(label, ((field.width - label.width) // 2, (field.height - label.height) // 2))
    bold = layer.filter(ImageFilter.MaxFilter(3))
    field.paste((242, 248, 255, 255), (0, 0, *field.size), bold.filter(ImageFilter.MaxFilter(5)))
    field.paste((23, 62, 119, 255), (0, 0, *field.size), bold)
    result.paste(field, (left, top))
    return result
