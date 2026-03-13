#!/usr/bin/env python
"""Simple test runner to verify error handling tests."""
import subprocess
import sys

error_tests = [
    "test_missing_csv_file_warning",
    "test_malformed_csv_handling",
    "test_file_write_failure_raises_ioerror",
    "test_incomplete_summary_dict_raises_keyerror",
    "test_incomplete_severity_distribution_raises_keyerror",
]

print("Running error handling tests...")
print("=" * 60)

for test_name in error_tests:
    print(f"\nRunning: {test_name}")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", 
         f"tests/test_generate_public_report.py::{test_name}",
         "-v", "--tb=short"],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        print(f"  ✓ PASSED")
    else:
        print(f"  ✗ FAILED")
        print(result.stdout)
        print(result.stderr)

print("\n" + "=" * 60)
print("Test run complete")
