from fobam.oba_crawler import OBAMeasurementExperiment

API_KEY = "GhU39K7bdfvdxRlcnEkT"
SECRET_KEY = "ZwnCzHIpw08DF10Fmz5c"
credentials = {"api_key": API_KEY, "secret_key": SECRET_KEY}
# EXAMPLE CASE 0: LOAD CREATED EXPERIMENT
def load_previously_created_experiment_example():
    """Load experiment already created previously. Requires the experiment called 'example_previously_created_experiment' to be already created."""
    experiment_handler = OBAMeasurementExperiment(
        "example_load_previously_created_experiment", False
    )
    experiment_handler.set_training_pages_by_category("Clothing")
    return experiment_handler


# EXAMPLE CASES WITH TRANCO PAGES

# EXAMPLE CASE 1: Default CREATE CACHED TRANCO
def create_default_cached_tranco_experiment_example():
    """Create new experiment with default parameters: using default cached tranco pages already categorized (uses TrainingPagesHandler)."""
    experiment_handler = OBAMeasurementExperiment("example_default_experiment", True)
    experiment_handler.set_training_pages_by_category("Clothing")
    return experiment_handler


# EXAMPLE CASE 2: CREATE NEW TRANCO
def create_updated_tranco_experiment_example():
    """Create new experiment with custom parameters: using custom pages list and categorizing them (uses TrainingPagesHandler)."""
    oba_exp_tranco_pages_updated = {
        "experiment_name": "example_tranco_updated_experiment",
        "fresh_experiment": True,  # If True we need the training_pages_params (experiment setup), create browser profile and {experiment_name}_config.json file. If false we don't need anything else.
        "use_custom_pages": False,  # If false we will use tranco_params
        "tranco_pages_params": {
            "updated": True,  #  We have to retrieve the last list of tranco and categorize it.
            "size": 1000000,
        },
        # If use_custom_pages==False and tranco_pages_params['updated'] == True, we need 'webshrinker_credentials'.
        "webshrinker_credentials": credentials,
        "custom_pages_params": None,  # Not needed for this case
    }
    experiment_handler = OBAMeasurementExperiment(**oba_exp_tranco_pages_updated)
    experiment_handler.set_training_pages_by_category("Clothing")
    return experiment_handler


# EXAMPLE CASES WITH CUSTOM PAGES

# EXAMPLE CASE 3: CREATE CUSTOM NO CATEGORIZATION
def create_custom_pages_no_categorization_experiment_example():
    example_custom_pages_list_no_specific_category = [
        "https://www.google.com",
        "https://www.delish.com",
        "https://www.foodnetwork.com/",
        "https://www.oakley.com",
        "https://www.facebook.com",
        "https://www.tasteofhome.com/",
        "https://www.coursera.org",
    ]
    """ Create new experiment with custom parameters: using custom pages list and categorizing them (does not use TrainingPagesHandler). """
    oba_exp_custom_pages_no_categorization = {
        "experiment_name": "example_custom_pages_experiment_no_categorization",
        "fresh_experiment": True,  # If True we need the training_pages_params (experiment setup), create browser profile and {experiment_name}_config.json file. If false we don't need anything else.
        "use_custom_pages": True,  # If True we will use custom_pages_params
        "custom_pages_params": {
            "categorize_pages": False,  # If it is False, we use the custom_pages_list and we do not use a TrainingPagesHandler at all, the list must be then saved in the {experiment_name}_config.json file without a list_id.
            "custom_pages_list": example_custom_pages_list_no_specific_category,  # List of URLs provided by the user.
        },
        "webshrinker_credentials": None,  # Not required for this case
        "tranco_pages_params": None,  # Not required for this case
    }

    experiment_handler = OBAMeasurementExperiment(
        **oba_exp_custom_pages_no_categorization
    )
    return experiment_handler


