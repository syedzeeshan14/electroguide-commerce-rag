from app.catalog import Catalog

if __name__ == '__main__':
    catalog = Catalog()
    catalog.build()
    print('Indexed products:', catalog.connection.execute('SELECT count(*) FROM products').fetchone()[0])
