"""Config, generation plan and presentation for Ray Model Card (no Comfy imports)."""
from dataclasses import dataclass
import math
import os
import re
import secrets
import unicodedata

from PIL import Image, ImageDraw, ImageFont


DEFAULT_CONFIG = """+ANIMALS
Great white shark swimming underwater::a great white shark swimming through clear blue ocean water, full body viewed from the side, detailed skin, gills and fins, natural underwater light, realistic wildlife photograph
Red fox sitting in fresh snow::a red fox sitting in fresh snow, full body, detailed orange and white fur, winter daylight, wildlife photograph
Blue and yellow macaw on a branch::a blue and yellow macaw perched on a wooden branch, full body, detailed feathers, natural light, wildlife photograph
African elephant crossing dry savanna::an African elephant walking across a dry savanna, full body, detailed wrinkled skin, daylight, wildlife photograph
Green tree frog on a wet leaf::a bright green tree frog sitting on a broad wet leaf, close-up, detailed moist skin, natural rainforest light, wildlife photograph
Green iguana on a sunlit rock::a green iguana resting on a sunlit rock, full body and long tail fully visible, detailed scales and dorsal spines, natural daylight, realistic wildlife photograph

+PEOPLE
10yo Korean girl, black bob and red glasses::portrait of a 10-year-old Korean girl, straight black hair in a shoulder-length bob, wearing round red glasses, natural daylight, realistic photograph
20yo Nigerian man, scar through left eyebrow::portrait of a 20-year-old Nigerian man, short black hair, distinctive small scar through his left eyebrow, natural daylight, realistic photograph
30yo Irish woman, auburn hair and freckles::portrait of a 30-year-old Irish woman, long auburn hair, prominent freckles across her cheeks and nose, natural daylight, realistic photograph
40yo Indian man, curled moustache::portrait of a 40-year-old Indian man, dark wavy hair, distinctive curled moustache, natural daylight, realistic photograph
50yo Brazilian woman, turquoise pendant::portrait of a 50-year-old Brazilian woman, dark curly hair, wearing a single turquoise pendant necklace, natural daylight, realistic photograph
70yo Japanese man, silver hair and smile lines::portrait of a 70-year-old Japanese man, short silver hair, distinctive deep smile lines around his eyes, natural daylight, realistic photograph

+BODY
Open right hand, palm facing camera::extreme close-up photograph of a woman's open right hand, palm facing camera, detailed skin texture, fingers fully visible, neutral studio lighting
Left ear, dark hair tucked behind::extreme close-up photograph of a woman's left ear, detailed natural skin texture, dark brown hair tucked behind the ear, neutral studio lighting
Green eye, iris and eyelashes in close-up::extreme close-up photograph of a woman's green eye, detailed iris, eyelashes and natural skin texture, neutral studio lighting
Bare right foot with all toes visible::extreme close-up photograph of a woman's bare right foot, toes fully visible, detailed natural skin texture, neutral studio lighting
Relaxed closed mouth, natural lips::extreme close-up photograph of a woman's relaxed closed mouth, natural lips and surrounding skin texture, neutral studio lighting
Nose in side profile, natural skin texture::extreme close-up photograph of a woman's nose viewed from the side in profile, detailed natural skin texture, neutral studio lighting

+EXPRESSIONS
Neutral expression, looking at camera::portrait of a 32-year-old Mediterranean woman with olive skin, green almond-shaped eyes, an oval face, straight nose, defined cheekbones, medium-full lips, shoulder-length dark brown wavy hair parted slightly to the left, slim athletic build, wearing a plain fitted gray crew-neck T-shirt, neutral relaxed expression, looking directly at camera, plain light-gray background, realistic photograph
Broad smile, visible teeth and raised cheeks::portrait of a 32-year-old Mediterranean woman with olive skin, green almond-shaped eyes, an oval face, straight nose, defined cheekbones, medium-full lips, shoulder-length dark brown wavy hair parted slightly to the left, slim athletic build, wearing a plain fitted gray crew-neck T-shirt, broad genuine smile with visible teeth, raised cheeks and slightly narrowed happy eyes, looking directly at camera, plain light-gray background, realistic photograph
Sad expression, downturned mouth and watery eyes::portrait of a 32-year-old Mediterranean woman with olive skin, green almond-shaped eyes, an oval face, straight nose, defined cheekbones, medium-full lips, shoulder-length dark brown wavy hair parted slightly to the left, slim athletic build, wearing a plain fitted gray crew-neck T-shirt, sad expression with lowered eyebrows, slightly downturned mouth and watery eyes, looking directly at camera, plain light-gray background, realistic photograph
Angry expression, furrowed brows and tense jaw::portrait of a 32-year-old Mediterranean woman with olive skin, green almond-shaped eyes, an oval face, straight nose, defined cheekbones, medium-full lips, shoulder-length dark brown wavy hair parted slightly to the left, slim athletic build, wearing a plain fitted gray crew-neck T-shirt, angry expression with deeply furrowed brows, narrowed eyes and tense jaw, looking directly at camera, plain light-gray background, realistic photograph
Frightened expression, wide eyes and open mouth::portrait of a 32-year-old Mediterranean woman with olive skin, green almond-shaped eyes, an oval face, straight nose, defined cheekbones, medium-full lips, shoulder-length dark brown wavy hair parted slightly to the left, slim athletic build, wearing a plain fitted gray crew-neck T-shirt, frightened expression with raised eyebrows, wide eyes and tense slightly open mouth, looking directly at camera, plain light-gray background, realistic photograph
Excited expression, wide eyes and open smile::portrait of a 32-year-old Mediterranean woman with olive skin, green almond-shaped eyes, an oval face, straight nose, defined cheekbones, medium-full lips, shoulder-length dark brown wavy hair parted slightly to the left, slim athletic build, wearing a plain fitted gray crew-neck T-shirt, intensely excited expression with raised eyebrows, wide sparkling eyes and a large open smile, looking directly at camera, plain light-gray background, realistic photograph

+POSES
Standing upright, arms relaxed at sides::full-body photograph of a 32-year-old Mediterranean woman with olive skin, green almond-shaped eyes, an oval face, shoulder-length dark brown wavy hair parted slightly to the left, 170 cm tall, slim athletic build with moderately broad shoulders, narrow waist and long legs, wearing a fitted gray crew-neck T-shirt, straight dark blue jeans and plain white sneakers, standing upright with feet shoulder-width apart and both arms relaxed at her sides, neutral expression, plain studio background, realistic photograph
Arms crossed firmly over the chest::full-body photograph of a 32-year-old Mediterranean woman with olive skin, green almond-shaped eyes, an oval face, shoulder-length dark brown wavy hair parted slightly to the left, 170 cm tall, slim athletic build with moderately broad shoulders, narrow waist and long legs, wearing a fitted gray crew-neck T-shirt, straight dark blue jeans and plain white sneakers, standing upright with both arms crossed firmly over her chest, neutral expression, plain studio background, realistic photograph
Hands on hips, elbows pointing outward::full-body photograph of a 32-year-old Mediterranean woman with olive skin, green almond-shaped eyes, an oval face, shoulder-length dark brown wavy hair parted slightly to the left, 170 cm tall, slim athletic build with moderately broad shoulders, narrow waist and long legs, wearing a fitted gray crew-neck T-shirt, straight dark blue jeans and plain white sneakers, standing upright with both hands resting on her hips and elbows pointing outward, neutral expression, plain studio background, realistic photograph
Low crouch, feet flat and hands on thighs::full-body photograph of a 32-year-old Mediterranean woman with olive skin, green almond-shaped eyes, an oval face, shoulder-length dark brown wavy hair parted slightly to the left, 170 cm tall, slim athletic build with moderately broad shoulders, narrow waist and long legs, wearing a fitted gray crew-neck T-shirt, straight dark blue jeans and plain white sneakers, crouching low with both feet flat on the ground, knees bent and hands resting lightly on her thighs, neutral expression, plain studio background, realistic photograph
Walking toward camera, left foot forward::full-body photograph of a 32-year-old Mediterranean woman with olive skin, green almond-shaped eyes, an oval face, shoulder-length dark brown wavy hair parted slightly to the left, 170 cm tall, slim athletic build with moderately broad shoulders, narrow waist and long legs, wearing a fitted gray crew-neck T-shirt, straight dark blue jeans and plain white sneakers, walking naturally toward the camera with her left foot forward and opposite arm swinging naturally, neutral expression, plain studio background, realistic photograph
Reaching overhead with the right arm::full-body photograph of a 32-year-old Mediterranean woman with olive skin, green almond-shaped eyes, an oval face, shoulder-length dark brown wavy hair parted slightly to the left, 170 cm tall, slim athletic build with moderately broad shoulders, narrow waist and long legs, wearing a fitted gray crew-neck T-shirt, straight dark blue jeans and plain white sneakers, standing while reaching high above her head with her right arm fully extended and her left arm relaxed beside her body, neutral expression, plain studio background, realistic photograph

+FRAMING
Front view at eye level, full body::full-body photograph of a 32-year-old Mediterranean woman with olive skin, green almond-shaped eyes, an oval face, shoulder-length dark brown wavy hair parted slightly to the left, 170 cm tall, slim athletic build, wearing a fitted gray crew-neck T-shirt, straight dark blue jeans and plain white sneakers, standing upright with arms relaxed at her sides, viewed directly from the front at eye level, symmetrical camera position, plain studio background, realistic photograph
Rear view at eye level, full body::full-body photograph of a 32-year-old Mediterranean woman with olive skin, shoulder-length dark brown wavy hair parted slightly to the left, 170 cm tall, slim athletic build, wearing a fitted gray crew-neck T-shirt, straight dark blue jeans and plain white sneakers, standing upright with arms relaxed at her sides, viewed directly from behind at eye level, back of head and body fully visible, plain studio background, realistic photograph
High camera angle, steep downward view::full-body photograph of a 32-year-old Mediterranean woman with olive skin, green almond-shaped eyes, an oval face, shoulder-length dark brown wavy hair parted slightly to the left, 170 cm tall, slim athletic build, wearing a fitted gray crew-neck T-shirt, straight dark blue jeans and plain white sneakers, standing upright with arms relaxed at her sides, camera positioned high above her looking steeply downward, strong top-down perspective, entire body visible, plain studio floor, realistic photograph
Low camera angle, looking steeply upward::full-body photograph of a 32-year-old Mediterranean woman with olive skin, green almond-shaped eyes, an oval face, shoulder-length dark brown wavy hair parted slightly to the left, 170 cm tall, slim athletic build, wearing a fitted gray crew-neck T-shirt, straight dark blue jeans and plain white sneakers, standing upright with arms relaxed at her sides, camera positioned very low near floor level looking steeply upward, entire body visible, strong low-angle perspective, plain studio background, realistic photograph
Strict left profile, body and face at 90°::full-body photograph of a 32-year-old Mediterranean woman with olive skin, green almond-shaped eyes, an oval face, straight nose, shoulder-length dark brown wavy hair parted slightly to the left, 170 cm tall, slim athletic build, wearing a fitted gray crew-neck T-shirt, straight dark blue jeans and plain white sneakers, standing upright with arms relaxed at her sides, strict left-side profile with her body and face turned exactly 90 degrees from the camera, eye-level camera, plain studio background, realistic photograph
Three-quarter left view, body and face at 45°::full-body photograph of a 32-year-old Mediterranean woman with olive skin, green almond-shaped eyes, an oval face, straight nose, defined cheekbones, shoulder-length dark brown wavy hair parted slightly to the left, 170 cm tall, slim athletic build, wearing a fitted gray crew-neck T-shirt, straight dark blue jeans and plain white sneakers, standing upright with arms relaxed at her sides, body and face rotated approximately 45 degrees toward the camera in a three-quarter left view, eye-level camera, plain studio background, realistic photograph

+LOCATIONS
Rainy European city intersection in the evening::busy modern European city intersection on a rainy evening, pedestrians, cars, storefronts and wet pavement reflections, realistic photograph
Urban park, spring sunshine and winding paths::large urban park on a sunny spring afternoon, green lawn, mature trees, benches and winding paths, realistic photograph
Modern apartment living room in daylight::comfortable modern apartment living room, sofa, bookshelves, large windows and natural daylight, realistic interior photograph
Ancient forest, moss and shafts of sunlight::dense ancient forest with moss-covered trees, ferns and shafts of sunlight passing through the canopy, realistic landscape photograph
Sandy beach, clear blue water and small waves::wide sandy beach beside clear blue ocean water, small waves, scattered rocks and bright daylight, realistic landscape photograph
Snowy peaks above an alpine river valley::high alpine valley surrounded by steep snow-capped mountains, small river crossing the valley, clear morning light, realistic landscape photograph

+PROPS
Analog clock showing exactly 3:15 PM::analog wall clock clearly showing exactly 3:15 PM, hour hand slightly past 3 and minute hand pointing at 3, centered and viewed straight on against a neutral white background, realistic photograph
Medieval longsword, steel blade and leather grip::single medieval longsword lying horizontally on a plain white surface against a neutral white background, straight steel blade, leather-wrapped grip and simple crossguard, realistic photograph
Red sports car, three-quarter front view::red modern sports car parked on a plain white studio floor against a neutral white background, full vehicle visible from a three-quarter front angle, realistic photograph
Wooden recurve bow with taut string and arrow::single wooden recurve bow with a taut string and one arrow resting beside it, lying on a plain white surface against a neutral white background, realistic photograph
Blue wooden chair, entire chair visible::single blue wooden chair standing upright on a plain white surface against a neutral white background, entire chair visible, realistic photograph
White cup of black coffee, visible steam::white ceramic coffee cup filled with hot black coffee on a plain white surface against a neutral white background, clearly visible steam rising from the cup, realistic photograph

+STYLES
Studio photograph, blue coat on white::full-body image of a 32-year-old Mediterranean woman with olive skin, green almond-shaped eyes, an oval face, straight nose, defined cheekbones, medium-full lips, shoulder-length dark brown wavy hair parted slightly to the left, 170 cm tall, slim athletic build with moderately broad shoulders, narrow waist and long legs, wearing a fitted cobalt-blue knee-length coat over a black shirt, dark straight-leg trousers and black ankle boots, standing neutrally with arms relaxed at her sides, isolated against a neutral white background, photorealistic professional studio photograph, realistic skin texture, natural lighting
Cinematic movie still, blue coat on white::full-body image of a 32-year-old Mediterranean woman with olive skin, green almond-shaped eyes, an oval face, straight nose, defined cheekbones, medium-full lips, shoulder-length dark brown wavy hair parted slightly to the left, 170 cm tall, slim athletic build with moderately broad shoulders, narrow waist and long legs, wearing a fitted cobalt-blue knee-length coat over a black shirt, dark straight-leg trousers and black ankle boots, standing neutrally with arms relaxed at her sides, isolated against a neutral white background, cinematic live-action movie still, anamorphic lens, shallow depth of field, cinematic color grading, dramatic practical lighting
Realistic 3D render, blue coat on white::full-body image of a 32-year-old Mediterranean woman with olive skin, green almond-shaped eyes, an oval face, straight nose, defined cheekbones, medium-full lips, shoulder-length dark brown wavy hair parted slightly to the left, 170 cm tall, slim athletic build with moderately broad shoulders, narrow waist and long legs, wearing a fitted cobalt-blue knee-length coat over a black shirt, dark straight-leg trousers and black ankle boots, standing neutrally with arms relaxed at her sides, isolated against a neutral white background, high-end realistic 3D character render, physically based materials, realistic subsurface skin scattering, global illumination
Editorial illustration, blue coat on white::full-body image of a 32-year-old Mediterranean woman with olive skin, green almond-shaped eyes, an oval face, straight nose, defined cheekbones, medium-full lips, shoulder-length dark brown wavy hair parted slightly to the left, 170 cm tall, slim athletic build with moderately broad shoulders, narrow waist and long legs, wearing a fitted cobalt-blue knee-length coat over a black shirt, dark straight-leg trousers and black ankle boots, standing neutrally with arms relaxed at her sides, isolated against a neutral white background, detailed contemporary editorial illustration, clean shapes, confident linework and controlled shading
Oil painting, visible brushwork, blue coat on white::full-body image of a 32-year-old Mediterranean woman with olive skin, green almond-shaped eyes, an oval face, straight nose, defined cheekbones, medium-full lips, shoulder-length dark brown wavy hair parted slightly to the left, 170 cm tall, slim athletic build with moderately broad shoulders, narrow waist and long legs, wearing a fitted cobalt-blue knee-length coat over a black shirt, dark straight-leg trousers and black ankle boots, standing neutrally with arms relaxed at her sides, isolated against a neutral white background, traditional oil painting on canvas, visible layered brush strokes, rich pigments and naturalistic anatomy
Japanese anime, cel shading, blue coat on white::full-body image of a 32-year-old Mediterranean woman with olive skin, green almond-shaped eyes, an oval face, straight nose, defined cheekbones, medium-full lips, shoulder-length dark brown wavy hair parted slightly to the left, 170 cm tall, slim athletic build with moderately broad shoulders, narrow waist and long legs, wearing a fitted cobalt-blue knee-length coat over a black shirt, dark straight-leg trousers and black ankle boots, standing neutrally with arms relaxed at her sides, isolated against a neutral white background, polished Japanese anime illustration, clean precise linework, cel shading and detailed character design

+TEXT
Chat bubble: "Hello, my name is Bob"::a clean chat interface showing one large white speech bubble on a simple pale background, the bubble contains exactly "Hello, my name is Bob" in crisp black sentence-case lettering, generous padding around the words, entire bubble and complete message fully visible, no other text
Diner neon: "Sal's" / "Open 24 Hours"::photorealistic interior of a classic American diner at night, chrome counter and red vinyl booths, a large neon sign above the counter displays exactly "Sal's" on the upper line and "Open 24 Hours" on the lower line, warm red and blue neon light reflected on the chrome, both lines fully visible and clearly legible, no other readable text
Street signs: "Maple Street" / "6th Avenue North"::photorealistic street corner at an intersection, two perpendicular green street-name signs mounted on one pole, one sign reads exactly "Maple Street" and the other reads exactly "6th Avenue North", crisp white lettering matching that capitalization, camera positioned at a three-quarter angle so the front faces of both signs are clearly visible, both complete signs in frame, natural daylight, city buildings in the background
Poster: "The Darkness"; "IN CINEMAS SOON"; "DAVE PRATT", "ZOE DIESEL"::professionally designed cinematic horror movie poster viewed straight on, dark atmospheric city imagery, clear typography with three distinct levels: exactly "IN CINEMAS SOON" across the top, the large prominent title "The Darkness" centered in the middle, and the actor names "DAVE PRATT" and "ZOE DIESEL" directly below the title, both actor names equally prominent, generous spacing, all lettering fully visible and easy to read, no additional text
"THE MORNING CHRONICLE", detailed front-page text::photorealistic overhead photograph of a complete broadsheet newspaper front page lying flat on a wooden table, page aligned square to the camera with all four edges visible, off-white paper, crisp black ink, dense professional multi-column editorial layout, large serif masthead reading exactly "THE MORNING CHRONICLE", immediately beneath it the dateline "FRIDAY, OCTOBER 23, 2026 — BERLIN — €3.20", dominant headline "A CITY AWAKES TO A NEW ERA", directly below it the subheadline "After years of planning, a landmark public project opens its doors as thousands gather across the capital.", large news photograph of crowds entering a modern civic building at sunrise, beneath the photograph the caption "Crowds gathered shortly after sunrise on Friday as the new civic complex opened to the public for the first time.", three clearly separated secondary stories headed "MARKETS RALLY AFTER WEEK OF UNCERTAINTY", "SCIENCE TEAM REPORTS MAJOR ENERGY BREAKTHROUGH", and "AUTUMN FESTIVAL TRANSFORMS CITY STREETS", bottom teaser strip reading "SPORT — PAGE 18", "BUSINESS — PAGE 22", "CULTURE — PAGE 27", and "WEATHER — PAGE 31", small barcode and printed price of €3.20 near the lower edge, authentic major-city newspaper typography, realistic ink and paper texture, subtle shadows, all specified text reproduced exactly as quoted, correctly spelled and fully legible, no gibberish or placeholder text
Raccoon holding a sign reading "NOT A DOG"::photorealistic raccoon standing upright on its hind legs on a busy city street, holding a rectangular white cardboard sign with both front paws, the sign reads exactly "NOT A DOG" in large bold black uppercase letters, sign facing directly toward the camera, entire raccoon and complete sign fully visible, detailed realistic fur, daylight, cars and pedestrians visible in the softly focused background

+COMPLEX
Two people, distinct outfits and left/right positions::full-body studio photograph of exactly two people standing side by side: on the left a tall dark-skinned Nigerian woman with short tightly curled black hair wearing a bright yellow cropped jacket, green high-waisted trousers and white sneakers; on the right a shorter pale-skinned Korean man with straight black hair wearing a purple crew-neck sweater, blue jeans and red sneakers; both facing the camera, hands visible, neither person touching the other, plain light-gray studio background
4 mugs, body/handle: red/white, blue/yellow, green/black, yellow/blue::exactly four ceramic mugs arranged in a straight horizontal row on a white table: a red mug with a white handle, a blue mug with a yellow handle, a green mug with a black handle, and a yellow mug with a blue handle, all mugs clearly separated and fully visible
Red cube on blue sphere; yellow pyramid right; green cylinder between::a small red cube resting directly on top of a large blue sphere, the blue sphere positioned to the left of a tall yellow pyramid, a small green cylinder standing exactly between the sphere and pyramid, clean studio background
7 objects: 3 red apples, 2 green pears, yellow banana, blue cup::exactly seven objects on a wooden table: three red apples, two green pears, one yellow banana and one blue ceramic cup, every object clearly separated and fully visible
Left hand with red pencil; right hand thumbs-up::close-up photograph of two human hands performing different actions: the left hand holding a red pencil between thumb and index finger while the right hand gives a thumbs-up gesture, both hands fully visible with five anatomically correct fingers each
Mirror reflection: green book in left hand, opposite visual side::a 32-year-old Mediterranean woman with olive skin, shoulder-length dark brown wavy hair, slim athletic build, wearing a red jacket, blue jeans and black ankle boots, standing in front of a large vertical mirror, camera positioned behind her so both her back and her frontal reflection are visible, holding a green book in her left hand while the mirror reflection correctly shows the book on the visually opposite side"""

