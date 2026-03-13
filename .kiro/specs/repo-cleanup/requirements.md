# Requirements Document: Repository Cleanup

## Introduction

This document specifies the requirements for a repository cleanup feature that systematically removes test files and intermediate documentation from the REAG fraud investigation repository while preserving essential code, notebooks, scripts, and core documentation. The feature must ensure safe, reversible cleanup operations with comprehensive validation to prevent accidental loss of critical files.

## Glossary

- **Repository**: The REAG fraud investigation git repository containing source code, notebooks, scripts, and documentation
- **Essential_File**: A file critical to repository functionality including source code, core documentation, configuration files, and data analysis notebooks
- **Test_File**: A Python file used for testing purposes, identified by naming patterns like test_*.py or *_test.py
- **Intermediate_Doc**: Documentation files created during development that are not part of the final documentation set (e.g., *_SUMMARY.md, *_IMPROVEMENTS.md)
- **Backup_Archive**: A compressed archive containing copies of files before deletion, enabling restoration if needed
- **Validation**: The process of verifying repository integrity after cleanup by checking essential files exist and Python imports work
- **Dry_Run**: A preview mode that shows what would be deleted without actually removing files
- **Cleanup_Orchestrator**: The main system component that coordinates the cleanup workflow
- **File_Classifier**: The component that categorizes repository files into essential, test, and intermediate documentation
- **Backup_Manager**: The component that creates and manages backup archives
- **Deletion_Engine**: The component that safely removes classified files
- **Validation_Engine**: The component that verifies repository integrity after cleanup

## Requirements

### Requirement 1: File Classification

**User Story:** As a developer, I want the system to automatically classify repository files, so that I can identify which files are safe to remove without manual inspection of every file.

#### Acceptance Criteria

1. WHEN the system scans the repository, THE File_Classifier SHALL categorize every file into exactly one classification category
2. THE File_Classifier SHALL identify test files by matching patterns including test_*.py, *_test.py, run_test.py, run_error_tests.py, and verify_*.py
3. THE File_Classifier SHALL identify intermediate documentation by matching patterns including *_SUMMARY.md, *_IMPROVEMENTS.md, *_COMPLETE.md, *_RESULTS.md, IMPLEMENTATION_PLAN.md, and IMPROVEMENT_RECOMMENDATIONS.md
4. THE File_Classifier SHALL protect essential files including README.md, USER_GUIDE.md, AGENTS.md, docs/ARCHITECTURE.md, all files in src/, notebooks/, scripts/, and configuration files
5. THE File_Classifier SHALL classify files in docs/legacy/ as legacy documentation
6. WHEN a file does not match any classification pattern, THE File_Classifier SHALL mark it as unknown for manual review
7. THE File_Classifier SHALL generate a human-readable classification report showing file counts and sizes for each category

### Requirement 2: Cleanup Planning

**User Story:** As a developer, I want to preview the cleanup plan before execution, so that I can verify the correct files will be deleted and understand the impact.

#### Acceptance Criteria

1. WHEN the system generates a cleanup plan, THE Cleanup_Orchestrator SHALL display the number of files to be deleted in each category
2. WHEN the system generates a cleanup plan, THE Cleanup_Orchestrator SHALL calculate and display the estimated disk space to be freed
3. THE Cleanup_Orchestrator SHALL provide a dry-run mode that shows what would be deleted without actually removing files
4. WHEN dry-run mode is enabled, THE Cleanup_Orchestrator SHALL generate a complete cleanup plan without modifying any files
5. THE Cleanup_Orchestrator SHALL display the list of files to be deleted grouped by classification category
6. WHEN the cleanup plan is displayed, THE Cleanup_Orchestrator SHALL prompt for user confirmation before proceeding with actual deletion

### Requirement 3: Backup Creation

**User Story:** As a developer, I want automatic backups created before deletion, so that I can recover files if the cleanup removes something important.