# EXAMPLE CASE 4: CREATE NEW CUSTOM PAGES WITH CATEGORIZATION
def create_custom_pages_with_categorization_experiment_example():
    """Create new experiment with custom parameters: using custom pages list and not categorizing them since it is not needed."""
    example_custom_pages_list_food_category = [
        "https://www.allrecipes.com/",
        "https://www.foodnetwork.com/",
        "https://www.tasteofhome.com/",
        "https://www.delish.com/",
        "https://www.bbcgoodfood.com/",
        "https://www.thespruceeats.com/",
        "https://www.thekitchn.com/",
    ]
    oba_custom_pages_with_categorize = {
        "experiment_name": "custom_exp_categorize",
        "fresh_experiment": True,  # If True we need the training_pages_params (experiment setup), create browser profile and {experiment_name}_config.json file. If false we don't need anything else.
        "use_custom_pages": True,  # If True we will use custom_pages_params
        "custom_pages_params": {
            "categorize_pages": True,  # If True we load the TrainingPagesHandler with the custom_pages_list=custom_pages_list, under custom_list=True, list_id={experiment_name}.
            "custom_pages_list": example_custom_pages_list_food_category,  # List of URLs provided by the user. This list is not saved in the {experiment_name}_config.json, since it has to first be categorized and then accessed through the TrainingPagesHandler().get_training_pages_by_category() method.
        },
        # If use_custom_pages==True and custom_pages_params['categorize_pages'] == True, we need 'webshrinker_credentials'.
        "webshrinker_credentials": {"api_key": API_KEY, "secret_key": SECRET_KEY},
        "tranco_pages_params": None,  # Not required for this case
    }
    experiment_handler = OBAMeasurementExperiment(**oba_custom_pages_with_categorize)

    return experiment_handler


# EXAMPLE CASE OF COOKIE BANNER USE
# EXAMPLE CASE 5: COOKIE BANNER
def create_cookie_banner_experiment_example():
    """Create new experiment with custom parameters: using custom pages list and categorizing them (uses TrainingPagesHandler). These pages have cookie banners and crawler will accept them."""
    random_pages_with_cookie_banner_various_languages = [
        "http://demandbase.com",
        "http://liftoff.io",
        "http://hyprmx.com",
        "http://conviva.com",
        "http://vdx.tv",
        "http://adtelligent.com",
        "http://buzzoola.com",
        "http://www.deepintent.com/",
        "http://mopub.com",
        "http://www.primis.tech",
    ]
    oba_custom_cookie_banner_pages = {
        "experiment_name": "example_cookie_banner_experiment",
        "fresh_experiment": True,  # If True we need the training_pages_params (experiment setup), create browser profile and {experiment_name}_config.json file. If false we don't need anything else.
        "cookie_banner_action": 1,
        "use_custom_pages": True,  # If True we will use custom_pages_params
        "custom_pages_params": {
            "categorize_pages": True,  # If True we load the TrainingPagesHandler with the custom_pages_list=custom_pages_list, under custom_list=True, list_id={experiment_name}.
            "custom_pages_list": random_pages_with_cookie_banner_various_languages,  # List of URLs provided by the user. This list is not saved in the {experiment_name}_config.json, since it has to first be categorized and then accessed through the TrainingPagesHandler().get_training_pages_by_category() method.
        },
        # If use_custom_pages==True and custom_pages_params['categorize_pages'] == True, we need 'webshrinker_credentials'.
        "webshrinker_credentials": {"api_key": API_KEY, "secret_key": SECRET_KEY},
        "tranco_pages_params": None,  # Not required for this case
    }
    experiment_handler = OBAMeasurementExperiment(**oba_custom_cookie_banner_pages)
    return experiment_handler


airtravel_pages_with_cookie_banner = [
    "http://aviasales.com",
    "http://britishairways.com",
    "http://easyjet.com",
    "http://emirates.com",
    "http://flightradar24.com",
    "http://kiwi.com",
    "http://ryanair.com",
]