SEED_MODES = ("fixed", "increment", "decrement", "randomize")
SEED_MAX = 2**64 - 1


@dataclass(frozen=True)
class Entry:
    caption: str
    positive: str
    negative: str
    line: int


@dataclass(frozen=True)
class Category:
    name: str
    entries: tuple
    line: int


@dataclass(frozen=True)
class Benchmark:
    title: str | None
    categories: tuple
    config: str


@dataclass(frozen=True)
class GenerationItem:
    index: int
    category_index: int
    category: str
    column: int
    entry: Entry
    seed: int


def config_error(line, content, message, expected=None):
    detail = f"Ray Model Card config error, line {line}:\n{message}"
    if content:
        detail += f"\nContent: {content[:200]}"
    if expected:
        detail += f"\nExpected: {expected}"
    return ValueError(detail)


def _tokens(text, line, content):
    """Decode escapes once, retaining which delimiter characters were escaped."""
    result, i = [], 0
    while i < len(text):
        if text[i] != "\\":
            result.append((text[i], False))
            i += 1
            continue
        if text.startswith("\\::", i):
            result.extend(((":", True), (":", True)))
            i += 3
        elif i + 1 < len(text) and text[i + 1] in "|+=\\":
            result.append((text[i + 1], True))
            i += 2
        else:
            raise config_error(line, content, "Malformed escaped delimiter.", r"\|, \::, \+, \= or \\")
    return result