#### Acceptance Criteria

1. WHEN files are marked for deletion, THE Backup_Manager SHALL create a compressed backup archive before any files are deleted
2. THE Backup_Manager SHALL generate a timestamped backup filename in the format cleanup_backup_TIMESTAMP.tar.gz
3. THE Backup_Manager SHALL create a manifest file containing metadata for each backed-up file including path, size, SHA256 hash, and modification time
4. THE Backup_Manager SHALL store the backup archive and manifest in a designated backup directory
5. IF backup creation fails, THEN THE Cleanup_Orchestrator SHALL abort the cleanup operation without deleting any files
6. THE Backup_Manager SHALL verify that all files marked for deletion are included in the backup archive
7. THE Backup_Manager SHALL calculate and record the total size of the backup archive

### Requirement 4: Safe File Deletion

**User Story:** As a developer, I want files deleted safely with error handling, so that partial failures don't leave the repository in an inconsistent state.

#### Acceptance Criteria

1. WHEN executing file deletion, THE Deletion_Engine SHALL delete only files that have been backed up successfully
2. THE Deletion_Engine SHALL track each deletion operation and record success or failure with error messages
3. WHEN a file deletion fails, THE Deletion_Engine SHALL continue with remaining deletions and report all failures at the end
4. THE Deletion_Engine SHALL remove empty parent directories after deleting files
5. THE Deletion_Engine SHALL not delete any file classified as essential
6. WHEN dry-run mode is enabled, THE Deletion_Engine SHALL not delete any files but SHALL return a preview of deletion operations
7. THE Deletion_Engine SHALL calculate and report the actual disk space freed after deletion

### Requirement 5: Repository Validation

**User Story:** As a developer, I want automatic validation after cleanup, so that I can be confident the repository still functions correctly.

#### Acceptance Criteria

1. WHEN file deletion completes, THE Validation_Engine SHALL verify that all essential files still exist
2. THE Validation_Engine SHALL check that essential directories including src/, notebooks/, scripts/, and config/ still exist
3. THE Validation_Engine SHALL validate that Python imports for modules in src/ still work correctly
4. THE Validation_Engine SHALL verify git repository integrity using git status checks
5. WHEN any validation check fails, THE Validation_Engine SHALL report specific error messages indicating which check failed
6. THE Validation_Engine SHALL generate a validation report listing all checks performed and their pass/fail status
7. IF validation fails, THEN THE Cleanup_Orchestrator SHALL mark the cleanup operation as failed

### Requirement 6: Automatic Rollback

**User Story:** As a developer, I want automatic restoration from backup if validation fails, so that the repository is never left in a broken state.

#### Acceptance Criteria

1. WHEN validation fails after cleanup, THE Cleanup_Orchestrator SHALL automatically initiate restoration from the backup archive
2. THE Backup_Manager SHALL restore all files from the backup archive to their original locations
3. WHEN restoration completes, THE Cleanup_Orchestrator SHALL verify that the repository has been returned to its pre-cleanup state
4. THE Cleanup_Orchestrator SHALL display a message indicating that validation failed and the repository was restored
5. WHEN restoration is triggered, THE Backup_Manager SHALL preserve the backup archive for future reference
6. IF restoration fails, THEN THE Cleanup_Orchestrator SHALL report the error and provide the backup archive location for manual recovery

### Requirement 7: Cleanup Summary and Reporting

**User Story:** As a developer, I want a detailed summary after cleanup, so that I can understand what was changed and verify the operation completed successfully.

#### Acceptance Criteria

1. WHEN cleanup completes successfully, THE Cleanup_Orchestrator SHALL display the number of files deleted
2. WHEN cleanup completes successfully, THE Cleanup_Orchestrator SHALL display the amount of disk space freed
3. THE Cleanup_Orchestrator SHALL display the backup archive location
4. WHEN cleanup completes, THE Cleanup_Orchestrator SHALL display the validation status
5. IF any files failed to delete, THEN THE Cleanup_Orchestrator SHALL list those files with error messages
6. THE Cleanup_Orchestrator SHALL generate a cleanup summary including timestamp, files deleted, space freed, and validation result
7. WHEN cleanup is cancelled by the user, THE Cleanup_Orchestrator SHALL exit without making any changes and display a cancellation message

