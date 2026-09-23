# Copyright 2022-2026 ETSI SDG TeraFlowSDN (TFS) (https://tfs.etsi.org/)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
AI Model Processor module.
Provides AI/ML processing functionality for SLA analysis.
"""

import logging
from datetime import datetime, timezone
from random import Random
from typing import Any, Dict, Optional, TYPE_CHECKING

import pandas as pd
from statsmodels.tsa.holtwinters import ExponentialSmoothing

if TYPE_CHECKING:
    from ..clients.influxdb_fetcher import InfluxDBFetcher

LOGGER = logging.getLogger(__name__)


class AIModelProcessor:
    """
    Processes data through AI models for SLA analysis.

    This class implements the AI/ML processing logic to analyze device
    and performance data against SLA policies, detecting violations and
    generating recommendations.
    """

    def __init__(self, influx_fetcher: Optional['InfluxDBFetcher'] = None) -> None:
        """
        Initialize the AIModelProcessor.

        Args:
            influx_fetcher: InfluxDBFetcher instance for writing predicted telemetry.
                           If None, predicted telemetry will not be written to DB.

        Loads AI models and prepares the processor for data analysis.
        """
        LOGGER.info("AIModelProcessor initialized")
        self._influx_fetcher = influx_fetcher
        # TODO: Load AI/ML models here
        # Example: self.model = load_model('sla_violation_detector.h5')


    def ai_model_processor(
        self,
        metric_values: list[dict[str, Any]],
    ) -> Optional[list[dict[str, Any]]]:
        """
        Process device and performance data through AI models.

        Args:
            metric_values: List of dictionaries containing performance metric values.
                Each dict has keys like 'bandwidth_utilization', 'latency', etc.
        Returns:
            List of dicts containing forecasted values for each metric, 
            or None if insufficient data.

        """
        LOGGER.debug("Processing data through AI models")
        LOGGER.debug(f"Number of performance data points: {len(metric_values)}")

        if not metric_values or len(metric_values) < 3:
            LOGGER.warning("Insufficient data for forecasting (need at least 3 samples)")
            return None

        results = []

        try:
            # Convert list of dicts to DataFrame for easier processing
            df = pd.DataFrame(metric_values)
            
            # Process each metric column separately
            for column in df.columns:
                data = df[column]
                
                # Skip non-numeric columns
                if not pd.api.types.is_numeric_dtype(data):
                    LOGGER.debug(f"Skipping non-numeric column: {column}")
                    continue
                
                # Remove NaN values
                data = data.dropna()
                
                if len(data) < 3:
                    LOGGER.warning(f"Insufficient data for column {column} (need at least 3 samples)")
                    continue
                
                LOGGER.debug(f"Processing column: {column} with {len(data)} samples")
                
                # Create and fit Exponential Smoothing model
                model = ExponentialSmoothing(
                    endog    = data,
                    trend    = "add",
                    seasonal = None  # No seasonal component for this data
                )
                
                fit = model.fit()
                
                # Forecast next 3 values
                forecast          = fit.forecast(steps=3)
                forecasted_values = forecast.tolist()
                
                # Calculate confidence score based on model fit quality
                # Using residual standard error as inverse confidence metric
                error     = {}
                residuals = fit.resid
                mse       = (residuals ** 2).mean()
                rmse      = mse ** 0.5

                error['mse']  = float(mse)
                error['rmse'] = float(rmse)

                # Normalize confidence: lower RMSE = higher confidence
                # Use data scale (std dev) to normalize RMSE
                data_std = data.std()
                
                if data_std > 0:
                    normalized_error = rmse / data_std
                    # Convert to confidence score (0-1 range, higher is better)
                    confidence = max(0, min(1, 1 - normalized_error))
                    if confidence < 0.9:
                        confidence += 0.1  # Boost confidence for borderline cases
                else:
                    confidence = 0.5  # Default if std dev is 0
                
                LOGGER.info(f"Metric: {column}, RMSE: {rmse:.4f}, Data Std: {data_std:.4f}, Confidence: {confidence:.4f}")
                LOGGER.info(f"Forecasted next 3 values for {column}: {forecasted_values}")

                results.append({
                    "metric_name":       column,
                    "forecasted_values": forecasted_values,
                    "confidence":        float(confidence),
                    "sample_interval":   5,
                    "error_metrics":     error,
                })
            
            # Push results to DB via InfluxDB fetcher
            if results and self._influx_fetcher:
                self._influx_fetcher.write_predicted_telemetry(results)
            
            return results if results else None
        
        except Exception as e:
            LOGGER.error(f"Error during forecasting: {e}", exc_info=True)
            return None

    def process_data(
        self,
        performance_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Process device and performance data through AI models.

        Args:
            performance_data: Performance metrics from InfluxDB.
            sla_policy: The SLA policy configuration with thresholds.

        Returns:
            Dictionary containing:
                - 'confidence_scores': AI model confidence scores.
                - 'summary': Dictionary with analysis summary statistics.
        """
        LOGGER.debug("Processing data through AI models")

        metric_values = performance_data.get('metric_values', [])
        LOGGER.debug(f"Number of performance data points: {len(metric_values)}")
        # LOGGER.debug(f"Performance data values: {metric_values}")

        if not metric_values:
            LOGGER.warning("No performance data available for processing")
            return {
                'model_result': None,
                'timestamp':    datetime.now(UTC).isoformat()
            }
        result = self.ai_model_processor(metric_values)

        if result is None:
            # fallback score structure
            LOGGER.warning("AI model processing failed or insufficient data. See logs for details.")
            return {
                'model_result': None,
                'timestamp':    datetime.now(UTC).isoformat()
            }

        return {
            'model_result': result,
            'timestamp':    datetime.now(UTC).isoformat()
        }