def _split(tokens, delimiter):
    for i in range(len(tokens) - len(delimiter) + 1):
        if all(tokens[i + j] == (char, False) for j, char in enumerate(delimiter)):
            return tokens[:i], tokens[i + len(delimiter):]
    return tokens, None


def _text(tokens):
    return "".join(char for char, _ in tokens).strip()


def parse_config(config):
    if not isinstance(config, str):
        raise ValueError("Ray Model Card config must be text.")
    if len(config) > 2_000_000:
        raise ValueError("Ray Model Card config exceeds 2 million characters.")
    title, categories, entries, category_name, category_line = None, [], [], None, 0

    def finish():
        if category_name is not None:
            if not entries:
                raise config_error(category_line, "+" + category_name, "Category contains no prompts.")
            categories.append(Category(category_name, tuple(entries), category_line))

    for line, raw in enumerate(config.splitlines(), 1):
        text = raw.strip()
        if not text:
            continue
        if len(text) > 32_768:
            raise config_error(line, text, "Line exceeds 32768 characters.")
        if text.startswith("="):
            if title is not None:
                raise config_error(line, text, "Duplicate title declaration; use one =title line.")
            title = _text(_tokens(text[1:], line, raw))
            if not title:
                raise config_error(line, text, "Title is empty.", "=MODEL NAME")
        elif text.startswith("+"):
            finish()
            category_name = _text(_tokens(text[1:], line, raw))
            category_line, entries = line, []
            if not category_name:
                raise config_error(line, text, "Category name is empty.", "+CATEGORY NAME")
        else:
            if category_name is None:
                raise config_error(line, text, "Prompt found before any category declaration.", "+CATEGORY NAME")
            # Negative belongs to the prompt, so a :: in a negative is literal.
            positive_part, negative = _split(_tokens(text, line, raw), "|")
            caption, positive = _split(positive_part, "::")
            if positive is None:
                positive, caption = caption, None
            positive = _text(positive)
            if not positive:
                raise config_error(line, text, "Positive prompt is empty.", "caption::positive prompt|negative prompt")
            caption = positive if caption is None else _text(caption)
            if not caption:
                raise config_error(line, text, "Caption is empty; omit :: to use the positive prompt.")
            entries.append(Entry(caption, positive, "" if negative is None else _text(negative), line))
    finish()
    if not categories:
        raise config_error(1, "", "At least one category with a prompt is required.", "+CATEGORY NAME\npositive prompt")
    return Benchmark(title, tuple(categories), config)


