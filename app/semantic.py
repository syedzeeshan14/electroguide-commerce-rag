"""OpenAI embeddings with a resumable local SQLite cache and cosine retrieval."""
import hashlib
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import numpy as np
import requests

DEFAULT_MODEL='text-embedding-3-small'
DEFAULT_DIMENSIONS=512

class SemanticUnavailable(Exception):
    """Semantic retrieval cannot be trusted; caller should label its fallback."""


def embedding_config(settings):
    model=settings.get('OPENAI_EMBEDDING_MODEL') or DEFAULT_MODEL
    if model not in ('text-embedding-3-small','text-embedding-3-large'):
        raise SemanticUnavailable('Use text-embedding-3-small or text-embedding-3-large for the embedding model.')
    try:
        dimensions=int(settings.get('OPENAI_EMBEDDING_DIMENSIONS') or DEFAULT_DIMENSIONS)
    except (ValueError,TypeError):
        raise SemanticUnavailable('Embedding dimensions must be an integer.') from None
    maximum=1536 if model==DEFAULT_MODEL else 3072
    if not 16<=dimensions<=maximum:
        raise SemanticUnavailable(f'Embedding dimensions must be between 16 and {maximum}.')
    return model,dimensions


def product_document(product):
    # Volatile price/stock and arbitrary SKU/generation numbers are deliberately excluded.
    # Identical descriptive records share an embedding, but retain independent commerce IDs.
    fields={'category':product['category'],'brand':product.get('brand',''),
            'intended use':product.get('use_case',''),
            'specifications':{k.replace('_',' '):v for k,v in sorted(product['specifications'].items())}}
    return 'Electronics product. '+json.dumps(fields,sort_keys=True,ensure_ascii=False)


def document_key(text):
    return hashlib.sha256(('electroguide-semantic-v1\n'+text).encode()).hexdigest()


def normalized(vector,dimensions):
    try:
        result=np.asarray(vector,dtype=np.float32)
    except (TypeError,ValueError,OverflowError):
        raise SemanticUnavailable('Invalid embedding vector.') from None
    if result.shape!=(dimensions,) or not np.isfinite(result).all():
        raise SemanticUnavailable('Embedding dimensions or values are invalid.')
    norm=float(np.linalg.norm(result))
    if not np.isfinite(norm) or norm<=0:
        raise SemanticUnavailable('Embedding vector must have a nonzero finite norm.')
    return result/norm


def embed_texts(settings,texts):
    if not settings.get('OPENAI_API_KEY','').strip():
        raise SemanticUnavailable('Configure OPENAI_API_KEY locally before generating embeddings.')
    if not texts or len(texts)>128 or any(not isinstance(text,str) or not text.strip() for text in texts):
        raise SemanticUnavailable('Embedding batch must contain 1–128 nonempty texts.')
    model,dimensions=embedding_config(settings)
    try:
        response=requests.post('https://api.openai.com/v1/embeddings',
            headers={'Authorization':'Bearer '+settings['OPENAI_API_KEY'].strip(),'Content-Type':'application/json'},
            json={'model':model,'input':texts,'dimensions':dimensions},timeout=60,allow_redirects=False)
        if response.status_code!=200:
            raise SemanticUnavailable(f'OpenAI embeddings returned HTTP {response.status_code}. Check credentials, billing, quota, and model access. Cached batches can be resumed.')
        payload=response.json()
        rows=payload['data']
        if not isinstance(rows,list) or len(rows)!=len(texts):
            raise ValueError('Invalid batch size')
        vectors=[None]*len(texts)
        for row in rows:
            index=row['index']
            if isinstance(index,bool) or not isinstance(index,int) or not 0<=index<len(texts) or vectors[index] is not None:
                raise ValueError('Invalid embedding index')
            vectors[index]=normalized(row['embedding'],dimensions)
        usage=payload.get('usage',{}).get('total_tokens',0)
        return vectors,usage if isinstance(usage,int) and not isinstance(usage,bool) and usage>=0 else 0
    except (requests.RequestException,ValueError,KeyError,TypeError,IndexError):
        raise SemanticUnavailable('Could not read valid OpenAI embeddings. Check connectivity and model settings; saved batches are retained.') from None


