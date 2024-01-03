from oba_crawler_copy import OBAMeasurementExperiment

# Create experiment and categorize 1m tranco pages
experiment = OBAMeasurementExperiment(
    experiment_name="categorize_tranco_1m",
    fresh_experiment=True,
    cookie_banner_action=1,
    tranco_pages_params={
        "updated": True,
        "size": 10000,
    },
    webshrinker_credentials={
        "api_key": "GhU39K7bdfvdxRlcnEkT",
        "secret_key": "ZwnCzHIpw08DF10Fmz5c",
    },
)