def make_plan(benchmark, seed, mode):
    if mode not in SEED_MODES:
        raise ValueError("Ray Model Card seed mode must be fixed, increment, decrement or randomize.")
    if not isinstance(seed, int) or not 0 <= seed <= SEED_MAX:
        raise ValueError("Ray Model Card seed must be an unsigned 64-bit integer.")
    items = []
    cursor = seed
    for row, category in enumerate(benchmark.categories):
        for column, entry in enumerate(category.entries):
            if mode == "increment":
                cursor = (cursor + 1) & SEED_MAX
            elif mode == "decrement":
                cursor = (cursor - 1) & SEED_MAX
            elif mode == "randomize":
                cursor = secrets.randbits(64)
            items.append(GenerationItem(len(items), row, category.name, column, entry, cursor))
    return tuple(items)


def display_name(value):
    if not isinstance(value, str):
        return ""
    return " ".join("".join(c for c in unicodedata.normalize("NFC", value)
                            if unicodedata.category(c) not in ("Cc", "Cf")).split())[:512]


def resolve_title(benchmark, selected):
    # Model loader paths are not useful as headings; keep the model/version stem.
    selected = display_name(selected)
    if selected:
        selected = selected.replace("\\", "/").rsplit("/", 1)[-1]
        selected = re.sub(r"\.(safetensors|ckpt|pt|pth|bin|gguf)$", "", selected, flags=re.I)
    return display_name(benchmark.title) or selected or "MODEL CARD", selected