### Requirement 8: Backup Management

**User Story:** As a developer, I want to manage backup archives, so that I can restore from backups or clean up old backups to free disk space.

#### Acceptance Criteria

1. THE Backup_Manager SHALL provide functionality to list all available backup archives with their timestamps and sizes
2. THE Backup_Manager SHALL provide functionality to restore the repository from a specified backup archive
3. WHEN restoring from backup, THE Backup_Manager SHALL extract all files from the archive to their original locations
4. THE Backup_Manager SHALL verify backup archive integrity before restoration
5. THE Backup_Manager SHALL implement automatic cleanup of old backups keeping the most recent 5 backups by default
6. WHERE backup retention is configured, THE Backup_Manager SHALL respect the configured retention policy
7. THE Backup_Manager SHALL provide functionality to manually delete specific backup archives

### Requirement 9: Error Handling and Recovery

**User Story:** As a developer, I want comprehensive error handling, so that I understand what went wrong and can take appropriate action.

#### Acceptance Criteria

1. WHEN insufficient disk space is available for backup, THE Backup_Manager SHALL abort the operation and display disk space requirements
2. WHEN permission is denied for file operations, THE Cleanup_Orchestrator SHALL report the specific files with permission issues
3. WHEN git repository corruption is detected, THE Validation_Engine SHALL report the corruption and THE Cleanup_Orchestrator SHALL restore from backup
4. WHEN a file is locked by another process, THE Deletion_Engine SHALL report the locked file and continue with other deletions
5. IF the user cancels the operation during confirmation, THEN THE Cleanup_Orchestrator SHALL exit gracefully without any changes
6. THE Cleanup_Orchestrator SHALL log all errors with timestamps and context for troubleshooting
7. WHEN any error occurs, THE Cleanup_Orchestrator SHALL provide actionable guidance for resolution

### Requirement 10: Performance and Efficiency

**User Story:** As a developer, I want the cleanup operation to complete quickly, so that I can continue working without long delays.

#### Acceptance Criteria

1. WHEN scanning a repository with 1000 files, THE File_Classifier SHALL complete the scan within 1 second
2. WHEN creating a backup of 100MB of files, THE Backup_Manager SHALL complete within 5 seconds
3. WHEN deleting 100 files, THE Deletion_Engine SHALL complete within 1 second
4. WHEN validating the repository, THE Validation_Engine SHALL complete all checks within 2 seconds
5. THE Backup_Manager SHALL use streaming for large files to avoid loading entire files into memory
6. THE File_Classifier SHALL use efficient directory traversal methods to minimize filesystem operations
7. THE Backup_Manager SHALL use compression level 6 for gzip to balance speed and archive size

### Requirement 11: Security and Safety

**User Story:** As a developer, I want security safeguards in place, so that the cleanup operation cannot be exploited or cause unintended damage.

#### Acceptance Criteria

1. THE File_Classifier SHALL validate that all file paths are within the repository root directory
2. THE File_Classifier SHALL reject any file path containing ".." components to prevent path traversal attacks
3. THE Cleanup_Orchestrator SHALL verify write permissions before attempting any file operations
4. THE Cleanup_Orchestrator SHALL default to dry-run mode to prevent accidental deletions
5. THE Cleanup_Orchestrator SHALL maintain an audit log of all file deletions with timestamps
6. WHERE backup archives contain sensitive data, THE Backup_Manager SHALL support encryption of backup archives
7. THE Backup_Manager SHALL implement automatic cleanup of old backups to prevent unlimited disk space consumption
