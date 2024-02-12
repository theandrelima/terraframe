from typing import Dict, Any, Type, Optional, List

import os
import yaml
import json
from pathlib import Path

from pydantic_wrangler import SHARED_DATA_STORE as DATA_STORE
from pydantic_wrangler.utils import get_directive_to_model_mapping, load_file_to_dict, create_all_models_from_dict

from terraframe.models import DeploymentModel
from terraframe.utils import expand_deployment_templates

class Terraframe:
    """
    The main class to work with.
    It includes necessary methods to create TerraframeModel objects from a terraframe.yaml file.
    """

    def __init__(
        self, project_folder_path_str: str, terraframe_yaml_file_name: str = "terraframe.yaml"
    ):
        self._data_store = DATA_STORE
        self.project_folder_path = Path(project_folder_path_str)
        
        # we need to set this env var because some .create methods
        # from Terraframe models will call utils functions that need to know
        # the project folder path. TODO: probably better to move this
        # to an app-wide config.
        os.environ["PROJECT_FOLDER_PATH"] = str(self.project_folder_path)  
        
        self.terraframe_file_path = self.project_folder_path / terraframe_yaml_file_name
        
        #TODO maybe this should become a config/environment variable.
        # self.model_modules = ["terraframe.models"]
        self.create_all_models_from_file()


    @property
    def records(self):
        return self._data_store.records


    @staticmethod
    def create_maintf_file(
        deployment: DeploymentModel,
        deployment_path: Path,
        main_file_name: Optional[str] = "main.tf",
    ) -> None:
        """
        Creates the 'main' file inside a deployment directory

        Args:
            deployment: the DeploymentModel instance.
            deployment_path: a Path object pointing to the folder for the 'deployment' object.
            main_file_name: the name for the main file.
        """
        with open(f"{deployment_path.absolute()}/{main_file_name}", "w") as main:
            main.write(deployment.get_rendered_str())

    @staticmethod
    def create_variables_file(
        deployment: DeploymentModel,
        deployment_path: Path,
        variable_file_name: Optional[str] = "variables.tf",
    ) -> None:
        """
        Creates the 'variables' file inside a deployment folder. For that, the code looks at each ChildModuleVarModel
        of each ChildModuleModel of the deployment instance.

        Args:
            deployment: the DeploymentModel instance.
            deployment_path: a Path object pointing to the folder for the 'deployment' object
            variable_file_name: the name for the variables file.
        """
        for cm in deployment.child_modules:
            with open(
                f"{deployment_path.absolute()}/{variable_file_name}", "w"
            ) as variables:
                for cmv in cm.child_module_vars:
                    variables.write(
                        f"{cmv.get_rendered_str(extra_vars_dict={'prefix': deployment.prefix})}\n\n"
                    )

    @staticmethod
    def get_vars_for_deployment(deployment: DeploymentModel) -> List[str]:
        """
        Retrieves names of all vars associated with 'deployment' and appends the deployment's
        prefix to each.

        Args:
            deployment: the DeploymentModel object to retrieve var names from.

        Returns: a list containing the names of each var associated with each ChildModule
        of 'deployment' object.

        """
        deployment_vars = []

        for child_module in deployment.child_modules:
            for var in child_module.child_module_vars:
                deployment_vars.append(f"{deployment.prefix}{var.name}")

        return deployment_vars
    
    def create_all_models_from_file(self) -> None:
        """pydantic_wrangler.utils.create_all_models_from_file() wouldn't satisfy Terraframe's needs,
        as here we need to do some pre-processing before creating the models. This method
        will be responsible for creating all TerraframeModel objects from the YAML file
        pointed by 'file_path'.

        Args:
            modules_to_inspect (Optional[List], optional): _description_. Defaults to [].
        """
        loaded_data = load_file_to_dict(self.terraframe_file_path)
        expand_deployment_templates(loaded_dict=loaded_data)
        key_to_model_mapping = get_directive_to_model_mapping()
        create_all_models_from_dict(loaded_dict=loaded_data, key_to_model_mapping=key_to_model_mapping)

    def create_empty_yml_vars_file(
        self, all_vars: Dict[str, List[str]], file_name: str
    ) -> None:
        """
        Creates a YAML file with 'file_name' under 'project_path' directory.
        This file will contain all variables read from files with a name in 'variables_file_name'
        found under project_path structure. All variables will have null value assigned.

        Args:
            all_vars: a dict in which each key is a deployment name, and it's associated value is a list of Terraform
            variable names associated with child modules for that deployment.
            file_name: the name for the file that will be created.
        """
        _all_vars = {}

        for k, variables in all_vars.items():
            _all_vars[k] = {var: None for var in variables}

        with open(f"{self.project_folder_path}/{file_name}", "w") as yaml_var_file:
            yaml_var_file.write(yaml.dump(_all_vars, indent=4))

    def process_deployments(self):
        """
        This method is a one-stop-shop to take care of:
            - creating deployment folders under the project folder
            - creating terraform files inside each deployment folder:
                - main.tf
                - variables.tf
                - terraform.tfvars (empty ofr the moment)
            - creating the project-level YAML file with all required vars for the project
        """
        all_vars = {}
        for deployment in self.records[DeploymentModel]:
            # creates a folder for the deployment
            deployment_path = self.project_folder_path / Path(deployment.name)
            deployment_path.mkdir(exist_ok=True)

            self.create_maintf_file(deployment, deployment_path)
            self.create_variables_file(deployment, deployment_path)
            all_vars[deployment.name] = self.get_vars_for_deployment(deployment)
        else:
            self.create_empty_yml_vars_file(
                all_vars=all_vars,
                file_name=f"{self.project_folder_path.name}_deployment_vars.yaml",
            )
