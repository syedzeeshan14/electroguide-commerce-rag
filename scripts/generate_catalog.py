"""Reproducible fictional electronics catalog; no retailer data or API needed."""
import argparse
import csv
import hashlib
import json
import random
from pathlib import Path

CATEGORIES = {
    'tv': ('TV', 249, 3499, ['4K', '8K'], [43, 50, 55, 65, 75, 85]),
    'mobile': ('Mobile phone', 149, 1399, ['Android demo OS'], [128, 256, 512]),
    'laptop': ('Laptop', 349, 2499, ['Windows demo OS', 'Linux'], [256, 512, 1024, 2048]),
    'tablet': ('Tablet', 129, 1199, ['Android demo OS'], [64, 128, 256, 512]),
    'smartwatch': ('Smartwatch', 49, 599, ['Bluetooth', 'Bluetooth + GPS'], [40, 42, 44, 46]),
    'headphones': ('Headphones', 29, 499, ['over-ear', 'in-ear'], [20, 30, 40, 50]),
    'camera': ('Camera', 299, 2999, ['mirrorless', 'compact'], [20, 24, 32, 45]),
    'monitor': ('Monitor', 99, 1499, ['1080p', '1440p', '4K'], [24, 27, 32, 34]),
    'speaker': ('Speaker', 29, 799, ['portable', 'home'], [10, 20, 40, 80]),
    'gaming': ('Gaming console', 199, 799, ['home console', 'handheld'], [256, 512, 1024]),
}
BRANDS = ['AsterDemo', 'NovalumeDemo', 'CircuitBayDemo', 'VoltoraDemo', 'PinnacleDemo']

def generate(count=50000, seed=42):
    if count < 1:
        raise ValueError('count must be positive')
    rng = random.Random(seed)
    categories = list(CATEGORIES)
    for i in range(count):
        category = categories[i % len(categories)]
        label, low, high, types, sizes = CATEGORIES[category]
        variant = i // len(categories) + 1
        brand, kind, size = rng.choice(BRANDS), rng.choice(types), rng.choice(sizes)
        specs = {'color': rng.choice(['black', 'silver', 'blue', 'white'])}
        if category in ('mobile', 'laptop', 'tablet', 'gaming'):
            specs.update(storage_gb=size, ram_gb=rng.choice([8, 16, 32]) if category == 'laptop' else rng.choice([4, 8, 12]), platform=kind)
        elif category in ('tv', 'monitor'):
            specs.update(screen_inches=size, resolution=kind, refresh_hz=rng.choice([60, 120]))
        elif category == 'smartwatch':
            specs.update(case_mm=size, connectivity=kind, battery_hours=rng.choice([24, 48, 72]))
        elif category == 'headphones':
            specs.update(form_factor=kind, battery_hours=size, noise_cancelling=rng.choice([True, False]))
        elif category == 'camera':
            specs.update(camera_type=kind, megapixels=size)
        else:
            specs.update(speaker_type=kind, power_watts=size)
        price = round(rng.uniform(low, high), 2)
        yield {
            'id': f'EG-{i+1:06d}', 'sku': f'DEMO-{category.upper()}-{variant:05d}',
            'name': f'{brand} {label} Series {variant:05d}', 'brand': brand,
            'category': category, 'price': price, 'currency': 'USD',
            'stock': rng.choice([0, 5, 10, 25, 50, 100]),
            'description': f'Fictional {label.lower()} for academic testing. ' + '; '.join(f'{k}: {v}' for k,v in specs.items()),
            'specifications': specs, 'synthetic': True,
            'image_url': None,
        }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--count', type=int, default=50000)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--output', type=Path, default=Path('data'))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    path = args.output / 'products.jsonl'
    csv_path = args.output / 'products.csv'
    with path.open('w') as f, csv_path.open('w', newline='') as c:
        fields = ['id','sku','name','brand','category','price','currency','stock','description','specifications','synthetic','image_url']
        writer = csv.DictWriter(c, fieldnames=fields)
        writer.writeheader()
        for product in generate(args.count, args.seed):
            f.write(json.dumps(product, sort_keys=True) + '\n')
            writer.writerow({**product, 'specifications': json.dumps(product['specifications'], sort_keys=True)})
    manifest = {'count': args.count, 'seed': args.seed, 'synthetic': True,
                'source': 'Locally generated fictional data, not scraped or licensed retailer inventory',
                'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                'limitations': ['No real products, reviews, images, sales, or compatibility claims',
                                'Uniform category balance; unsuitable for claims about real buying behavior',
                                'CSV is a neutral interchange format, not a validated Salesforce import']}
    (args.output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(manifest, indent=2))

if __name__ == '__main__':
    main()
