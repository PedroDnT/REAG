"""
Base Analyzer Class

Provides common functionality for all fraud detection analyzers.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Dict, Any
import pandas as pd
from datetime import datetime


class BaseAnalyzer(ABC):
    """
    Abstract base class for all fraud detection analyzers.

    Provides common functionality:
    - Configuration management
    - Report generation
    - Data validation
    - Logging
    """

    def __init__(self, config: Optional[Any] = None):
        """
        Initialize the analyzer.

        Args:
            config: Configuration object (optional)
        """
        self.config = config
        self.name = self.__class__.__name__

    @abstractmethod
    def analyze(self, *args, **kwargs) -> pd.DataFrame:
        """
        Perform the analysis.

        Must be implemented by subclasses.

        Returns:
            DataFrame with analysis results
        """
        raise NotImplementedError(f"{self.name}.analyze() must be implemented")

    def generate_report(
        self,
        results: pd.DataFrame,
        output_path: Optional[Path] = None,
        format: str = 'csv'
    ) -> Optional[Path]:
        """
        Generate and save analysis report.

        Args:
            results: Analysis results DataFrame
            output_path: Path to save report (optional)
            format: Output format ('csv', 'excel', 'json')

        Returns:
            Path to saved report, or None if not saved
        """
        if output_path is None:
            return None

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Save based on format
        if format == 'csv':
            results.to_csv(output_path, index=False)
        elif format == 'excel':
            results.to_excel(output_path, index=False)
        elif format == 'json':
            results.to_json(output_path, orient='records', indent=2)
        else:
            raise ValueError(f"Unsupported format: {format}")

        print(f"✅ Report saved: {output_path}")
        return output_path

    def validate_dataframe(
        self,
        df: pd.DataFrame,
        required_columns: list,
        name: str = "DataFrame"
    ) -> None:
        """
        Validate that a DataFrame has required columns.

        Args:
            df: DataFrame to validate
            required_columns: List of required column names
            name: Name of the DataFrame for error messages

        Raises:
            ValueError: If required columns are missing
        """
        missing = [col for col in required_columns if col not in df.columns]

        if missing:
            raise ValueError(
                f"{name} is missing required columns: {missing}\n"
                f"Available columns: {df.columns.tolist()}"
            )

    def log(self, message: str, level: str = "INFO") -> None:
        """
        Log a message.

        Args:
            message: Message to log
            level: Log level (INFO, WARNING, ERROR)
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        prefix = {
            "INFO": "ℹ️ ",
            "WARNING": "⚠️ ",
            "ERROR": "❌",
            "SUCCESS": "✅"
        }.get(level, "")

        print(f"{prefix}{message}")

    def create_summary_stats(self, df: pd.DataFrame, group_by: Optional[str] = None) -> Dict[str, Any]:
        """
        Create summary statistics for results.

        Args:
            df: Results DataFrame
            group_by: Optional column to group by

        Returns:
            Dictionary with summary statistics
        """
        stats = {
            'total_records': len(df),
            'timestamp': datetime.now().isoformat(),
            'analyzer': self.name
        }

        if group_by and group_by in df.columns:
            stats['breakdown'] = df[group_by].value_counts().to_dict()

        return stats

    def __repr__(self) -> str:
        return f"{self.name}(config={self.config is not None})"
