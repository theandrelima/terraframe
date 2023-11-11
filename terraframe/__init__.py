from typing import Dict, Any, Type, Optional, List

import yaml
from pathlib import Path

from store import TFModelsGlobalStore, get_shared_data_store
from terraframe.models import TerraFrameBaseModel, DeploymentModel, RemoteStateModel
from terraframe.utils import (
    yaml_to_dict,
    expand_deployment_templates,
    create_all_models_from_yaml,
    get_yaml_key_name_to_models_mapping,
    get_all_matching_files_for_path,
    get_all_variables_from_module
)
from terraframe.constants import DEPLOYMENT_TEMPLATES_KEY


class Terraframe:
    """
    The main class to work with.
    It includes necessary methods to create TerraframeModel objects from a terraframe.yaml file.
    """

    def __init__(
        self, project_path_str: str, terraframe_yaml_file_name: str = "terraframe.yaml"
    ):
        self.ds = get_shared_data_store().records
        self.project_path = Path(project_path_str)
        self.terraframe_file = self.project_path / terraframe_yaml_file_name
        self.loaded_dict = self.get_loaded_dict()
        self.keys_to_models_mapping = get_yaml_key_name_to_models_mapping()
        self.create_all_models_from_yaml(self.loaded_dict, self.keys_to_models_mapping)

    def get_loaded_dict(self) -> Dict[str, Any]:
        """
        Loads and expands the YAML file in a python dictionary.

        Returns:
            The python dictionary representation of the loaded YAML.
        """
        dictionary = yaml_to_dict(yaml_file_path=self.terraframe_file)
        expand_deployment_templates(dictionary)

        return dictionary

    @staticmethod
    def create_all_models_from_yaml(
        yaml_dict: dict, key_to_model_mapping: Dict[str, Type[TerraFrameBaseModel]]
    ) -> None:
        """
        Given a dictionary and a mapping of yaml keys to TerraframeModel classes, evaluates
        if any given key in the dictionary represents a TerraframeModel. If it does, then
        invokes the corresponding model class factory passing the values of that key as arguments
        for instantiating object(s) of such model.

        TODO: include better logic explanation

        Args:
            yaml_dict: a dict taken from yaml config. This could be the full dict, as represented by the yaml file, or a subset of it.
            key_to_model_mapping: a dictionary that maps yaml keys to TerraframeModel classes.
        """
        for yaml_key in yaml_dict:
            model_cls = key_to_model_mapping.get(yaml_key)
            if model_cls:
                if isinstance(yaml_dict[yaml_key], list):
                    for dict_element in yaml_dict[yaml_key]:
                        create_all_models_from_yaml(dict_element, key_to_model_mapping)

                model_cls.factory_for_yaml_data(yaml_dict[yaml_key])

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

    def create_empty_yml_vars_file(self, all_vars: Dict[str, List[str]], file_name: str) -> None:
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

        with open(f"{self.project_path}/{file_name}", "w") as yaml_var_file:
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
        for deployment in self.ds[DeploymentModel]:
            # creates a folder for the deployment
            deployment_path = self.project_path / Path(deployment.name)
            deployment_path.mkdir(exist_ok=True)

            self.create_maintf_file(deployment, deployment_path)
            self.create_variables_file(deployment, deployment_path)
            all_vars[deployment.name] = self.get_vars_for_deployment(deployment)
        else:
            self.create_empty_yml_vars_file(all_vars=all_vars, file_name=f"{self.project_path.name}_deployment_vars.yaml")
