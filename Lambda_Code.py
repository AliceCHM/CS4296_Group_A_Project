import json
import time
from datetime import datetime

def lambda_handler(event, context):
    start_time = time.time()
    
    _ = [i**2 for i in range(1000)]
    
    end_time = time.time()
    compute_ms = (end_time - start_time) * 1000
    
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'X-Compute-Time': str(compute_ms)
        },
        'body': json.dumps({
            'message': 'Hello World',
            'timestamp': datetime.utcnow().isoformat(),
            'service': 'AWS Lambda',
            'compute_ms': compute_ms
        })
    }