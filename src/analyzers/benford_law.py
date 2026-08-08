"""
Benford's Law Analyzer for Fraud Detection

Benford's Law states that in many naturally occurring datasets,
the first digit follows a logarithmic distribution:
- 30.1% start with 1
- 17.6% start with 2
- 12.5% start with 3
- ...
- 4.6% start with 9

Fabricated numbers tend to deviate from this distribution.
Successfully used in Enron fraud detection and financial forensics.
"""

import logging

import pandas as pd
import numpy as np
from pathlib import Path
import matplotlib.pyplot as plt

from src.utils.statistics import chi2_cdf

logger = logging.getLogger(__name__)


class BenfordLawAnalyzer:
    """
    Analyzes financial data for compliance with Benford's Law

    Non-compliance suggests possible data manipulation or fabrication.
    """

    # Minimum risk score threshold for including funds in results
    MIN_RISK_SCORE_THRESHOLD = 1.5  # Corresponds to MEDIUM risk level

    # Expected Benford's Law distribution for first digits
    BENFORD_EXPECTED = {
        1: 0.301,  # 30.1%
        2: 0.176,  # 17.6%
        3: 0.125,  # 12.5%
        4: 0.097,  # 9.7%
        5: 0.079,  # 7.9%
        6: 0.067,  # 6.7%
        7: 0.058,  # 5.8%
        8: 0.051,  # 5.1%
        9: 0.046   # 4.6%
    }

    def __init__(self, alpha: float = 0.05):
        """
        Args:
            alpha: Significance level for chi-square test (default: 0.05)
        """
        self.alpha = alpha

    def extract_first_digits(self, values: pd.Series) -> pd.Series:
        """
        Extract first digit from numeric values

        Args:
            values: Series of numeric values

        Returns:
            Series of first digits (1-9)
        """
        # Convert to absolute values and remove zeros/NaN
        values = values.abs().replace(0, np.nan).dropna()

        if len(values) == 0:
            return pd.Series(dtype=int)

        # Use mathematical approach to handle scientific notation correctly
        first_digits = []
        for val in values:
            try:
                # Convert to float to handle large integers
                val_float = float(val)

                # Ensure we have a positive finite number
                if val_float <= 0 or not np.isfinite(val_float):
                    continue

                # Get the first digit by normalizing to [1, 10)
                # Find power of 10: 10^n <= val < 10^(n+1)
                if val_float >= 1:
                    # For values >= 1, divide by powers of 10 until in [1, 10)
                    normalized = val_float
                    while normalized >= 10:
                        normalized /= 10
                else:
                    # For values < 1, multiply by powers of 10 until in [1, 10)
                    normalized = val_float
                    while normalized < 1:
                        normalized *= 10

                # First digit is the integer part of the normalized value
                first_digit = int(normalized)
                if 1 <= first_digit <= 9:
                    first_digits.append(first_digit)
            except (ValueError, TypeError, OverflowError):
                # Skip values that can't be converted
                continue

        return pd.Series(first_digits)

    def calculate_observed_distribution(self, first_digits: pd.Series) -> dict[int, float]:
        """
        Calculate observed distribution of first digits

        Args:
            first_digits: Series of first digits (1-9)

        Returns:
            Dictionary mapping digit to observed proportion
        """
        if len(first_digits) == 0:
            return {}

        counts = first_digits.value_counts()
        total = len(first_digits)

        observed = {}
        for digit in range(1, 10):
            observed[digit] = counts.get(digit, 0) / total

        return observed

    def chi_square_test(self, observed: dict[int, float],
                       sample_size: int) -> tuple[float, float, bool]:
        """
        Perform chi-square goodness-of-fit test

        Args:
            observed: Observed distribution
            sample_size: Number of observations

        Returns:
            Tuple of (chi_square_statistic, p_value, is_significant)
        """
        if sample_size < 30:
            # Not enough data for meaningful test
            return 0.0, 1.0, False

        # Calculate chi-square statistic
        chi_square = 0.0
        for digit in range(1, 10):
            expected = self.BENFORD_EXPECTED[digit]
            obs = observed.get(digit, 0)

            expected_count = expected * sample_size
            observed_count = obs * sample_size

            # Calculate chi-square component
            # Note: expected_count is always > 0 for Benford distribution
            chi_square += ((observed_count - expected_count) ** 2) / expected_count

        # Degrees of freedom = 9 digits - 1
        df = 8

        # Calculate p-value using our chi2_cdf implementation
        p_value = 1 - chi2_cdf(chi_square, df)

        # Test significance
        is_significant = p_value < self.alpha

        return chi_square, p_value, is_significant

    def mean_absolute_deviation(self, observed: dict[int, float]) -> float:
        """
        Calculate Mean Absolute Deviation (MAD) from Benford's Law

        MAD is easier to interpret than chi-square:
        - MAD < 0.006: Close conformity
        - 0.006 <= MAD < 0.012: Acceptable conformity
        - 0.012 <= MAD < 0.015: Marginally acceptable
        - MAD >= 0.015: Nonconformity

        Args:
            observed: Observed distribution

        Returns:
            Mean absolute deviation
        """
        deviations = []
        for digit in range(1, 10):
            expected = self.BENFORD_EXPECTED[digit]
            obs = observed.get(digit, 0)
            deviations.append(abs(obs - expected))

        return np.mean(deviations)

    def analyze_series(self, values: pd.Series,
                      series_name: str = "Values") -> dict:
        """
        Analyze a series of values for Benford's Law compliance

        Args:
            values: Series of numeric values to analyze
            series_name: Name for reporting

        Returns:
            Dictionary with analysis results
        """
        # Extract first digits
        first_digits = self.extract_first_digits(values)
        sample_size = len(first_digits)

        if sample_size == 0:
            return {
                'series_name': series_name,
                'sample_size': 0,
                'error': 'No valid values to analyze'
            }

        # Calculate observed distribution
        observed = self.calculate_observed_distribution(first_digits)

        # Perform chi-square test
        chi_square, p_value, is_significant = self.chi_square_test(observed, sample_size)

        # Calculate MAD
        mad = self.mean_absolute_deviation(observed)

        # Determine conformity level
        if mad < 0.006:
            conformity = "CLOSE_CONFORMITY"
            fraud_risk = "LOW"
        elif mad < 0.012:
            conformity = "ACCEPTABLE_CONFORMITY"
            fraud_risk = "LOW"
        elif mad < 0.015:
            conformity = "MARGINALLY_ACCEPTABLE"
            fraud_risk = "MEDIUM"
        else:
            conformity = "NONCONFORMITY"
            fraud_risk = "HIGH"

        # Increase fraud risk if chi-square test is significant
        if is_significant:
            if fraud_risk == "LOW":
                fraud_risk = "MEDIUM"
            elif fraud_risk == "MEDIUM":
                fraud_risk = "HIGH"
            elif fraud_risk == "HIGH":
                fraud_risk = "CRITICAL"

        return {
            'series_name': series_name,
            'sample_size': sample_size,
            'chi_square': chi_square,
            'p_value': p_value,
            'is_significant': is_significant,
            'mad': mad,
            'conformity': conformity,
            'fraud_risk': fraud_risk,
            'observed_distribution': observed,
            'expected_distribution': self.BENFORD_EXPECTED
        }

    def analyze_fund_data(self, informe_df: pd.DataFrame,
                         cda_df: pd.DataFrame | None = None) -> pd.DataFrame:
        """
        Analyze fund data for Benford's Law compliance

        Tests multiple financial series:
        - Patrimônio Líquido (PL)
        - Valor da Quota
        - Captação/Resgate
        - Portfolio values (if CDA provided)

        Args:
            informe_df: Informe diário dataframe
            cda_df: Optional CDA dataframe

        Returns:
            DataFrame with analysis results per fund
        """
        logger.info("Analyzing funds for Benford's Law compliance...")

        results = []

        # Analyze by fund
        for fund_cnpj in informe_df['CNPJ_FUNDO'].unique():
            fund_data = informe_df[informe_df['CNPJ_FUNDO'] == fund_cnpj]

            fund_results = {
                'fund_cnpj': fund_cnpj
            }

            # Test PL (Patrimônio Líquido)
            if 'VL_PATRIM_LIQ' in fund_data.columns:
                pl_analysis = self.analyze_series(
                    fund_data['VL_PATRIM_LIQ'],
                    f"PL_{fund_cnpj}"
                )
                fund_results['pl_mad'] = pl_analysis.get('mad', 0)
                fund_results['pl_p_value'] = pl_analysis.get('p_value', 1)
                fund_results['pl_fraud_risk'] = pl_analysis.get('fraud_risk', 'UNKNOWN')
                fund_results['pl_sample_size'] = pl_analysis.get('sample_size', 0)

            # Test Quota Value
            if 'VL_QUOTA' in fund_data.columns:
                quota_analysis = self.analyze_series(
                    fund_data['VL_QUOTA'],
                    f"QUOTA_{fund_cnpj}"
                )
                fund_results['quota_mad'] = quota_analysis.get('mad', 0)
                fund_results['quota_p_value'] = quota_analysis.get('p_value', 1)
                fund_results['quota_fraud_risk'] = quota_analysis.get('fraud_risk', 'UNKNOWN')

            # Test Captação
            if 'CAPTC_DIA' in fund_data.columns:
                captc_analysis = self.analyze_series(
                    fund_data['CAPTC_DIA'],
                    f"CAPTC_{fund_cnpj}"
                )
                fund_results['captc_mad'] = captc_analysis.get('mad', 0)
                fund_results['captc_fraud_risk'] = captc_analysis.get('fraud_risk', 'UNKNOWN')

            # Test Resgate
            if 'RESG_DIA' in fund_data.columns:
                resg_analysis = self.analyze_series(
                    fund_data['RESG_DIA'],
                    f"RESG_{fund_cnpj}"
                )
                fund_results['resg_mad'] = resg_analysis.get('mad', 0)
                fund_results['resg_fraud_risk'] = resg_analysis.get('fraud_risk', 'UNKNOWN')

            # Calculate overall fraud risk score
            risk_scores = {
                'LOW': 1,
                'MEDIUM': 2,
                'HIGH': 3,
                'CRITICAL': 4,
                'UNKNOWN': 0
            }

            risks = [
                fund_results.get('pl_fraud_risk', 'UNKNOWN'),
                fund_results.get('quota_fraud_risk', 'UNKNOWN'),
                fund_results.get('captc_fraud_risk', 'UNKNOWN'),
                fund_results.get('resg_fraud_risk', 'UNKNOWN')
            ]

            risk_values = [risk_scores.get(r, 0) for r in risks]
            avg_risk_score = np.mean([r for r in risk_values if r > 0]) if any(r > 0 for r in risk_values) else 0

            if avg_risk_score >= 3:
                fund_results['overall_fraud_risk'] = 'CRITICAL'
            elif avg_risk_score >= 2.5:
                fund_results['overall_fraud_risk'] = 'HIGH'
            elif avg_risk_score >= 1.5:
                fund_results['overall_fraud_risk'] = 'MEDIUM'
            else:
                fund_results['overall_fraud_risk'] = 'LOW'

            # Only include funds with at least MEDIUM risk
            if avg_risk_score >= self.MIN_RISK_SCORE_THRESHOLD:
                results.append(fund_results)

        result_df = pd.DataFrame(results)

        if not result_df.empty:
            result_df = result_df.sort_values('overall_fraud_risk',
                                             key=lambda x: x.map(risk_scores),
                                             ascending=False)
            logger.warning(f"{len(result_df)} funds show Benford's Law anomalies")
            logger.info(f"Risk breakdown:\n{result_df['overall_fraud_risk'].value_counts()}")
        else:
            logger.info("All funds conform to Benford's Law")

        return result_df

    def plot_distribution(self, observed: dict[int, float],
                         title: str = "Benford's Law Analysis",
                         save_path: Path | None = None):
        """
        Plot observed vs expected distribution

        Args:
            observed: Observed distribution
            title: Plot title
            save_path: Optional path to save plot
        """
        digits = list(range(1, 10))
        expected = [self.BENFORD_EXPECTED[d] for d in digits]
        obs = [observed.get(d, 0) for d in digits]

        fig, ax = plt.subplots(figsize=(10, 6))

        x = np.arange(len(digits))
        width = 0.35

        ax.bar(x - width/2, expected, width, label='Benford Expected', alpha=0.8)
        ax.bar(x + width/2, obs, width, label='Observed', alpha=0.8)

        ax.set_xlabel('First Digit')
        ax.set_ylabel('Proportion')
        ax.set_title(title)
        ax.set_xticks(x)
        ax.set_xticklabels(digits)
        ax.legend()
        ax.grid(True, alpha=0.3)

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            logger.info(f"Plot saved to {save_path}")

        return fig

    def generate_report(self, informe_df: pd.DataFrame,
                       cda_df: pd.DataFrame | None = None,
                       output_dir: Path | None = None) -> dict:
        """
        Generate comprehensive Benford's Law report

        Args:
            informe_df: Informe diário dataframe
            cda_df: Optional CDA dataframe
            output_dir: Optional directory to save reports

        Returns:
            Dictionary with report data
        """
        logger.info("=" * 70)
        logger.info("BENFORD'S LAW FRAUD DETECTION REPORT")
        logger.info("=" * 70)

        # Analyze all funds
        fund_results = self.analyze_fund_data(informe_df, cda_df)

        # Save results
        if output_dir and not fund_results.empty:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)

            results_path = output_dir / 'benford_law_analysis.csv'
            fund_results.to_csv(results_path, index=False)
            logger.info(f"Results saved to {results_path}")

        # Summary statistics
        summary = {
            'total_funds_analyzed': len(informe_df['CNPJ_FUNDO'].unique()),
            'funds_with_anomalies': len(fund_results),
            'critical_risk_funds': len(fund_results[fund_results['overall_fraud_risk'] == 'CRITICAL']),
            'high_risk_funds': len(fund_results[fund_results['overall_fraud_risk'] == 'HIGH']),
            'medium_risk_funds': len(fund_results[fund_results['overall_fraud_risk'] == 'MEDIUM'])
        }

        logger.info("=" * 70)
        logger.info("SUMMARY")
        logger.info("=" * 70)
        logger.info(f"Total funds analyzed: {summary['total_funds_analyzed']}")
        logger.info(f"Funds with anomalies: {summary['funds_with_anomalies']}")
        logger.info(f"  - CRITICAL risk: {summary['critical_risk_funds']}")
        logger.info(f"  - HIGH risk: {summary['high_risk_funds']}")
        logger.info(f"  - MEDIUM risk: {summary['medium_risk_funds']}")

        if summary['critical_risk_funds'] > 0:
            logger.warning("CRITICAL: Some funds show strong evidence of number fabrication!")
            logger.warning("   Recommend immediate investigation.")

        return {
            'summary': summary,
            'detailed_results': fund_results
        }
