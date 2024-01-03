
API_KEY = "GhU39K7bdfvdxRlcnEkT"
SECRET_KEY = "ZwnCzHIpw08DF10Fmz5c"
credentials = {"api_key": API_KEY, "secret_key": SECRET_KEY}

# TODO: Repeat all the experiment for tranco 1M to have more categorized pages of every category cached.

# Create experiment with parameters
oba_cookie_banner_experiment_with_categorization = {
        "experiment_name": "example_clothing_accept_cookie_banner_experiment",
        "fresh_experiment": True,
        "cookie_banner_action": 1,
        "tranco_pages_params": {
            "updated": True,
            "size": 100,
            },
        # We need valid 'webshrinker_credentials' to be able to categorize.
        "webshrinker_credentials": {"api_key": API_KEY, "secret_key": SECRET_KEY},
    }



from fobam.oba_crawler import OBAMeasurementExperiment
experiment = OBAMeasurementExperiment(**oba_cookie_banner_experiment_with_categorization)