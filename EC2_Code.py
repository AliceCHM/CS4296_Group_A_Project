from flask import Flask, jsonify
from datetime import datetime
import time

app = Flask(__name__)

@app.route('/hello')
def hello():
    start_time = time.time()
    _ = [i**2 for i in range(1000)]
    compute_ms = (time.time() - start_time) * 1000
    
    return jsonify({
        "message": "Hello World",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "AWS EC2",
        "compute_ms": compute_ms
    })

@app.route('/health')
def health():
    return jsonify({"status": "healthy"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)