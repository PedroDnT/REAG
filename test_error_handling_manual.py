#!/usr/bin/env python
"""Manual verification of error handling implementation."""
import tempfile
import shutil
from pathlib import Path
import sys

sys.path.insert(0, '.')

from scripts.generate_public_report import PublicReportGenerator
from config.settings import Config

def test_missing_files():
    """Test 8.1: Missing CSV files return empty DataFrames with warnings"""
    temp_dir = Path(tempfile.mkdtemp())
    try:
        config = Config()
        config.REPORTS_DIR = temp_dir
        config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        
        generator = PublicReportGenerator(config=config)
        reports = generator.load_anomaly_reports()
        
        # All should be empty
        assert all(df.empty for df in reports.values()), "Missing files should return empty DataFrames"
        return True
    finally:
        shutil.rmtree(temp_dir)

def test_malformed_csv():
    """Test 8.2: Malformed CSV returns empty DataFrame with error log"""
    temp_dir = Path(tempfile.mkdtemp())
    try:
        config = Config()
        config.REPORTS_DIR = temp_dir
        config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        
        # Create malformed CSV
        (temp_dir / 'anomalias_fluxo.csv').write_text('bad;csv\ndata', encoding='utf-8')
        
        generator = PublicReportGenerator(config=config)
        reports = generator.load_anomaly_reports()
        
        # Should handle gracefully
        assert reports['flow_anomalies'].empty, "Malformed CSV should return empty DataFrame"
        return True
    finally:
        shutil.rmtree(temp_dir)

def test_file_write_error():
    """Test 8.3: File write failures raise IOError"""
    temp_dir = Path(tempfile.mkdtemp())
    try:
        config = Config()
        config.REPORTS_DIR = temp_dir
        config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        
        generator = PublicReportGenerator(config=config)
        
        # Try to write to invalid path
        try:
            generator.generate_report(
                output_format='markdown',
                output_file='/root/invalid/path.md'
            )
            return False  # Should have raised
        except IOError as e:
            assert 'Failed to write report' in str(e), "IOError should have descriptive message"
            return True
    finally:
        shutil.rmtree(temp_dir)

def test_incomplete_summary():
    """Test 8.4: Incomplete summary raises KeyError"""
    import pandas as pd
    
    generator = PublicReportGenerator()
    reports = {
        'flow_anomalies': pd.DataFrame(),
        'pl_drops': pd.DataFrame(),
        'runs': pd.DataFrame(),
        'divergences': pd.DataFrame(),
    }
    
    incomplete_summary = {
        'generation_date': '2024-01-01',
        'total_anomalies': 10,
        # Missing required keys
    }
    
    try:
        generator._build_report_data(incomplete_summary, reports)
        return False  # Should have raised
    except KeyError as e:
        assert 'missing required key' in str(e).lower(), "KeyError should mention missing key"
        return True

if __name__ == '__main__':
    tests = [
        ('8.1 Missing CSV files', test_missing_files),
        ('8.2 Malformed CSV', test_malformed_csv),
        ('8.3 File write error', test_file_write_error),
        ('8.4 Incomplete summary', test_incomplete_summary),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            results.append((name, False))
    
    # Write results to file since stdout is not working
    with open('/tmp/test_results.txt', 'w') as f:
        f.write("Error Handling Test Results\n")
        f.write("=" * 50 + "\n\n")
        for name, passed in results:
            status = "PASS" if passed else "FAIL"
            f.write(f"{status}: {name}\n")
        
        all_passed = all(passed for _, passed in results)
        f.write("\n" + "=" * 50 + "\n")
        f.write(f"Overall: {'ALL TESTS PASSED' if all_passed else 'SOME TESTS FAILED'}\n")
    
    # Exit with appropriate code
    sys.exit(0 if all(passed for _, passed in results) else 1)
