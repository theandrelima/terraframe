import json
from pathlib import Path

from terraframe import Terraframe
from utils import (
    yaml_to_dict,
    exapand_terraframe_templates,
    create_all_models_from_yaml,
    get_yaml_key_name_to_models_mapping,
    create_empty_yml_vars_file,
)
from models import *


if __name__ == "__main__":
    project_path = "tests/projects/my_project"
    t = Terraframe(project_path_str=project_path)
    t.process_deployments()
