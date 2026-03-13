# Implementation Plan: Report Generation Refactoring

## Overview

This plan refactors the report generation system in `scripts/generate_public_report.py` to eliminate ~200 lines of duplicate logic by introducing a unified `ReportData` dataclass and format-specific renderers. The refactoring separates data preparation from presentation, improving maintainability, testability, and extensibility.

## Tasks

- [-] 1. Create data model dataclasses
  - [x] 1.1 Implement ReportMetadata, ExecutiveSummary, DetailedFindings, SeverityDistribution dataclasses
    - Create frozen dataclasses with type annotations
    - Add docstrings describing each field
    - Place at top of scripts/generate_public_report.py after imports
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

  - [x] 1.2 Implement AnonymizedDatasets dataclass
    - Create frozen dataclass containing four DataFrame fields
    - Add validation docstrings for anonymization requirements
    - _Requirements: 1.1, 1.2, 1.3, 2.1, 2.2_

  - [x] 1.3 Implement complete ReportData dataclass
    - Create frozen dataclass aggregating all nested dataclasses
    - Include methodology_text and disclaimer_text string fields
    - Add comprehensive docstring
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

  - [x] 1.4 Write unit tests for dataclass construction
    - Test valid construction with all fields
    - Test immutability (frozen=True enforcement)
    - Test with empty DataFrames
    - _Requirements: 13.3_

- [-] 2. Implement renderer abstract base class and concrete renderers
  - [x] 2.1 Create ReportRenderer abstract base class
    - Define abstract render method with ReportData parameter
    - Add docstring describing interface contract
    - Place after dataclass definitions
    - _Requirements: 4.1, 4.2, 14.2_

  - [x] 2.2 Implement MarkdownRenderer
    - Inherit from ReportRenderer
    - Implement render method producing valid Markdown
    - Add helper methods: _render_header, _render_executive_summary, _render_detailed_findings
    - Include all report sections (metadata, summary, findings, methodology, disclaimer)
    - _Requirements: 3.1, 3.2, 3.5, 4.3_

  - [x] 2.3 Implement HtmlRenderer
    - Inherit from ReportRenderer
    - Implement render method producing valid HTML5 with embedded CSS
    - Add helper methods: _render_html_template, _render_metric_cards, _render_findings_list
    - Include all report sections
    - _Requirements: 3.1, 3.3, 3.5, 4.3_

  - [x] 2.4 Implement JsonRenderer
    - Inherit from ReportRenderer
    - Implement render method producing valid JSON
    - Add helper methods: _dataframe_to_records, _build_json_structure
    - Convert DataFrames to JSON-serializable records
    - Include all report sections
    - _Requirements: 3.1, 3.4, 3.5, 4.3_

  - [x] 2.5 Write unit tests for each renderer
    - Test output format validity (Markdown syntax, HTML validity, JSON parsing)
    - Test all sections present in output
    - Test with empty datasets
    - _Requirements: 13.4_

  - [x] 2.6 Write property test for renderer determinism
    - **Property 3: Renderer Determinism**
    - **Validates: Requirements 4.5, 9.2**
    - Test that calling render twice with same ReportData produces identical output
    - Use hypothesis to generate varied ReportData instances
    - _Requirements: 4.5, 9.2, 13.7_

  - [ ] 2.7 Write property test for renderer immutability
    - **Property 6: No Side Effects**
    - **Validates: Requirements 9.1, 9.5**
    - Test that rendering does not modify input ReportData
    - Verify data unchanged after render call
    - _Requirements: 9.1, 9.5, 13.7_

- [-] 3. Add _build_report_data method to PublicReportGenerator
  - [x] 3.1 Implement _build_report_data method
    - Accept summary dict and reports dict parameters
    - Extract and construct ReportMetadata from summary
    - Construct ExecutiveSummary, DetailedFindings, SeverityDistribution from summary
    - Anonymize all DataFrames and construct AnonymizedDatasets
    - Define methodology_text and disclaimer_text strings
    - Return immutable ReportData instance
    - Add comprehensive docstring with Args, Returns sections
    - _Requirements: 1.1, 2.1, 2.2, 2.3, 5.4, 14.3_

  - [x] 3.2 Write unit tests for _build_report_data
    - Test with valid summary and reports
    - Test all nested dataclasses properly initialized
    - Test all datasets are anonymized (no CNPJ_FUNDO or DENOM_SOCIAL)
    - Test with empty DataFrames
    - _Requirements: 13.3_

  - [ ] 3.3 Write property test for data consistency
    - **Property 4: Data Consistency**
    - **Validates: Requirements 5.1, 5.4**
    - Test that total_anomalies equals sum of category counts
    - Test that unique_funds_affected <= total_anomalies
    - Use hypothesis to generate varied summary statistics
    - _Requirements: 5.1, 5.4, 13.7_

- [-] 4. Add _get_renderer factory method to PublicReportGenerator
  - [x] 4.1 Implement _get_renderer factory method
    - Accept output_format string parameter
    - Return MarkdownRenderer for "markdown" format
    - Return HtmlRenderer for "html" format
    - Return JsonRenderer for "json" format
    - Raise ValueError with descriptive message for unsupported formats
    - Add docstring with Args, Returns, Raises sections
    - _Requirements: 3.6, 4.4, 14.3_

  - [ ] 4.2 Write unit tests for _get_renderer
    - Test returns correct renderer for each valid format
    - Test raises ValueError for unsupported format
    - Test case-insensitive format matching (optional enhancement)
    - _Requirements: 13.3_

- [ ] 5. Checkpoint - Verify core components
  - Ensure all tests pass, ask the user if questions arise.

