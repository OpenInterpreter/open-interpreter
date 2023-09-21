import inquirer
from utils.get_local_models_paths import get_local_models_paths
import os

def model_explorer():
    return

def get_more_models(model_name=None, parameter_level=None):
    # This function will return more models based on the given parameters
    # For now, it's just a placeholder
    return []

def select_model():
    models = get_local_models_paths()
    models.append("Get More ->")
    questions = [inquirer.List('model', message="Select a model", choices=models)]
    answers = inquirer.prompt(questions)
    if answers['model'] == "Get More ->":
        return get_more_models()
    else:
        return select_parameter_level(answers['model'])

def select_parameter_level(model):
    # Assuming parameter levels are subfolders in the model folder
    parameter_levels = os.listdir(model)
    parameter_levels.append("Get More ->")
    questions = [inquirer.List('parameter_level', message="Select a parameter level", choices=parameter_levels)]
    answers = inquirer.prompt(questions)
    if answers['parameter_level'] == "Get More ->":
        return get_more_models(model)
    else:
        return os.path.join(model, answers['parameter_level'])

def select_quality_level(parameter_level):
    # Assuming quality levels are files in the parameter level folder
    quality_levels = [f for f in os.listdir(parameter_level) if os.path.isfile(os.path.join(parameter_level, f))]
    quality_levels.append("Get More ->")
    questions = [inquirer.List('quality_level', message="Select a quality level", choices=quality_levels)]
    answers = inquirer.prompt(questions)
    if answers['quality_level'] == "Get More ->":
        return get_more_models(parameter_level)
    else:
        return os.path.join(parameter_level, answers['quality_level'])