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

import logging
import pandas as pd
from enum import Enum
from collections import defaultdict

logger = logging.getLogger(__name__)

class Handlers(Enum):
    AGGREGATION_HANDLER = "AggregationHandler"
    AGGREGATION_HANDLER_MANY_TO_ONE = "AggregationHandlerManyToOne"
    UNSUPPORTED_HANDLER = "UnsupportedHandler"

    @classmethod
    def is_valid_handler(cls, handler_name):
        return handler_name in cls._value2member_map_

def select_handler(handler_name):
    try:
        logger.info(f"Aggregation handler: {handler_name}")
        handler_enum = Handlers(handler_name)  # auto-validates
        return HANDLER_FUNCTIONS[handler_enum]
    except (ValueError, KeyError):
        logger.error("Unsupported handler")
        raise ValueError(f"Unsupported handler: {handler_name}")

def transform_data(record : pd.DataFrame, value_key : str) -> pd.DataFrame:
    new_value_key = 'value'
    return record.rename(columns={value_key: new_value_key})

def find(data, type, value):
    return next((item for item in data if item[type] == value), None)

def threshold_handler(key, aggregated_df, thresholds):
    """
    Apply thresholds (value_threshold_low and value_threshold_high) based on the thresholds dictionary
    on the aggregated DataFrame.

    Args:
        key (str): Key for the aggregated DataFrame.
        aggregated_df (pd.DataFrame): DataFrame with aggregated metrics.
        thresholds (dict): Thresholds dictionary with keys in the format '<metricName>' and values as (value_threshold_low, value_threshold_high).

    Returns:
        pd.DataFrame: DataFrame with additional threshold columns.
    """
    for metric_name, threshold_values in thresholds.items():
        # Ensure the metric column exists in the DataFrame
        if metric_name not in aggregated_df.columns:
            logger.warning(f"Metric '{metric_name}' does not exist in the DataFrame for key: {key}. Skipping threshold application.")
            continue

        logger.info(f"[Threshold] Metric: {metric_name}")
        logger.info(f"[Threshold] Value range: {threshold_values}")

        # Ensure the threshold values are valid (check for tuple specifically)
        if isinstance(threshold_values, list) and len(threshold_values) == 2:
            fall_th, raise_th = threshold_values
            
            # Add threshold columns with updated naming
            aggregated_df[f"value_threshold_low"]  = aggregated_df[metric_name] < fall_th
            aggregated_df[f"value_threshold_high"] = aggregated_df[metric_name] > raise_th
        else:
            logger.warning(f"Threshold values for '{metric_name}' ({threshold_values}) are not a list of length 2. Skipping threshold application.")
    logger.info(f"[AggregatedDF]: {aggregated_df}")
    return aggregated_df

