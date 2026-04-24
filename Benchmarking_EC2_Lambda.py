import requests
import time
import statistics
import asyncio
import aiohttp
import pandas as pd
import json
import subprocess
import sys
from datetime import datetime
import math

class Benchmark:
    def __init__(self):
        with open('lambda-url.txt', 'r') as f:
            self.lambda_url = f.read().strip()
        with open('ec2-ip.txt', 'r') as f:
            ec2_ip = f.read().strip()
            self.ec2_url = f"http://{ec2_ip}:5000/hello"
        
        self.results = []
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
    def percentile(self, data, p):
        if not data:
            return 0
        data_sorted = sorted(data)
        index = (len(data_sorted) - 1) * p / 100
        lower = math.floor(index)
        upper = math.ceil(index)
        if lower == upper:
            return data_sorted[lower]
        return (data_sorted[lower] * (upper - index) + 
                data_sorted[upper] * (index - lower))
    
    def single_request(self, url):
        try:
            start = time.perf_counter()
            r = requests.get(url, timeout=30)
            end = time.perf_counter()
            latency_ms = (end - start) * 1000
            return latency_ms, r.status_code
        except Exception as e:
            print(f"  Error: {e}")
            return None, 500
    
    # TEST 1: COLD START
    def test_cold_start(self, name, url, repeats=5):
        print(f"\n{'='*60}")
        print(f"TEST 1: COLD START - {name}")
        print(f"Running {repeats} cold start attempts")
        print(f"{'='*60}")
        
        cold_times = []
        errors = 0
        
        for i in range(repeats):
            print(f"  Attempt {i+1}/{repeats}...", end="", flush=True)
            
            if i > 0:
                time.sleep(30)
            
            latency, code = self.single_request(url)
            
            if latency and code == 200:
                cold_times.append(latency)
                print(f" ✓ {latency:.2f} ms")
            else:
                errors += 1
                print(f" ✗ FAILED (code {code})")
        
        if cold_times:
            self.results.append({
                "Platform": name,
                "Test": "Cold Start",
                "Repeats": repeats,
                "Avg ms": round(statistics.mean(cold_times), 2),
                "Min ms": round(min(cold_times), 2),
                "Max ms": round(max(cold_times), 2),
                "P50 ms": round(self.percentile(cold_times, 50), 2),
                "P95 ms": round(self.percentile(cold_times, 95), 2),
                "P99 ms": round(self.percentile(cold_times, 99), 2),
                "Std Dev": round(statistics.stdev(cold_times) if len(cold_times) > 1 else 0, 2),
                "Errors": errors,
                "Requests/sec": "N/A"
            })
            print(f"\n  Summary: {statistics.mean(cold_times):.2f} ms avg over {len(cold_times)} successful cold starts")
    
    # TEST 2: WARM TEST
    def test_warm(self, name, url, n=100):
        print(f"\n{'='*60}")
        print(f"TEST 2: WARM PERFORMANCE - {name}")
        print(f"Running {n} sequential requests (concurrency=1)")
        print(f"{'='*60}")
        
        times = []
        errors = 0
        
        for i in range(n):
            latency, code = self.single_request(url)
            if latency and code == 200:
                times.append(latency)
            else:
                errors += 1
            
            if (i+1) % 20 == 0:
                print(f"  Progress: {i+1}/{n} requests completed")
        
        if times:
            avg_ms = statistics.mean(times)
            req_per_sec = 1000 / avg_ms if avg_ms > 0 else 0
            
            self.results.append({
                "Platform": name,
                "Test": "Warm (c=1)",
                "Repeats": n,
                "Avg ms": round(avg_ms, 2),
                "Min ms": round(min(times), 2),
                "Max ms": round(max(times), 2),
                "P50 ms": round(self.percentile(times, 50), 2),
                "P95 ms": round(self.percentile(times, 95), 2),
                "P99 ms": round(self.percentile(times, 99), 2),
                "Std Dev": round(statistics.stdev(times), 2),
                "Errors": errors,
                "Requests/sec": round(req_per_sec, 2)
            })
            print(f"\n  Results: {avg_ms:.2f} ms avg, {req_per_sec:.2f} req/sec, {errors} errors")
    
    # TESTS 3-5: CONCURRENCY
    async def fetch_concurrent(self, session, url):
        try:
            start = time.perf_counter()
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                await resp.text()
                end = time.perf_counter()
                return (end - start) * 1000, resp.status
        except:
            return None, 500
    
    async def run_concurrent(self, url, total_requests, concurrency):
        all_times = []
        errors = 0
        
        async with aiohttp.ClientSession() as session:
            batch_size = min(concurrency * 10, 1000)
            for batch_start in range(0, total_requests, batch_size):
                batch_end = min(batch_start + batch_size, total_requests)
                tasks = [self.fetch_concurrent(session, url) for _ in range(batch_end - batch_start)]
                results_batch = await asyncio.gather(*tasks)
                
                for latency, status in results_batch:
                    if latency and status == 200:
                        all_times.append(latency)
                    else:
                        errors += 1
        
        return all_times, errors
    
    def test_concurrency(self, name, url):
        print(f"\n{'='*60}")
        print(f"TESTS 3-5: CONCURRENCY - {name}")
        print(f"{'='*60}")
        
        test_configs = [
            {"name": "Low Concurrency", "n": 100, "c": 1},
            {"name": "Low Concurrency", "n": 500, "c": 5},
            {"name": "Low Concurrency", "n": 1000, "c": 10},
            {"name": "Heavy Load", "n": 5000, "c": 50},
            {"name": "Heavy Load", "n": 10000, "c": 100},
        ]
        
        for config in test_configs:
            print(f"\n  {config['name']}: {config['n']} requests, {config['c']} concurrent users")
            times, errors = asyncio.run(self.run_concurrent(url, config['n'], config['c']))
            
            if times:
                avg_ms = statistics.mean(times)
                actual_duration = (sum(times) / 1000) / config['c']  # Approximate
                throughput = config['n'] / actual_duration if actual_duration > 0 else 0
                
                self.results.append({
                    "Platform": name,
                    "Test": f"{config['name']} (c={config['c']})",
                    "Repeats": config['n'],
                    "Avg ms": round(avg_ms, 2),
                    "Min ms": round(min(times), 2),
                    "Max ms": round(max(times), 2),
                    "P50 ms": round(self.percentile(times, 50), 2),
                    "P95 ms": round(self.percentile(times, 95), 2),
                    "P99 ms": round(self.percentile(times, 99), 2),
                    "Std Dev": round(statistics.stdev(times), 2),
                    "Errors": errors,
                    "Requests/sec": round(throughput, 2)
                })
                print(f"    ✓ Avg: {avg_ms:.2f} ms, Errors: {errors}, Throughput: {throughput:.2f} req/sec")
            else:
                print(f"    ✗ Test failed - no successful requests")
    
    # SUSTAINED LOAD TEST
    def test_sustained_load(self, name, url, duration=60, concurrency=20):
        print(f"\n{'='*60}")
        print(f"TEST: SUSTAINED LOAD - {name}")
        print(f"Running for {duration} seconds with {concurrency} concurrent users")
        print(f"{'='*60}")
        
        async def sustained():
            times = []
            errors = 0
            end_time = time.time() + duration
            
            async with aiohttp.ClientSession() as session:
                tasks = []
                while time.time() < end_time:
                    while len(tasks) < concurrency:
                        tasks.append(asyncio.create_task(self.fetch_concurrent(session, url)))
                    
                    done, pending = await asyncio.wait(tasks, timeout=0.1, return_when=asyncio.FIRST_COMPLETED)
                    tasks = list(pending)
                    
                    for task in done:
                        latency, status = task.result()
                        if latency and status == 200:
                            times.append(latency)
                        else:
                            errors += 1
                    
                    await asyncio.sleep(0.01)
            
            return times, errors
        
        times, errors = asyncio.run(sustained())
        total_requests = len(times) + errors
        
        if times:
            avg_ms = statistics.mean(times)
            throughput = total_requests / duration
            
            self.results.append({
                "Platform": name,
                "Test": f"Sustained Load ({duration}s, c={concurrency})",
                "Repeats": total_requests,
                "Avg ms": round(avg_ms, 2),
                "Min ms": round(min(times), 2),
                "Max ms": round(max(times), 2),
                "P50 ms": round(self.percentile(times, 50), 2),
                "P95 ms": round(self.percentile(times, 95), 2),
                "P99 ms": round(self.percentile(times, 99), 2),
                "Std Dev": round(statistics.stdev(times), 2),
                "Errors": errors,
                "Requests/sec": round(throughput, 2)
            })
            print(f"\n  Results:")
            print(f"    Total requests: {total_requests}")
            print(f"    Average latency: {avg_ms:.2f} ms")
            print(f"    Throughput: {throughput:.2f} req/sec")
            print(f"    Errors: {errors}")
    
    def run_all(self):
        print("\n" + "="*60)
        print("AWS PERFORMANCE BENCHMARK: Lambda vs EC2")
        print(f"Start time: {self.timestamp}")
        print("="*60)
        
        print(f"\nLambda URL: {self.lambda_url}")
        print(f"EC2 URL: {self.ec2_url}")
        
        print("\nPre-warming services...")
        self.single_request(self.lambda_url)
        self.single_request(self.ec2_url)
        time.sleep(5)
        
        for name, url in [("Lambda", self.lambda_url), ("EC2", self.ec2_url)]:
            print(f"\n{'#'*60}")
            print(f"# TESTING {name}")
            print(f"{'#'*60}")
            
            # Test 1: Cold Start
            print("  - Press Enter to continue...")
            input()
            
            self.test_cold_start(name, url, repeats=5)
            
            # Test 2: Warm
            self.test_warm(name, url, n=100)
            
            # Tests 3-5: Concurrency
            self.test_concurrency(name, url)
            
            self.test_sustained_load(name, url, duration=60, concurrency=20)
        
        self.save_results()
    
    def save_results(self):
        print("\n" + "="*60)
        print("BENCHMARK COMPLETE")
        print("="*60)
        
        if not self.results:
            print("\nNo results to display.")
            return
        
        df = pd.DataFrame(self.results)
        
        print("\nSUMMARY TABLE:")
        print(df.to_string(index=False))
        
        return df

if __name__ == "__main__":
    benchmark = Benchmark()
    benchmark.run_all()