@dataclass(frozen=True)
class Layout:
    columns: int
    card_width: int
    card_height: int
    margin: int
    gap: int
    thumbnail_width: int
    thumbnail_height: int
    caption_height: int
    caption_font: int
    header_font: int
    category_header_height: int
    title_font: int
    title_block_height: int
    category_block_height: int
    category_gap: int
    xs: tuple

    def row_y(self, row):
        return self.margin + self.title_block_height + row * (self.category_block_height + self.category_gap)


def calculate_layout(benchmark, card_width, image_width, image_height):
    if not isinstance(card_width, int) or not 256 <= card_width <= 32768:
        raise ValueError("Ray Model Card width must be between 256 and 32768 pixels.")
    if any(not isinstance(n, int) or not 64 <= n <= 16384 for n in (image_width, image_height)):
        raise ValueError("Ray Model Card image dimensions must be between 64 and 16384 pixels.")
    columns = max(len(category.entries) for category in benchmark.categories)
    margin, gap = max(8, round(card_width * .008)), max(1, round(card_width * .001))
    usable = card_width - 2 * margin - (columns - 1) * gap
    width = usable // columns
    if width < 32:
        raise ValueError(f"Ray Model Card: {columns} columns leave thumbnails narrower than 32px. Increase card width or reduce the largest category.")
    height = max(1, round(width * image_height / image_width))
    caption_font = max(9, round(width * .035))
    caption_height = 2 * (caption_font + max(2, caption_font // 5)) + gap * 2
    header_font = max(14, round(card_width * .013))
    header_height = header_font + max(8, round(header_font * .4))
    title_font = max(28, round(card_width * .045))
    title_block = title_font + max(14, round(card_width * .014)) + round(card_width * .026)
    block = header_height + height + caption_height
    category_gap = max(8, round(card_width * .006))
    rows = len(benchmark.categories)
    card_height = margin * 2 + title_block + rows * block + (rows - 1) * category_gap
    if card_height > 65535 or card_width * card_height > 100_000_000:
        raise ValueError(f"Ray Model Card would be {card_width}×{card_height}; limit is 100 megapixels and 65535px per side. Reduce card width or benchmark size.")
    # Distribute leftover pixels between columns using absolute integer positions.
    spare = usable - width * columns
    xs = tuple(margin + i * (width + gap) + (i * spare // max(1, columns - 1)) for i in range(columns))
    return Layout(columns, card_width, card_height, margin, gap, width, height, caption_height,
                  caption_font, header_font, header_height, title_font, title_block, block, category_gap, xs)


def check_memory(plan, layout, width, height, preview_width, max_images, memory_limit_mb):
    if not isinstance(preview_width, int) or not 64 <= preview_width <= 32768:
        raise ValueError("Ray Model Card preview width must be between 64 and 32768 pixels.")
    if not isinstance(max_images, int) or not 1 <= max_images <= 4096:
        raise ValueError("Ray Model Card maximum image count must be between 1 and 4096.")
    if not isinstance(memory_limit_mb, int) or not 256 <= memory_limit_mb <= 65536:
        raise ValueError("Ray Model Card output memory budget must be between 256 and 65536 MiB.")
    if len(plan) > max_images:
        raise ValueError(f"Ray Model Card requests {len(plan)} images; Settings permits {max_images}. Increase the limit deliberately for a larger benchmark.")
    pixels = layout.card_width * layout.card_height
    preview_pixels = pixels * min(1, preview_width / layout.card_width) ** 2
    # Float outputs + PIL/array conversion buffers + thumbnails + one decoded image.
    estimate = len(plan) * width * height * 4 * 4 + pixels * 18 + preview_pixels * 18
    estimate += len(plan) * layout.thumbnail_width * layout.thumbnail_height * 3 + width * height * 24
    if estimate > memory_limit_mb * 1024**2:
        raise ValueError(f"Ray Model Card needs about {math.ceil(estimate / 1024**2)} MiB for retained images/card buffers; Settings budget is {memory_limit_mb} MiB. Reduce dimensions/count or raise the budget. Model/VRAM memory is additional.")
    return estimate


def load_font(size, bold=False, title=False):
    windows = os.path.join(os.environ.get("WINDIR", "C:/Windows"), "Fonts")
    names = (["Impact.ttf", "DejaVuSansCondensed-Bold.ttf"] if title else
             ["DejaVuSansCondensed-Bold.ttf", "arialbd.ttf"] if bold else ["DejaVuSans.ttf", "arial.ttf"])
    for name in names:
        for path in (name, os.path.join(windows, name), "/usr/share/fonts/truetype/dejavu/" + name,
                     "/System/Library/Fonts/Supplemental/" + name):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                pass
    return ImageFont.load_default(size=size)


def fit_text(text, font, width):
    text = display_name(text)
    if font.getlength(text) <= width:
        return text
    while text and font.getlength(text + "…") > width:
        text = text[:-1]
    return text + "…" if text else ""


def caption_lines(text, font, width):
    text = display_name(text)
    if font.getlength(text) <= width:
        return [text]
    split = 0
    while split < len(text) and font.getlength(text[:split + 1]) <= width:
        split += 1
    last_space = text.rfind(" ", 0, split + 1)
    if last_space > 0:
        split = last_space
    split = max(1, split)
    return [text[:split].strip(), fit_text(text[split:].strip(), font, width)]


def compose_card(benchmark, plan, thumbnails, layout, title, timestamp, interrupt=lambda: None):
    card = Image.new("RGB", (layout.card_width, layout.card_height), "black")
    try:
        draw = ImageDraw.Draw(card)
        available = layout.card_width - 2 * layout.margin
        size = layout.title_font
        font = load_font(size, title=True)
        while size > 16 and font.getlength(title) > available:
            size -= 1
            font = load_font(size, title=True)
        draw.text((layout.margin, layout.margin), fit_text(title, font, available), font=font, fill="white", anchor="lt")
        date_font = load_font(max(12, round(layout.card_width * .014)))
        draw.text((layout.margin, layout.margin + layout.title_font + layout.gap * 3), timestamp,
                  font=date_font, fill="#cccccc", anchor="lt")
        header = load_font(layout.header_font, bold=True, title=True)
        caption = load_font(layout.caption_font)
        for row, category in enumerate(benchmark.categories):
            interrupt()
            draw.text((layout.margin, layout.row_y(row)), fit_text(category.name, header, available),
                      font=header, fill="white", anchor="lt")
        for item, thumbnail in zip(plan, thumbnails):
            interrupt()
            x, y = layout.xs[item.column], layout.row_y(item.category_index) + layout.category_header_height
            card.paste(thumbnail, (x, y))
            for line, text in enumerate(caption_lines(item.entry.caption, caption, layout.thumbnail_width)):
                draw.text((x, y + layout.thumbnail_height + layout.gap + line * (layout.caption_font + max(2, layout.caption_font // 5))),
                          text, font=caption, fill="#cccccc", anchor="lt")
        return card
    except BaseException:
        card.close()
        raise


def fenced(text, language="text"):
    longest = max((len(run) for run in re.findall(r"`+", text)), default=0)
    fence = "`" * max(3, longest + 1)
    return f"{fence}{language}\n{text}" + ("" if text.endswith("\n") else "\n") + fence


def make_report(benchmark, plan, title, selected, timestamp, settings, layout, runtime_seconds=None):
    lines = ["# Ray Model Card", "", "## Model", "", fenced(title), "", f"- Datetime: {timestamp}"]
    if runtime_seconds is not None:
        duration = round(runtime_seconds, 2)
        hours, remainder = divmod(duration, 3600)
        minutes, seconds = divmod(remainder, 60)
        lines.append(f"- Runtime: {int(hours):02d}:{int(minutes):02d}:{seconds:05.2f} ({duration:.2f} seconds)")
    if selected and selected != title:
        lines += ["- Selected model name:", "", fenced(selected)]
    lines += ["", "## Generation settings", ""]
    lines += [f"- {key.replace('_', ' ').capitalize()}: {value}" for key, value in settings.items()]
    lines += [f"- Card height: {layout.card_height}", f"- Columns: {layout.columns}",
              f"- Image count: {len(plan)}", "- Captions: two lines maximum; overflow ends with an ellipsis.",
              "- Seed mode advances before each image; fixed repeats the initial seed. Values wrap at 64 bits.",
              "- Upstream MODEL patches are used as supplied (including shift/renorm).", "", "## Configuration", "",
              fenced(benchmark.config), "", "## Results", ""]
    for item in plan:
        lines += [f"### {item.index + 1}. Result", "", f"- Index: {item.index}",
                  f"- Card position: row/category {item.category_index + 1}, column {item.column + 1}",
                  f"- Config line: {item.entry.line}", f"- Seed: {item.seed}", "", "Category:", "", fenced(item.category),
                  "", "Caption:", "", fenced(item.entry.caption), "", "Positive:", "", fenced(item.entry.positive),
                  "", "Negative:", "", fenced(item.entry.negative), ""]
    return "\n".join(lines)
