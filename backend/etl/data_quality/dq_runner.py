#!/usr/bin/env python3
"""
PropRoo Data Quality Runner

Orchestrates Soda Core scans for data quality validation.
Generates structured JSON reports for CI/CD artifact storage.

Usage:
    python dq_runner.py --data-dir /path/to/data --output-dir /path/to/reports
"""

import argparse
import json
import logging
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def run_soda_scan(
    scan_name: str, config_path: Path, variables: Dict[str, Any] = None
) -> Dict[str, Any]:
    """Run a Soda scan and return parsed JSON results."""
    logger.info(f"Running Soda scan: {scan_name}")

    cmd = ["soda", "scan"]

    # Add configuration
    if config_path and config_path.exists():
        cmd.extend(["-c", str(config_path)])

    # Add variables
    if variables:
        for key, value in variables.items():
            cmd.extend(["-v", f"{key}={value}"])

    # Add scan name and output format
    cmd.extend([scan_name, "--format", "json", "--output", "-"])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            cwd=Path(__file__).parent.parent.parent,  # repo root
        )

        # Parse JSON output
        scan_result = json.loads(result.stdout)
        logger.info(f"Soda scan {scan_name} completed successfully")
        return scan_result

    except subprocess.CalledProcessError as e:
        logger.error(f"Soda scan {scan_name} failed with exit code {e.returncode}")
        logger.error(f"stderr: {e.stderr}")
        # Return error structure
        return {
            "scan": {
                "name": scan_name,
                "outcome": "ERROR",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            "checks": [],
            "errors": [{"message": e.stderr}],
        }
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Soda scan output: {e}")
        logger.error(f"stdout: {result.stdout}")
        return {
            "scan": {
                "name": scan_name,
                "outcome": "ERROR",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            "checks": [],
            "errors": [{"message": f"JSON decode error: {e}"}],
        }


def main():
    parser = argparse.ArgumentParser(description="Run Soda Core data quality scans")
    parser.add_argument(
        "--data-dir",
        type=str,
        required=True,
        help="Path to the data directory containing parquet files",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Path to write JSON scan reports",
    )
    parser.add_argument(
        "--vars",
        nargs="*",
        default=[],
        help="Variables to pass to Soda scans (format: key=value)",
    )

    args = parser.parse_args()

    # Parse variables
    variables = {}
    for var in args.vars:
        if "=" in var:
            key, value = var.split("=", 1)
            variables[key] = value

    data_path = Path(args.data_dir)
    if not data_path.exists():
        logger.error(f"Data directory not found: {data_path}")
        sys.exit(1)

    # Setup paths
    checks_dir = Path(__file__).parent / "checks"
    output_path = Path(args.output_dir) if args.output_dir else None

    if output_path:
        output_path.mkdir(parents=True, exist_ok=True)

    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    timestamp = datetime.now(timezone.utc).isoformat()

    logger.info(f"Starting Soda data quality scans - Run ID: {run_id}")
    logger.info("=" * 60)

    # Define scans to run
    scans = [
        ("sales_quality", checks_dir / "sales_quality.yml"),
        ("growth_quality", checks_dir / "growth_quality.yml"),
        ("summary_quality", checks_dir / "summary_quality.yml"),
    ]

    all_results = {
        "run_id": run_id,
        "timestamp": timestamp,
        "data_directory": str(data_path),
        "scans": {},
        "summary": {
            "total_scans": len(scans),
            "passed_scans": 0,
            "failed_scans": 0,
            "error_scans": 0,
        },
    }

    # Run each scan
    for scan_name, config_path in scans:
        if not config_path.exists():
            logger.warning(f"Scan config not found: {config_path}")
            all_results["scans"][scan_name] = {
                "error": f"Config file not found: {config_path}"
            }
            all_results["summary"]["error_scans"] += 1
            continue

        scan_result = run_soda_scan(scan_name, config_path, variables)
        all_results["scans"][scan_name] = scan_result

        # Update summary
        outcome = scan_result.get("scan", {}).get("outcome", "ERROR")
        if outcome == "PASS":
            all_results["summary"]["passed_scans"] += 1
        elif outcome == "FAIL":
            all_results["summary"]["failed_scans"] += 1
        else:
            all_results["summary"]["error_scans"] += 1

    # Determine overall status
    all_pass = (
        all_results["summary"]["failed_scans"] == 0
        and all_results["summary"]["error_scans"] == 0
    )
    all_results["overall_status"] = "PASS" if all_pass else "FAIL"

    # Print summary
    logger.info("\n" + "=" * 60)
    logger.info("SODA DATA QUALITY SCAN SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Run ID: {run_id}")
    logger.info(f"Overall Status: {all_results['overall_status']}")
    logger.info(
        f"Scans: {all_results['summary']['passed_scans']}/{all_results['summary']['total_scans']} passed"
    )

    for scan_name, scan_result in all_results["scans"].items():
        if "error" in scan_result:
            logger.warning(f"  {scan_name}: ERROR - {scan_result['error']}")
        else:
            outcome = scan_result.get("scan", {}).get("outcome", "UNKNOWN")
            checks_passed = sum(
                1 for c in scan_result.get("checks", []) if c.get("outcome") == "PASS"
            )
            checks_total = len(scan_result.get("checks", []))
            logger.info(
                f"  {scan_name}: {outcome} ({checks_passed}/{checks_total} checks passed)"
            )

    logger.info("=" * 60)

    # Write JSON report
    if output_path:
        report_path = output_path / f"soda-scan-report-{run_id}.json"
        with open(report_path, "w") as f:
            json.dump(all_results, f, indent=2, default=str)
        logger.info(f"\nJSON report written to {report_path}")

        # Also write latest symlink for easy access
        latest_path = output_path / "soda-scan-report-latest.json"
        if latest_path.exists():
            latest_path.unlink()
        latest_path.symlink_to(report_path.name)
        logger.info(f"Latest report symlink: {latest_path}")

    # Exit with appropriate code
    if not all_pass:
        logger.error("Some Soda scans failed or had errors")
        sys.exit(1)
    else:
        logger.info("All Soda scans passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()
