from fobam.oba_crawler import OBAMeasurementExperiment
# Load experiment previously created
experiment = OBAMeasurementExperiment(experiment_name="example_clothing_accept_cookie_banner_experiment", fresh_experiment=False)
experiment.set_training_pages_by_category(category="Clothing")