"""Offline lexical baseline. This is deliberately not labeled vector RAG."""
import json
import re
import sqlite3
from pathlib import Path

ALIASES = {'television':'tv', 'televisions':'tv', 'tvs':'tv', 'phone':'mobile', 'phones':'mobile', 'smartphone':'mobile', 'smartphones':'mobile', 'laptops':'laptop', 'tablets':'tablet', 'watches':'smartwatch', 'watch':'smartwatch', 'monitors':'monitor', 'cameras':'camera', 'speakers':'speaker'}

class Catalog:
    def __init__(self, database='data/catalog.sqlite'):
        self.connection = sqlite3.connect(database, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row

    def build(self, source='data/products.jsonl'):
        with self.connection, Path(source).open(encoding='utf-8') as source_file:
            self.connection.execute('DROP TABLE IF EXISTS products')
            self.connection.execute('DROP TABLE IF EXISTS product_search')
            self.connection.execute('CREATE TABLE products (id TEXT PRIMARY KEY, category TEXT, price REAL, stock INTEGER, payload TEXT)')
            self.connection.execute('CREATE VIRTUAL TABLE product_search USING fts5(id UNINDEXED, text)')
            for line in source_file:
                p = json.loads(line)
                self.connection.execute('INSERT INTO products VALUES (?,?,?,?,?)', (p['id'],p['category'],p['price'],p['stock'],line.strip()))
                self.connection.execute('INSERT INTO product_search VALUES (?,?)', (p['id'], ' '.join([p['name'],p['category'],p['description']])))
            self.connection.execute('CREATE INDEX filters ON products(category,price,stock)')

    def search(self, query='', category=None, max_price=None, in_stock=True, limit=10, sort='relevance', offset=0, brand=None):
        limit = max(1, min(int(limit), 50))
        words = re.findall(r'[a-z0-9]+', query.lower())
        tokens = [ALIASES.get(word, word) for word in words]
        clauses, params = [], []
        join = ''
        order = 'p.price, p.id'
        exact_code = re.fullmatch(r'EG-[0-9]{6}', query.strip(), re.IGNORECASE)
        if exact_code:
            clauses.append('p.id=?')
            params.append(query.strip().upper())
        elif tokens:
            join = ' JOIN product_search ON p.id=product_search.id'
            clauses.append('product_search MATCH ?')
            params.append(' AND '.join('"' + token + '"' for token in tokens))
            order = 'bm25(product_search), p.price, p.id'
        if category:
            clauses.append('p.category=?')
            params.append(category)
        if max_price is not None:
            if float(max_price) < 0:
                raise ValueError('max_price must be nonnegative')
            clauses.append('p.price<=?')
            params.append(float(max_price))
        if in_stock:
            clauses.append('p.stock>0')
        if brand:
            clauses.append("json_extract(p.payload, '$.brand')=?")
            params.append(brand)
        if sort == 'price_low':
            order = 'p.price, p.id'
        elif sort == 'price_high':
            order = 'p.price DESC, p.id'
        elif sort == 'featured':
            order = 'CAST(substr(p.id,4) AS INTEGER)'
        where = ' WHERE ' + ' AND '.join(clauses) if clauses else ''
        sql = 'SELECT p.payload FROM products p' + join + where + ' ORDER BY ' + order + ' LIMIT ? OFFSET ?'
        return [json.loads(row['payload']) for row in self.connection.execute(sql, [*params,limit,max(0,int(offset))])]
