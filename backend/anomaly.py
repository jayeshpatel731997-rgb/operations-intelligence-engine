from __future__ import annotations

import pandas as pd


def calculate_rolling_stats(
    values: pd.Series,
    window: int = 7,
) -> pd.DataFrame:
    baseline = values.shift(1)
    rolling_mean = baseline.rolling(window=window, min_periods=2).mean()
    rolling_std = baseline.rolling(window=window, min_periods=2).std().fillna(0)

    return pd.DataFrame(
        {
            "value": values,
            "rolling_mean": rolling_mean,
            "rolling_std": rolling_std,
            "threshold": rolling_mean + (2 * rolling_std),
        }
    )


def detect_anomaly(value: float, rolling_mean: float, rolling_std: float, anomaly_type: str) -> dict[str, bool | str]:
    threshold = rolling_mean + (2 * rolling_std)
    anomaly_flag = value > threshold if rolling_std > 0 else False

    return {
        "anomaly_flag": anomaly_flag,
        "anomaly_type": anomaly_type if anomaly_flag else "normal",
    }


def detect_downtime_spike(downtime_values: pd.Series, window: int = 7) -> pd.DataFrame:
    stats = calculate_rolling_stats(downtime_values, window)
    stats["anomaly_flag"] = stats["value"] > stats["threshold"]
    stats["anomaly_type"] = stats["anomaly_flag"].map(
        {True: "downtime spike", False: "normal"}
    )
    return stats


def detect_abnormal_speed_drop(speed_loss_values: pd.Series, window: int = 7) -> pd.DataFrame:
    stats = calculate_rolling_stats(speed_loss_values, window)
    stats["anomaly_flag"] = stats["value"] > stats["threshold"]
    stats["anomaly_type"] = stats["anomaly_flag"].map(
        {True: "abnormal speed drop", False: "normal"}
    )
    return stats


def detect_defect_spike(defect_values: pd.Series, window: int = 7) -> pd.DataFrame:
    stats = calculate_rolling_stats(defect_values, window)
    stats["anomaly_flag"] = stats["value"] > stats["threshold"]
    stats["anomaly_type"] = stats["anomaly_flag"].map(
        {True: "defect spike", False: "normal"}
    )
    return stats


def detect_anomalies(
    dataframe: pd.DataFrame,
    downtime_column: str = "downtime_events",
    speed_column: str = "speed_loss",
    defect_column: str = "defect_units",
    window: int = 7,
) -> pd.DataFrame:
    result = dataframe.copy()

    downtime = detect_downtime_spike(result[downtime_column], window)
    speed = detect_abnormal_speed_drop(result[speed_column], window)
    defects = detect_defect_spike(result[defect_column], window)

    result["downtime_anomaly_flag"] = downtime["anomaly_flag"]
    result["downtime_anomaly_type"] = downtime["anomaly_type"]
    result["speed_anomaly_flag"] = speed["anomaly_flag"]
    result["speed_anomaly_type"] = speed["anomaly_type"]
    result["defect_anomaly_flag"] = defects["anomaly_flag"]
    result["defect_anomaly_type"] = defects["anomaly_type"]

    result["anomaly_flag"] = (
        result["downtime_anomaly_flag"]
        | result["speed_anomaly_flag"]
        | result["defect_anomaly_flag"]
    )
    result["anomaly_type"] = result.apply(_first_anomaly_type, axis=1)

    return result


def _first_anomaly_type(row: pd.Series) -> str:
    for column in [
        "downtime_anomaly_type",
        "speed_anomaly_type",
        "defect_anomaly_type",
    ]:
        if row[column] != "normal":
            return row[column]
    return "normal"


if __name__ == "__main__":
    sample = pd.DataFrame(
        {
            "downtime_events": [10, 11, 9, 12, 10, 11, 45],
            "speed_loss": [2, 1, 2, 3, 2, 2, 12],
            "defect_units": [20, 22, 19, 21, 20, 18, 80],
        }
    )
    print(detect_anomalies(sample, window=5)[["anomaly_flag", "anomaly_type"]])
