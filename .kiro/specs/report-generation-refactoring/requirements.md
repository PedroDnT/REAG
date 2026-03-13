# Requirements Document: Report Generation Refactoring

## Introduction

This document specifies the requirements for refactoring the report generation system in the REAG fraud investigation project. The current system contains approximately 200 lines of duplicate logic across format renderers (Markdown, HTML, JSON), where each format method independently rebuilds report sections and anonymizes data. The refactored system will introduce a unified data structure that captures report content once, then delegates to format-specific renderers, improving maintainability, testability, and extensibility.

## Glossary

- **Report_Generator**: The PublicReportGenerator class responsible for orchestrating report generation
- **Report_Data**: Immutable dataclass containing all report sections and metadata
- **Renderer**: Format-specific component that transforms ReportData into target format (Markdown, HTML, JSON)
- **Anonymization**: Process of replacing personally identifiable information (CNPJ_FUNDO, DENOM_SOCIAL) with stable anonymous identifiers (FUND_ID)
- **Anomaly_Report**: CSV file containing detected anomalies from the investigation pipeline
- **CNPJ**: Brazilian tax identification number for legal entities (personally identifiable information)
- **FUND_ID**: Anonymized fund identifier in format "FUND_XXXX" where X is a digit

## Requirements

### Requirement 1: Unified Data Structure

**User Story:** As a developer, I want a single data structure that captures all report content, so that I can eliminate duplicate data preparation logic across format renderers.

#### Acceptance Criteria

1. THE Report_Generator SHALL create a ReportData dataclass containing all report sections
2. THE ReportData dataclass SHALL be immutable (frozen=True)
3. THE ReportData dataclass SHALL contain metadata, executive_summary, detailed_findings, severity_distribution, datasets, methodology_text, and disclaimer_text fields
4. WHEN ReportData is constructed, THE Report_Generator SHALL populate all nested dataclass instances
5. THE ReportData structure SHALL be type-safe with explicit type annotations for all fields

### Requirement 2: Data Anonymization

**User Story:** As a compliance officer, I want all personally identifiable information removed from reports, so that we can publish findings without privacy violations.

#### Acceptance Criteria

1. WHEN anonymizing fund data, THE Report_Generator SHALL remove CNPJ_FUNDO columns from all dataframes
2. WHEN anonymizing fund data, THE Report_Generator SHALL remove DENOM_SOCIAL columns from all dataframes
3. WHEN anonymizing fund data, THE Report_Generator SHALL replace CNPJ values with stable FUND_ID identifiers
4. FOR ALL dataframes containing the same CNPJ value, THE Report_Generator SHALL map that CNPJ to the same FUND_ID
5. THE FUND_ID format SHALL match the pattern "FUND_XXXX" where X is a digit
6. WHEN a dataframe is empty, THE Report_Generator SHALL return an empty dataframe without errors
7. WHEN a dataframe does not contain CNPJ_FUNDO, THE Report_Generator SHALL return a copy of the original dataframe

### Requirement 3: Format-Specific Rendering

**User Story:** As a data analyst, I want to generate reports in multiple formats (Markdown, HTML, JSON), so that I can use the format most appropriate for my workflow.

#### Acceptance Criteria

1. THE Report_Generator SHALL support markdown, html, and json output formats
2. WHEN rendering to Markdown, THE Renderer SHALL produce valid Markdown syntax
3. WHEN rendering to HTML, THE Renderer SHALL produce valid HTML5 with embedded CSS
4. WHEN rendering to JSON, THE Renderer SHALL produce valid JSON that can be parsed
5. FOR ALL supported formats, THE Renderer SHALL include all report sections (metadata, executive summary, detailed findings, severity distribution, methodology, disclaimer)
6. WHEN an unsupported format is requested, THE Report_Generator SHALL raise a ValueError with a descriptive message

### Requirement 4: Renderer Interface