- [-] 6. Refactor generate_report method to use new architecture
  - [x] 6.1 Update generate_report method
    - Keep existing load_anomaly_reports and calculate_summary_statistics calls
    - Add call to _build_report_data to construct ReportData
    - Add call to _get_renderer to get appropriate renderer
    - Call renderer.render(report_data) to generate content
    - Keep existing file writing logic (create parent dirs, write UTF-8)
    - Maintain backward compatibility with existing CLI interface
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 6.1, 6.2, 6.3, 6.6_

  - [ ] 6.2 Write integration tests for complete workflow
    - Test generate_report for all three formats
    - Test file creation with valid output path
    - Test stdout output (no file)
    - Test parent directory creation
    - Test file overwriting
    - _Requirements: 13.5_

  - [ ] 6.3 Write property test for anonymization completeness
    - **Property 2: Anonymization Completeness**
    - **Validates: Requirements 2.1, 2.2, 2.3, 10.1, 10.2**
    - Test that all datasets in ReportData have no CNPJ_FUNDO or DENOM_SOCIAL columns
    - Test that non-empty datasets have FUND_ID column
    - Use hypothesis to generate varied report DataFrames
    - _Requirements: 2.1, 2.2, 2.3, 10.1, 10.2, 13.6, 13.8_

- [ ] 7. Enhance anonymize_fund_data method
  - [x] 7.1 Review and document anonymize_fund_data method
    - Verify CNPJ_FUNDO removal logic
    - Verify DENOM_SOCIAL removal logic
    - Verify FUND_ID generation follows pattern "FUND_XXXX"
    - Add comprehensive docstring with Args, Returns sections
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 14.3_

  - [ ] 7.2 Write unit tests for anonymize_fund_data
    - Test CNPJ_FUNDO column removal
    - Test DENOM_SOCIAL column removal
    - Test FUND_ID generation and format
    - Test empty DataFrame handling
    - Test DataFrame without CNPJ_FUNDO
    - _Requirements: 13.3_

  - [ ] 7.3 Write property test for FUND_ID stability
    - **Property 7: FUND_ID Stability**
    - **Validates: Requirements 2.4**
    - Test that same CNPJ always maps to same FUND_ID across multiple calls
    - Use hypothesis to generate DataFrames with repeated CNPJs
    - _Requirements: 2.4, 13.6_

- [-] 8. Add error handling and validation
  - [x] 8.1 Add error handling for missing CSV files
    - Update load_anomaly_reports to return empty DataFrames for missing files
    - Add warning logs for missing files
    - _Requirements: 7.1_

  - [x] 8.2 Add error handling for malformed CSV data
    - Wrap CSV parsing in try/except blocks
    - Return empty DataFrame on parse failure
    - Add error logs with details
    - _Requirements: 7.2_

  - [x] 8.3 Add error handling for file write failures
    - Wrap file write operations in try/except blocks
    - Raise IOError with descriptive message on failure
    - _Requirements: 6.4, 7.4_

  - [x] 8.4 Add validation for summary statistics completeness
    - Check for required keys in summary dict
    - Raise KeyError with missing key name if incomplete
    - _Requirements: 7.5_

  - [-] 8.5 Write unit tests for error handling
    - Test missing CSV file handling
    - Test malformed CSV handling
    - Test file write failure (mock)
    - Test incomplete summary dict
    - _Requirements: 13.3_

- [ ] 9. Checkpoint - Verify error handling and integration
  - Ensure all tests pass, ask the user if questions arise.

- [x] 10. Remove deprecated format-specific methods
  - [x] 10.1 Remove generate_markdown_report method
    - Delete method from PublicReportGenerator class
    - Verify no internal references remain
    - _Requirements: 15.1, 15.2_

  - [x] 10.2 Remove generate_html_report method
    - Delete method from PublicReportGenerator class
    - Verify no internal references remain
    - _Requirements: 15.1, 15.2_

  - [x] 10.3 Remove generate_json_report method
    - Delete method from PublicReportGenerator class
    - Verify no internal references remain
    - _Requirements: 15.1, 15.2_

  - [x] 10.4 Remove _df_to_json_records static method
    - Delete method (functionality moved to JsonRenderer)
    - Verify no internal references remain
    - _Requirements: 15.1, 15.2_

- [-] 11. Update documentation and code quality
  - [x] 11.1 Add module-level docstring
    - Document the refactored architecture
    - Describe ReportData and renderer pattern
    - Include usage examples for all formats
    - _Requirements: 14.4, 14.5_

  - [x] 11.2 Run linters and type checkers
    - Run `ruff check scripts/generate_public_report.py`
    - Run `mypy scripts/generate_public_report.py`
    - Fix any warnings or errors
    - _Requirements: 15.5_

  - [ ] 11.3 Verify test coverage
    - Run `pytest --cov=scripts.generate_public_report tests/`
    - Ensure coverage is at least 90%
    - Add tests for any uncovered branches
    - _Requirements: 13.1, 13.2_

  - [ ] 11.4 Write property test for output format validity
    - **Property 5: Renderer Output Validity**
    - **Validates: Requirements 3.2, 3.3, 3.4**
    - Test that Markdown output has valid syntax
    - Test that HTML output is valid HTML5
    - Test that JSON output can be parsed
    - Use hypothesis to generate varied ReportData instances
    - _Requirements: 3.2, 3.3, 3.4, 13.7_

- [ ] 12. Final checkpoint and validation
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties
- Unit tests validate specific examples and edge cases
- The refactoring eliminates ~200 lines of duplicate logic
- New architecture makes adding formats trivial (~50 lines per renderer)
- All changes maintain backward compatibility with existing CLI interface
