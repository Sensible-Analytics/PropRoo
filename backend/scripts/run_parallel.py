#!/usr/bin/env python3
"""
Consolidated Parallel Runner
Runs multiple backfill processes simultaneously with staggered starts.
"""
import subprocess
import time
import sys
import argparse
import logging
from typing import List, Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)

def run_parallel(backfill_type: str, num_processes: int, records_per_batch: int, stagger_delay: int) -> None:
    logger.info(f"Starting {num_processes} parallel {backfill_type} processes...")
    logger.info(f"Each batch: {records_per_batch} records")
    logger.info(f"Stagger delay: {stagger_delay} seconds")
    
    processes: List[Dict[str, Any]] = []
    
    for i in range(num_processes):
        offset = i * records_per_batch
        batch_id = i + 1
        
        # Use the consolidated backfill script
        cmd = [
            "python3",
            "backend/scripts/backfill.py",
            backfill_type,
            "--limit", str(records_per_batch),
            "--offset", str(offset),
            "--batch-id", str(batch_id)
        ]
        
        logger.info(f"Starting Batch {batch_id} (offset: {offset})...")
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        processes.append({
            'id': batch_id,
            'process': process,
            'offset': offset,
            'finished': False
        })
        
        if i < num_processes - 1:
            logger.info(f"Waiting {stagger_delay}s before starting next batch...")
            time.sleep(stagger_delay)
    
    logger.info("="*60)
    logger.info(f"All {num_processes} processes started!")
    logger.info("="*60)
    
    # Monitor processes
    logger.info("Monitoring processes (Ctrl+C to stop monitoring, processes will continue)...")
    try:
        while any(not p['finished'] for p in processes):
            for p in processes:
                if not p['finished'] and p['process'].poll() is not None:
                    logger.info(f"Batch {p['id']} completed!")
                    p['finished'] = True
            time.sleep(5)
    except KeyboardInterrupt:
        logger.info("Stopped monitoring. Processes are still running in background.")
        sys.exit(0)

def main() -> None:
    parser = argparse.ArgumentParser(description="Consolidated Parallel Runner")
    parser.add_argument("type", choices=["geocoding", "listings"], help="Type of runner to start")
    parser.add_argument("--procs", type=int, help="Number of parallel processes")
    parser.add_argument("--batch", type=int, help="Records per batch")
    parser.add_argument("--stagger", type=int, default=10, help="Stagger delay in seconds")
    
    args = parser.parse_args()
    
    # Default configurations if not provided
    if args.type == "geocoding":
        num_procs = args.procs or 5
        batch_size = args.batch or 1000
    else:  # listings
        num_procs = args.procs or 3
        batch_size = args.batch or 100
        
    run_parallel(args.type, num_procs, batch_size, args.stagger)

if __name__ == "__main__":
    main()
