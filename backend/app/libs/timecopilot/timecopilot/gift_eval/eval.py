import logging
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv
from gluonts.ev.metrics import (
    MAE,
    MAPE,
    MASE,
    MSE,
    MSIS,
    ND,
    NRMSE,
    RMSE,
    SMAPE,
    MeanWeightedSumQuantileLoss,
)
from gluonts.model import evaluate_model
from gluonts.model.predictor import RepresentablePredictor
from gluonts.time_feature import get_seasonality
from huggingface_hub import snapshot_download

from .data import Dataset
from .gluonts_predictor import GluonTSPredictor
from .utils import MED_LONG_DATASETS, QUANTILE_LEVELS

logger = logging.getLogger(__name__)

load_dotenv()

METRICS = [
    MSE(forecast_type="mean"),
    MSE(forecast_type=0.5),
    MAE(),
    MASE(),
    MAPE(),
    SMAPE(),
    MSIS(),
    RMSE(),
    NRMSE(),
    ND(),
    MeanWeightedSumQuantileLoss(quantile_levels=QUANTILE_LEVELS),
]
DATASET_PROPERTIES_URL = "https://raw.githubusercontent.com/SalesforceAIResearch/gift-eval/refs/heads/main/notebooks/dataset_properties.json"


class GIFTEval:
    """
    Evaluation utility for [GIFTEval](https://huggingface.co/spaces/Salesforce/GIFT-Eval).

    This class loads a time series dataset, sets up evaluation metrics, and provides
    methods to evaluate GluonTS predictors on the dataset, saving results to CSV if
    desired.
    """

    @staticmethod
    def download_data(storage_path: Path | str | None = None):
        """
        Download the GIFTEval dataset from Hugging Face.

        Args:
            storage_path (Path | str | None): Path to store the dataset.
        """
        snapshot_download(
            repo_id="Salesforce/GiftEval",
            repo_type="dataset",
            local_dir=storage_path,
        )

    def __init__(
        self,
        dataset_name: str,
        term: str,
        output_path: Path | str | None = None,
        storage_path: Path | str | None = None,
    ):
        # fmt: off
        """
        Initialize a GIFTEval instance for a specific dataset and evaluation term.

        Args:
            dataset_name (str): Name of the dataset to evaluate on.
            term (str): Evaluation term (e.g., 'medium', 'long').
            output_path (str | Path | None): Directory to save results CSV, or
                None to skip saving.
            storage_path (Path | str | None): Path where the dataset is stored.

        Example:
            ```python
            import pandas as pd
            from timecopilot.gift_eval.eval import GIFTEval
            from timecopilot.gift_eval.gluonts_predictor import GluonTSPredictor
            from timecopilot.models.stats import SeasonalNaive

            storage_path = "./gift_eval_data"
            GIFTEval.download_data(storage_path)

            predictor = GluonTSPredictor(
                # you can use any forecaster from TimeCopilot
                # and create your own forecaster by subclassing 
                # [Forecaster][timecopilot.models.utils.forecaster.Forecaster]
                forecaster=SeasonalNaive(),
                batch_size=512,
            )
            gift_eval = GIFTEval(
                dataset_name="m4_weekly",
                term="short",
                output_path="./seasonal_naive",
                storage_path=storage_path,
            )
            gift_eval.evaluate_predictor(
                predictor,
                batch_size=512,
            )
            eval_df = pd.read_csv("./seasonal_naive/all_results.csv")
            ```

        Raises:
            ValueError: If the dataset is not compatible with the specified term.

        """
        # fmt: on
        res_dataset_properties = requests.get(DATASET_PROPERTIES_URL)
        res_dataset_properties.raise_for_status()  # Raise an error for bad responses
        self.dataset_properties_map = res_dataset_properties.json()
        pretty_names = {
            "saugeenday": "saugeen",
            "temperature_rain_with_missing": "temperature_rain",
            "kdd_cup_2018_with_missing": "kdd_cup_2018",
            "car_parts_with_missing": "car_parts",
        }
        if (
            term == "medium" or term == "long"
        ) and dataset_name not in MED_LONG_DATASETS:
            raise ValueError(f"Dataset {dataset_name} is not a medium or long dataset")
        if "/" in dataset_name:
            ds_key = dataset_name.split("/")[0]
            ds_freq = dataset_name.split("/")[1]
            ds_key = ds_key.lower()
            ds_key = pretty_names.get(ds_key, ds_key)
        else:
            ds_key = dataset_name.lower()
            ds_key = pretty_names.get(ds_key, ds_key)
            ds_freq = self.dataset_properties_map[ds_key]["frequency"]
        self.ds_config = f"{ds_key}/{ds_freq}/{term}"
        self.ds_key = ds_key

        # Initialize the dataset
        to_univariate = (
            Dataset(
                name=dataset_name,
                term=term,
                to_univariate=False,
                storage_path=storage_path,
            ).target_dim
            != 1
        )
        self.dataset = Dataset(
            name=dataset_name,
            term=term,
            to_univariate=to_univariate,
            storage_path=storage_path,
        )
        self.dataset_name = dataset_name
        self.seasonality = get_seasonality(self.dataset.freq)
        self.output_path = output_path

    def evaluate_predictor(
        self,
        predictor: RepresentablePredictor | GluonTSPredictor,
        batch_size: int | None = None,
        overwrite_results: bool = False,
    ):
        """
        Evaluate a GluonTS predictor on the loaded dataset and save results.

        Args:
            predictor (RepresentablePredictor | GluonTSPredictor): The predictor to
                evaluate.
            batch_size (int | None): Batch size for evaluation. If None, uses
                predictor's default.
            overwrite_results (bool): Whether to overwrite the existing results CSV
                file.
        """
        if batch_size is None:
            if isinstance(predictor, GluonTSPredictor):
                batch_size = predictor.batch_size
            else:
                batch_size = 512
        res = evaluate_model(
            predictor,
            test_data=self.dataset.test_data,
            metrics=METRICS,
            batch_size=batch_size,
            axis=None,
            mask_invalid_label=True,
            allow_nan_forecast=False,
            seasonality=self.seasonality,
        )

        # Prepare the results for the CSV file
        model_name = (
            predictor.__class__.__name__
            if not isinstance(predictor, GluonTSPredictor)
            else predictor.alias
        )
        results_data = [
            [
                self.ds_config,
                model_name,
                res["MSE[mean]"][0],
                res["MSE[0.5]"][0],
                res["MAE[0.5]"][0],
                res["MASE[0.5]"][0],
                res["MAPE[0.5]"][0],
                res["sMAPE[0.5]"][0],
                res["MSIS"][0],
                res["RMSE[mean]"][0],
                res["NRMSE[mean]"][0],
                res["ND[0.5]"][0],
                res["mean_weighted_sum_quantile_loss"][0],
                self.dataset_properties_map[self.ds_key]["domain"],
                self.dataset_properties_map[self.ds_key]["num_variates"],
            ]
        ]

        # Create a DataFrame and write to CSV
        results_df = pd.DataFrame(
            results_data,
            columns=[
                "dataset",
                "model",
                "eval_metrics/MSE[mean]",
                "eval_metrics/MSE[0.5]",
                "eval_metrics/MAE[0.5]",
                "eval_metrics/MASE[0.5]",
                "eval_metrics/MAPE[0.5]",
                "eval_metrics/sMAPE[0.5]",
                "eval_metrics/MSIS",
                "eval_metrics/RMSE[mean]",
                "eval_metrics/NRMSE[mean]",
                "eval_metrics/ND[0.5]",
                "eval_metrics/mean_weighted_sum_quantile_loss",
                "domain",
                "num_variates",
            ],
        )
        if self.output_path is not None:
            csv_file_path = Path(self.output_path) / "all_results.csv"
            csv_file_path.parent.mkdir(parents=True, exist_ok=True)
            if csv_file_path.exists() and not overwrite_results:
                results_df = pd.concat([pd.read_csv(csv_file_path), results_df])
            results_df.to_csv(csv_file_path, index=False)

            logger.info(
                f"Results for {self.dataset_name} have been written to {csv_file_path}"
            )