**User Story:** As a developer, I want a common interface for all renderers, so that adding new formats is straightforward and consistent.

#### Acceptance Criteria

1. THE system SHALL define a ReportRenderer abstract base class
2. THE ReportRenderer SHALL declare an abstract render method accepting ReportData and returning a string
3. WHEN implementing a new renderer, THE developer SHALL inherit from ReportRenderer
4. THE Report_Generator SHALL use a factory method to instantiate the appropriate renderer based on format
5. FOR ALL renderers, calling render with the same ReportData SHALL produce identical output (determinism)

### Requirement 5: Report Content Consistency

**User Story:** As a quality assurance analyst, I want report metrics to be internally consistent, so that I can trust the accuracy of the data.

#### Acceptance Criteria

1. THE total_anomalies count SHALL equal the sum of flow_anomalies_count, pl_drops_count, runs_count, and divergences_count
2. THE unique_funds_affected count SHALL be less than or equal to total_anomalies
3. THE sum of severity_distribution (high + medium + low) SHALL not exceed total_anomalies
4. WHEN a report is generated, THE Report_Generator SHALL validate consistency between executive_summary and detailed_findings
5. FOR ALL numeric metrics, THE values SHALL be non-negative integers

### Requirement 6: File Output Management

**User Story:** As a user, I want to optionally save reports to files, so that I can persist results for later analysis.

#### Acceptance Criteria

1. WHEN an output_file path is provided, THE Report_Generator SHALL write the report content to that file
2. WHEN the output_file parent directory does not exist, THE Report_Generator SHALL create it
3. WHEN an output_file already exists, THE Report_Generator SHALL overwrite it
4. WHEN file writing fails due to permissions or disk space, THE Report_Generator SHALL raise an IOError with a descriptive message
5. WHEN no output_file is provided, THE Report_Generator SHALL return the report content as a string without writing to disk
6. THE Report_Generator SHALL use UTF-8 encoding for all file writes

### Requirement 7: Error Handling and Recovery

**User Story:** As a system operator, I want graceful error handling, so that partial data issues don't crash the entire report generation process.

#### Acceptance Criteria

1. WHEN an expected anomaly CSV file is missing, THE Report_Generator SHALL return an empty DataFrame for that file and log a warning
2. WHEN a CSV file cannot be parsed, THE Report_Generator SHALL return an empty DataFrame for that file and log an error
3. WHEN anonymization encounters unexpected data types, THE Report_Generator SHALL attempt string conversion and log a warning
4. IF string conversion fails during anonymization, THEN THE Report_Generator SHALL use an empty DataFrame and log an error
5. WHEN calculate_summary_statistics returns an incomplete dictionary, THE Report_Generator SHALL raise a KeyError with the missing key name

### Requirement 8: Performance Requirements

**User Story:** As a user, I want fast report generation, so that I can iterate quickly during analysis.

#### Acceptance Criteria

1. WHEN generating a report with 5000 anomaly records, THE Report_Generator SHALL complete in less than 200 milliseconds
2. WHEN generating a report with 5000 anomaly records, THE Report_Generator SHALL use less than 150 MB of memory
3. WHEN anonymizing 1000 unique CNPJs, THE Report_Generator SHALL complete in less than 50 milliseconds
4. THE Report_Generator SHALL build ReportData only once per report generation, regardless of output format
5. THE Report_Generator SHALL anonymize each dataframe at most once per report generation

### Requirement 9: Renderer Immutability

**User Story:** As a developer, I want renderers to have no side effects, so that I can safely reuse data structures and reason about code behavior.

#### Acceptance Criteria

1. WHEN a Renderer processes ReportData, THE Renderer SHALL not modify the input data
2. FOR ALL ReportData instances, calling render multiple times SHALL produce identical output
3. THE ReportData dataclass SHALL be frozen to prevent accidental mutation
4. FOR ALL nested dataclasses within ReportData, THE dataclasses SHALL be frozen
5. WHEN rendering completes, THE original ReportData instance SHALL be unchanged

