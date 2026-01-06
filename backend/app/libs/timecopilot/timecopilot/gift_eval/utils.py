from itertools import product

QUANTILE_LEVELS = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]

SHORT_DATASETS = [
    "m4_yearly",
    "m4_quarterly",
    "m4_monthly",
    "m4_weekly",
    "m4_daily",
    "m4_hourly",
    "electricity/15T",
    "electricity/H",
    "electricity/D",
    "electricity/W",
    "solar/10T",
    "solar/H",
    "solar/D",
    "solar/W",
    "hospital",
    "covid_deaths",
    "us_births/D",
    "us_births/M",
    "us_births/W",
    "saugeenday/D",
    "saugeenday/M",
    "saugeenday/W",
    "temperature_rain_with_missing",
    "kdd_cup_2018_with_missing/H",
    "kdd_cup_2018_with_missing/D",
    "car_parts_with_missing",
    "restaurant",
    "hierarchical_sales/D",
    "hierarchical_sales/W",
    "LOOP_SEATTLE/5T",
    "LOOP_SEATTLE/H",
    "LOOP_SEATTLE/D",
    "SZ_TAXI/15T",
    "SZ_TAXI/H",
    "M_DENSE/H",
    "M_DENSE/D",
    "ett1/15T",
    "ett1/H",
    "ett1/D",
    "ett1/W",
    "ett2/15T",
    "ett2/H",
    "ett2/D",
    "ett2/W",
    "jena_weather/10T",
    "jena_weather/H",
    "jena_weather/D",
    "bitbrains_fast_storage/5T",
    "bitbrains_fast_storage/H",
    "bitbrains_rnd/5T",
    "bitbrains_rnd/H",
    "bizitobs_application",
    "bizitobs_service",
    "bizitobs_l2c/5T",
    "bizitobs_l2c/H",
]

MED_LONG_DATASETS = [
    "electricity/15T",
    "electricity/H",
    "solar/10T",
    "solar/H",
    "kdd_cup_2018_with_missing/H",
    "LOOP_SEATTLE/5T",
    "LOOP_SEATTLE/H",
    "SZ_TAXI/15T",
    "M_DENSE/H",
    "ett1/15T",
    "ett1/H",
    "ett2/15T",
    "ett2/H",
    "jena_weather/10T",
    "jena_weather/H",
    "bitbrains_fast_storage/5T",
    "bitbrains_rnd/5T",
    "bizitobs_application",
    "bizitobs_service",
    "bizitobs_l2c/5T",
    "bizitobs_l2c/H",
]

ALL_DATASETS = SHORT_DATASETS + MED_LONG_DATASETS


DATASETS_WITH_TERMS = [(dataset_name, "short") for dataset_name in SHORT_DATASETS]
DATASETS_WITH_TERMS += [
    (dataset_name, term)
    for dataset_name, term in product(MED_LONG_DATASETS, ["medium", "long"])
]
