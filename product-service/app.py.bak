# ~/shopmicro/product-service/app.py
from flask import Flask, jsonify
import redis, json, os

app = Flask(__name__)
r = redis.Redis(host=os.getenv('REDIS_HOST','cache'), port=6379, decode_responses=True)

@app.route('/products')
def list_products():
    cached = r.get('products')
    if cached:
        return jsonify({'source':'cache','data':json.loads(cached)})
    data = [{'id':1,'name':'Laptop','price':999},{'id':2,'name':'Mouse','price':25}]
    r.setex('products', 60, json.dumps(data))
    return jsonify({'source':'db','data':data})

@app.route('/health')
def health(): return jsonify({'status':'ok'})

if __name__ == '__main__': app.run(host='0.0.0.0', port=5000)
