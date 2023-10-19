import json
from pathlib import Path

from terraframe import Terraframe
from utils import yaml_to_dict, exapand_terraframe_templates, create_all_models_from_yaml, get_yaml_key_name_to_models_mapping, create_empty_yml_vars_file
from models import *


if __name__ == "__main__":
    # import sys
    # print(sys.path)
    #
    # raise Exception
    t = Terraframe()
    # this is very much 'hard-coded' at the moment.
    project_path = Path("tests/projects/my_project")
    terraframe_file = project_path / Path("terraframe.yaml")
    loaded_dict = yaml_to_dict(terraframe_file)
    exapand_terraframe_templates(loaded_dict)
    
    create_all_models_from_yaml(
        yaml_dict=loaded_dict, 
        key_to_model_mapping=get_yaml_key_name_to_models_mapping()
    )
    
    for deployment in t.ds[DeploymentModel]:
        # create deployment folders under the project folder
        deployment_directory = terraframe_file.parent / Path(deployment.name)
        deployment_directory.mkdir(exist_ok=True)

        # create main.tf file
        with open(f"{deployment_directory.absolute()}/main.tf", "w") as main:
            main.write(deployment.get_rendered_str())
        
        # create variables.tf
        for cm in deployment.child_modules:
            with open(f"{deployment_directory.absolute()}/variables.tf", "w") as variables:
                for cmv in cm.child_module_vars:
                    variables.write(f"{cmv.get_rendered_str(extra_vars_dict={'prefix': deployment.prefix})}\n\n")
        
        # create empty terraform.tfvars
        create_empty_yml_vars_file(
            project_path=project_path,
            file_name="virtual_colo_deployment_vars.yml",
        )
    