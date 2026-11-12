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
BRANDS = ['Aster', 'Novalume', 'CircuitBay', 'Voltora', 'Pinnacle']
CATALOG_VERSION = 2
FAMILIES = {'tv':['Vista','Cinema','Horizon'], 'mobile':['Pulse','Nova','Arc'], 'laptop':['Airbook','Studio','Workmate'], 'tablet':['Slate','Canvas','Tab'], 'smartwatch':['Tempo','Active','Orbit'], 'headphones':['Quiet','Wave','Studio Sound'], 'camera':['Focus','Frame','Capture'], 'monitor':['View','Clarity','Ultraview'], 'speaker':['Echoform','Room','Roam'], 'gaming':['Playbox','Pocket Play','Gamehub']}

def generate(count=50000, seed=42):
    if count < 1:
        raise ValueError('count must be positive')
    rng = random.Random(seed)
    categories = list(CATEGORIES)
    for i in range(count):
        category = categories[i % len(categories)]
        label, low, high, types, sizes = CATEGORIES[category]
        variant = i // len(categories) + 1
        brand = rng.choice(BRANDS)
        tier = rng.randrange(3)
        kind = types[min(tier, len(types)-1)]
        size = sizes[min(len(sizes)-1, tier + rng.randrange(2))]
        specs = {'color': rng.choice(['black', 'silver', 'blue', 'white'])}
        if category in ('mobile', 'laptop', 'tablet', 'gaming'):
            specs.update(storage_gb=size, ram_gb=[8,16,32][tier] if category == 'laptop' else [4,8,12][tier], platform=kind)
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
        price = round((low + (high-low)*([0.08,0.38,0.78][tier] + rng.uniform(0,.12))) / 10)*10 - .01
        family = FAMILIES[category][tier]
        generation = (variant-1)//250+1
        detail = f'{size}GB' if category in ('mobile','tablet','gaming') else (f'{size}GB SSD' if category=='laptop' else (f'{size} inch' if category in ('tv','monitor') else (f'{size}mm' if category=='smartwatch' else (f'{size}MP' if category=='camera' else f'{size}h' if category=='headphones' else f'{size}W'))))
        use_case = ['everyday essentials','study work productivity','creative entertainment'][tier]
        if category=='laptop':
            specs.update(screen_inches=[13.3,14,16][tier],processor=['Entry 4-core','Performance 8-core','Creator 12-core'][tier],battery_hours=[10,12,8][tier])
        name = f'{brand} {family} {generation} · {detail}'
        yield {
            'id': f'EG-{i+1:06d}', 'sku': f'DEMO-{category.upper()}-{variant:05d}',
            'name': name, 'brand': brand,
            'category': category, 'price': price, 'currency': 'USD',
            'stock': rng.choice([0, 5, 10, 25, 50, 100]),
            'description': f'{label} concept for {use_case}. Synthetic specifications: ' + '; '.join(f'{k}: {v}' for k,v in specs.items()),
            'specifications': specs, 'synthetic': True,
            'image_url': None, 'use_case': use_case, 'catalog_version': CATALOG_VERSION,
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
        fields = ['id','sku','name','brand','category','price','currency','stock','description','specifications','synthetic','image_url','use_case','catalog_version']
        writer = csv.DictWriter(c, fieldnames=fields)
        writer.writeheader()
        for product in generate(args.count, args.seed):
            f.write(json.dumps(product, sort_keys=True) + '\n')
            writer.writerow({**product, 'specifications': json.dumps(product['specifications'], sort_keys=True)})
    manifest = {'catalog_version': CATALOG_VERSION, 'count': args.count, 'seed': args.seed, 'synthetic': True,
                'source': 'Locally generated fictional data, not scraped or licensed retailer inventory',
                'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                'limitations': ['No real products, reviews, images, sales, or compatibility claims',
                                'Uniform category balance; unsuitable for claims about real buying behavior',
                                'CSV is a neutral interchange format, not a validated Salesforce import']}
    (args.output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(manifest, indent=2))

if __name__ == '__main__':
    main()