### Requirement 10: Security and Privacy

**User Story:** As a compliance officer, I want strong guarantees that no PII appears in output, so that we meet regulatory requirements.

#### Acceptance Criteria

1. FOR ALL generated reports, THE output SHALL not contain CNPJ_FUNDO values
2. FOR ALL generated reports, THE output SHALL not contain DENOM_SOCIAL values
3. WHEN error messages are generated, THE Report_Generator SHALL not include PII in error text
4. WHEN logging operations, THE Report_Generator SHALL not log CNPJ or DENOM_SOCIAL values
5. THE anonymization process SHALL be applied before any rendering occurs

### Requirement 11: Extensibility

**User Story:** As a developer, I want to easily add new output formats, so that the system can adapt to future requirements.

#### Acceptance Criteria

1. WHEN adding a new output format, THE developer SHALL implement a new Renderer class in approximately 50 lines of code
2. WHEN adding a new output format, THE developer SHALL not modify existing Renderer implementations
3. WHEN adding a new output format, THE developer SHALL only modify the factory method to register the new format
4. THE ReportData structure SHALL contain all information needed by any reasonable output format
5. WHEN a new Renderer is added, THE existing test suite SHALL continue to pass without modification

### Requirement 12: Backward Compatibility During Migration

**User Story:** As a system operator, I want zero downtime during the refactoring, so that report generation remains available throughout the migration.

#### Acceptance Criteria

1. DURING migration Phase 1, THE existing generate_markdown_report, generate_html_report, and generate_json_report methods SHALL remain functional
2. DURING migration Phase 2, THE Report_Generator SHALL support both old and new implementations via a feature flag
3. WHEN the feature flag is set to use the old implementation, THE output SHALL be identical to the pre-refactoring behavior
4. WHEN the feature flag is set to use the new implementation, THE output SHALL be equivalent to the old implementation
5. THE migration SHALL provide a rollback mechanism that can be activated in less than 5 minutes

### Requirement 13: Testing and Validation

**User Story:** As a quality assurance engineer, I want comprehensive test coverage, so that I can verify correctness and catch regressions.

#### Acceptance Criteria

1. THE new code SHALL achieve at least 90% line coverage
2. THE new code SHALL achieve 100% branch coverage for critical paths (anonymization, rendering)
3. THE test suite SHALL include unit tests for all dataclass constructors
4. THE test suite SHALL include unit tests for all Renderer implementations
5. THE test suite SHALL include integration tests for the complete report generation workflow
6. THE test suite SHALL include property-based tests for anonymization idempotence
7. THE test suite SHALL include property-based tests for renderer determinism
8. THE test suite SHALL include tests verifying no PII in output

### Requirement 14: Documentation

**User Story:** As a new developer, I want clear documentation, so that I can understand and extend the system.

#### Acceptance Criteria

1. THE ReportData dataclass SHALL have docstrings describing each field
2. THE ReportRenderer abstract class SHALL have docstrings describing the interface contract
3. FOR ALL public methods, THE Report_Generator SHALL have docstrings with Args, Returns, and Raises sections
4. THE design document SHALL include architecture diagrams showing component relationships
5. THE design document SHALL include example usage for all supported formats

### Requirement 15: Code Quality and Maintainability

**User Story:** As a maintainer, I want clean, readable code, so that future modifications are straightforward.

#### Acceptance Criteria

1. THE refactoring SHALL eliminate at least 200 lines of duplicate logic
2. THE Report_Generator SHALL have a single method (_build_report_data) responsible for data preparation
3. FOR ALL format-specific logic, THE code SHALL be isolated in Renderer classes
4. THE code SHALL follow Python type hinting best practices with explicit type annotations
5. THE code SHALL pass all configured linters (ruff, mypy) without warnings
