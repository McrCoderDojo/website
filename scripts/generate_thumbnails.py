from pathlib import Path

import yaml
from PIL import Image

CONTENT_DIR = Path(__file__).parent.parent / 'content'
THUMB_SIZE = 150


def thumb_path(image_path: Path) -> Path:
    return image_path.with_stem(image_path.stem + '_thumb')


def make_thumbnail(src: Path, dest: Path):
    with Image.open(src) as img:
        img = img.convert('RGB')
        ratio = THUMB_SIZE / min(img.width, img.height)
        new_size = (round(img.width * ratio), round(img.height * ratio))
        img = img.resize(new_size, Image.LANCZOS)
        left = (img.width - THUMB_SIZE) // 2
        top = (img.height - THUMB_SIZE) // 2
        img = img.crop((left, top, left + THUMB_SIZE, top + THUMB_SIZE))
        img.save(dest, quality=85)


def process_meta(meta_file: Path):
    with open(meta_file) as f:
        meta = yaml.safe_load(f)

    if not meta or 'cover_image' not in meta:
        return

    if 'thumbnail' in meta:
        return

    cover_rel = meta['cover_image']
    cover_abs = meta_file.parent / cover_rel

    if not cover_abs.exists():
        print(f'  MISSING: {cover_abs}')
        return

    dest_abs = thumb_path(cover_abs)
    dest_rel = str(thumb_path(Path(cover_rel)))

    print(f'  {cover_abs.name} -> {dest_abs.name}')
    make_thumbnail(cover_abs, dest_abs)

    meta['thumbnail'] = dest_rel
    with open(meta_file, 'w') as f:
        yaml.dump(meta, f, allow_unicode=True, sort_keys=True)


def main():
    for section in ('posts', 'pages'):
        for meta_file in sorted((CONTENT_DIR / section).glob('*/meta.yml')):
            print(meta_file.parent.name)
            process_meta(meta_file)


if __name__ == '__main__':
    main()
