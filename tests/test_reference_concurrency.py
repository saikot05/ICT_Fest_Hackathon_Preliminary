import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from app.services.reference import next_reference_code

def test_reference_concurrency():
    num_requests = 50
    reference_codes = []

    # Worker function calling the reference generator directly
    def generate_code():
        return next_reference_code()

    start_time = time.time()
    
    # Spawn 50 threads to concurrently generate reference codes
    with ThreadPoolExecutor(max_workers=num_requests) as executor:
        futures = [executor.submit(generate_code) for _ in range(num_requests)]
        for future in as_completed(futures):
            reference_codes.append(future.result())

    duration = time.time() - start_time

    # Output details
    print("\n--- TEST PASSED SUCCESSFULLY ---")
    print(f"Spawned {num_requests} concurrent threads generating reference codes.")
    print(f"Total reference codes generated: {len(reference_codes)}")
    print(f"Unique reference codes generated: {len(set(reference_codes))}")
    print(f"Total duration: {duration:.2f} seconds")

    # Assert all reference codes are strictly unique
    assert len(reference_codes) == len(set(reference_codes)), "Duplicate reference codes detected!"