def aggregation_handler(key, batch, input_kpi_list, output_kpi_list, thresholds):
    """
      Process a batch of data and calculate aggregated values for each input KPI
      and maps them to the output KPIs.
    """

    logger.info("AggregationHandler starts")
    if not batch:
        logger.warning("Empty batch received. Skipping processing")
        return []

    logger.info(f"Processing {len(batch)} records for key: {key}")

    # Convert data into a DataFrame
    df = pd.DataFrame(batch)

    # Filter the DataFrame to retain rows where kpi_id is in the input list (subscribed endpoints only)
    df = df[df['kpi_id'].isin(input_kpi_list)].copy()

    if df.empty:
        logger.warning(f"No data available for KPIs: {input_kpi_list}. Skipping processing")
        return []

    # Define all possible aggregation methods
    aggregation_methods = {
        "min"     : ('kpi_value', 'min'),
        "max"     : ('kpi_value', 'max'),
        "avg"     : ('kpi_value', 'mean'),
        "first"   : ('kpi_value', lambda x: x.iloc[0]),
        "last"    : ('kpi_value', lambda x: x.iloc[-1]),
        "variance": ('kpi_value', 'var'),
        "count"   : ('kpi_value', 'count'),
        "range"   : ('kpi_value', lambda x: x.max() - x.min()),
        "sum"     : ('kpi_value', 'sum'),
    }

    results = []

    # Process each KPI-specific task parameter
    for kpi_index, kpi_id in enumerate(input_kpi_list):
        logger.debug(f"Processing KPI: {kpi_id}")
        kpi_task_parameters = thresholds["task_parameter"][kpi_index]
        logger.debug(f"KPI task parameters: {kpi_task_parameters}")

        # Get valid task parameters for this KPI
        valid_task_parameters = [
            method for method in kpi_task_parameters.keys()
            if method in aggregation_methods
        ]

        # Select the aggregation methods based on valid task parameters
        selected_methods = {method: aggregation_methods[method] for method in valid_task_parameters}
        logger.debug(f"Processing methods: {selected_methods}")

        kpi_df = df[df['kpi_id'] == kpi_id]
        logger.debug(f"KPI data frame:\n{kpi_df}")

        # Check if kpi_df is not empty before applying the aggregation methods
        if not kpi_df.empty:
            agg_df = kpi_df.groupby('kpi_id').agg(**selected_methods).reset_index()
            logger.debug(f"Aggregated DataFrame for KPI {kpi_id}:\n{agg_df}")

            agg_df['kpi_id'] = output_kpi_list[kpi_index]
            record = threshold_handler(key, agg_df, kpi_task_parameters)

            # Make the data frame agnostic to the aggregation method
            value_key = list(selected_methods.keys())[0]
            upd_record = transform_data(record, value_key)

            # Store the record
            results.extend(upd_record.to_dict(orient='records'))
        else:
            logger.warning(f"No data available for KPIs: {kpi_id}. Skipping aggregation")
            continue

    if results:
        logger.info(f"Aggregation result: {results}")
        return results
    else:
        return []

def aggregation_handler_many_to_one(key, batch, input_kpi_list, output_kpi_list, thresholds):
    logger.info("AggregationHandlerManyToOne starts")
    if not batch:
        logger.warning("Empty batch received. Skipping processing.")
        return []

    logger.info(f"Processing {len(batch)} records for key: {key}")

    kpi_task_parameters = None
    for kpi_index, kpi_id in enumerate(input_kpi_list):
        logger.debug(f"Processing KPI: {kpi_id}")
        kpi_task_parameters = thresholds["task_parameter"][kpi_index]
        logger.debug(f"KPI task parameters: {kpi_task_parameters}")

    threshold_high, threshold_low = None, None
    for _, threshold_values in kpi_task_parameters.items():
        if isinstance(threshold_values, list) and len(threshold_values) == 2:
            threshold_low, threshold_high = threshold_values

    # Group and sum
    sum_dict = defaultdict(int)
    count_dict = defaultdict(int)

    for item in batch:
        kpi_id = item["kpi_id"]
        if kpi_id in input_kpi_list:
            sum_dict[kpi_id] += item["kpi_value"]
            count_dict[kpi_id] += 1

    # Compute average
    avg_dict = {kpi_id: sum_dict[kpi_id] / count_dict[kpi_id] for kpi_id in sum_dict}

    total_kpi_metric = 0
    for kpi_id, total_value in avg_dict.items():
        total_kpi_metric += total_value

    result = {
        "kpi_id": output_kpi_list[0],
        "value": total_kpi_metric,
        "value_threshold_high": bool(total_kpi_metric > threshold_high),
        "value_threshold_low": bool(total_kpi_metric < threshold_low)
    }
    results = []

    results.append(result)
    logger.info(f"Aggregation result: {result}")

    return results

HANDLER_FUNCTIONS = {
    Handlers.AGGREGATION_HANDLER: aggregation_handler,
    Handlers.AGGREGATION_HANDLER_MANY_TO_ONE: aggregation_handler_many_to_one
}