class EmbeddingIndex:
    def __init__(self,path):
        self.path=Path(path)

    def _connect(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        connection=sqlite3.connect(str(self.path),timeout=30)
        connection.execute('CREATE TABLE IF NOT EXISTS vectors (doc_key TEXT, model TEXT, dimensions INTEGER, vector BLOB NOT NULL, PRIMARY KEY(doc_key,model,dimensions))')
        connection.execute('CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        return connection

    def status(self,settings):
        if not self.path.exists():
            return {'ready':False,'reason':'missing'}
        model,dimensions=embedding_config(settings)
        with closing(self._connect()) as connection:
            metadata=dict(connection.execute('SELECT key,value FROM metadata'))
            ready=metadata.get('ready')=='true' and metadata.get('model')==model and metadata.get('dimensions')==str(dimensions)
            count=connection.execute('SELECT count(*) FROM vectors WHERE model=? AND dimensions=?',(model,dimensions)).fetchone()[0]
        return {'ready':ready,'vectors':count,'model':model,'dimensions':dimensions,'fingerprint':metadata.get('fingerprint')}

    def build(self,products,settings,batch_size=64,progress=None):
        if not 1<=batch_size<=128:
            raise ValueError('batch_size must be between 1 and 128')
        model,dimensions=embedding_config(settings)
        documents={}
        product_count=0
        digest=hashlib.sha256()
        for product in products:
            text=product_document(product)
            key=document_key(text)
            documents[key]=text
            digest.update((product['id']+key).encode())
            product_count+=1
        if not documents:
            raise SemanticUnavailable('Cannot build an index for an empty catalog.')
        connection=self._connect()
        try:
            existing=set()
            for key,blob in connection.execute('SELECT doc_key,vector FROM vectors WHERE model=? AND dimensions=?',(model,dimensions)):
                try:
                    normalized(np.frombuffer(blob,dtype='<f4'),dimensions)
                    existing.add(key)
                except (ValueError,SemanticUnavailable):
                    pass # Invalid cached vectors are regenerated by the next batch.
            missing=[key for key in sorted(documents) if key not in existing]
            report={'products':product_count,'unique_documents':len(documents),'cached':len(documents)-len(missing),'embedded':0,'usage_tokens':0,'model':model,'dimensions':dimensions}
            if progress:
                progress({**report,'remaining':len(missing)})
            # Publish readiness only after every required document exists. Save each batch for resume.
            connection.execute("INSERT OR REPLACE INTO metadata VALUES ('ready','false')")
            connection.commit()
            for start in range(0,len(missing),batch_size):
                batch=missing[start:start+batch_size]
                vectors,tokens=embed_texts(settings,[documents[key] for key in batch])
                with connection:
                    connection.executemany('INSERT OR REPLACE INTO vectors VALUES (?,?,?,?)',[(key,model,dimensions,vector.astype('<f4').tobytes()) for key,vector in zip(batch,vectors)])
                report['embedded']+=len(batch)
                report['usage_tokens']+=tokens
                if progress:
                    progress({**report,'remaining':len(missing)-report['embedded']})
            with connection:
                connection.executemany('INSERT OR REPLACE INTO metadata VALUES (?,?)',[
                    ('ready','true'),('model',model),('dimensions',str(dimensions)),
                    ('fingerprint',digest.hexdigest()),('products',str(product_count)),('unique_documents',str(len(documents)))])
            return report
        finally:
            connection.close()

    def similarities(self,products,question,settings):
        status=self.status(settings)
        if not status['ready']:
            raise SemanticUnavailable('Semantic index is missing, incomplete, or uses different model settings. Run python -m scripts.build_semantic_index.')
        keys=[document_key(product_document(product)) for product in products]
        unique=list(dict.fromkeys(keys))
        vectors={}
        connection=self._connect()
        try:
            for start in range(0,len(unique),400):
                batch=unique[start:start+400]
                placeholders=','.join('?' for _ in batch)
                sql=f'SELECT doc_key,vector FROM vectors WHERE model=? AND dimensions=? AND doc_key IN ({placeholders})'
                for key,blob in connection.execute(sql,[status['model'],status['dimensions'],*batch]):
                    vectors[key]=normalized(np.frombuffer(blob,dtype='<f4'),status['dimensions'])
        finally:
            connection.close()
        if any(key not in vectors for key in unique):
            raise SemanticUnavailable('Catalog descriptions changed. Rebuild the semantic index; unchanged vectors will be reused.')
        if not unique:
            return {}
        query_vectors,_=embed_texts(settings,[question[:4000]])
        matrix=np.stack([vectors[key] for key in unique])
        values=np.clip(matrix@query_vectors[0],-1,1)
        by_key=dict(zip(unique,values))
        return {product['id']:float(by_key[key]) for product,key in zip(products,keys)}
