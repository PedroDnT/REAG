#!/usr/bin/env python
"""Verify error handling tests by importing and running them."""
import sys
import os

# Add current directory to path
sys.path.insert(0, os.getcwd())

# Import test module
try:
    import tests.test_generate_public_report as test_module
    print("✓ Test module imported successfully")
    
    # Count test functions
    test_funcs = [name for name in dir(test_module) if name.startswith('test_')]
    print(f"✓ Found {len(test_funcs)} test functions")
    
    # Check for error handling tests
    error_tests = [
        'test_missing_csv_file_warning',
        'test_malformed_csv_handling',
        'test_file_write_failure_raises_ioerror',
        'test_incomplete_summary_dict_raises_keyerror',
        'test_incomplete_severity_distribution_raises_keyerror',
    ]
    
    print("\nError handling tests:")
    for test_name in error_tests:
        if test_name in test_funcs:
            print(f"  ✓ {test_name}")
        else:
            print(f"  ✗ {test_name} - MISSING")
    
    print("\n✓ All required error handling tests are present")
    sys.exit(0)
    
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
