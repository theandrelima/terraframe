from typing import Dict, Any, Type, Optional, Iterable, List, Set

import sys
import yaml
import inspect
from pathlib import Path

from store import TFModelsGlobalStore, get_shared_data_store
from terraframe.models import TerraFrameBaseModel, DeploymentModel
from terraframe.utils import yaml_to_dict, exapand_terraframe_templates, create_all_models_from_yaml, get_yaml_key_name_to_models_mapping
from terraframe.constants import DEPLOYMENT_TEMPLATES_KEY


class Terraframe:
    """
    The main class to work with.
    It includes necessary methods to create TerraframeModel objects from a terraframe.yaml file.
    """
    def __init__(self, project_path_str: str, terraframe_yaml_file_name: str = "terraframe.yaml"):
        self.ds = get_shared_data_store().records
        self.project_path = Path(project_path_str)
        self.terraframe_file = self.project_path / terraframe_yaml_file_name
        self.loaded_dict = self.get_loaded_dict()

    @staticmethod
    def _expand_deployment_templates(loaded_dict: Dict[str, Any]) -> None:
        """
        Helper method that checks if there's deployments to expand in the yaml file.
        If there's any, it expands it with the specified deployent_template.

        Args:
            loaded_dict: the yaml file loaded as a python dictionary.
        """
        def get_deployment_template(deployment_dict: Dict[str, Any]) -> bool:
            return deployment_dict.pop("deployment_template", None)

        templates = loaded_dict["deployment_templates"]

        if templates:
            for deployment in loaded_dict["deployments"]:
                template_name = get_deployment_template(deployment)
                if template_name:
                    deployment.update(templates[template_name])

            loaded_dict.pop("deployment_templates")

    @staticmethod
    def get_yaml_key_name_to_models_mapping():
        """
        Creates a mapping between TerraframeModel '_yaml_directive' attribute and the
        TerraframeModel class itself. This allows for easy correlation between 'keys'
        in terraframe.yaml keys and actual TerraframeModels.

        Returns:
            A dictionary in which each key is a yaml directive and the value is the
        corresponding TerraframeModel class.

        """
        model_classes = {}
        # how do I register modules?
        # for module in registered_model_modules:
        for _, obj in inspect.getmembers(sys.modules["models"]):
            try:
                m_name = getattr(obj, "_yaml_directive").get_default()
                if inspect.isclass(obj) and m_name:
                    model_classes[m_name] = obj
            except AttributeError:
                continue

        return model_classes

    def get_loaded_dict(self) -> Dict[str, Any]:
        """
        Loads and expands the YAML file in a python dictionary.

        Returns:
            The python dictionary representation of the loaded YAML.
        """
        with open(self.terraframe_file, "r") as f:
            dictionary = yaml.load(f, Loader=yaml.FullLoader)

        self._expand_deployment_templates(dictionary)

        return dictionary

    @staticmethod
    def create_all_models_from_yaml(yaml_dict: dict, key_to_model_mapping: Dict[str, Type[TerraFrameBaseModel]]) -> None:
        """
        Given a dictionary and a mapping of yaml keys to TerraframeModel classes, evaluates
        if any given key in the dictionary represents a TerraframeModel. If it does, then
        invokes the corresponding model class factory passing the values of that key as arguments
        for instanting object(s) of such model.

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
        for deployment in self.ds[DeploymentModel]:
            # creates a folder for the deployment
            deployment_path = self.project_path / Path(deployment.name)
            deployment_path.mkdir(exist_ok=True)

            self._create_maintf_file(deployment, deployment_path)
            self._create_variables_file(deployment, deployment_path)
            self._create_empty_yml_vars_file(f"{deployment.name}_deployment_vars.yaml")

    @staticmethod
    def _create_maintf_file(deployment: DeploymentModel, deployment_path: Path, main_file_name: Optional[str] = "main.tf") -> None:
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
    def _create_variables_file(deployment: DeploymentModel, deployment_path: Path, variable_file_name: Optional[str] = "variables.tf") -> None:
        """
        Creates the 'variables' file inside a deployment. For that, the code looks at each ChildModuleVarModel
        of each ChildModuleModeel of the deployment instance.

        Args:
            deployment: the DeploymentModel instance.
            deployment_path: a Path object pointing to the folder for the 'deployment' object
            variable_file_name: the name for the variables file.
        """
        for cm in deployment.child_modules:
            with open(f"{deployment_path.absolute()}/{variable_file_name}", "w") as variables:
                for cmv in cm.child_module_vars:
                    variables.write(f"{cmv.get_rendered_str(extra_vars_dict={'prefix': deployment.prefix})}\n\n")

    def _create_empty_yml_vars_file(self, file_name: str, variables_file_names: Iterable[str]=("variables.tf",)) -> None:
        """Creates a YAML file with 'file_name' under 'project_path' directory.
        This file will contain all variables read from files with a name in 'variables_file_name'
        found under project_path structure. All variables will have null value assigned.

        Args:
            file_name: the name of the .yml file to be created
            variables_file_names: An iterable of strings representing the possible variable
            file names that will be scanned for variables.
        """
        module_folders = [folder for folder in self.project_path.iterdir() if folder.is_dir()]

        dict_structure = {}

        for module in module_folders:
            var_files = self.get_all_matching_files_for_path(module, variables_file_names)
            var_names = []

            for var_file in var_files:
                var_names += self.get_all_variables_from_module(module, var_file.name)

            dict_structure[module.name] = {var: None for var in var_names}

        with open(f"{self.project_path}/{file_name}", "w") as yaml_var_file:
            yaml_var_file.write(yaml.dump(dict_structure, indent=4))

    @staticmethod
    def get_all_matching_files_for_path(path: Path, file_patterns: Iterable[str]) -> Set[Path]:
        """Recursivelly search and return all files under 'path' folder that match a pattern in 'file_patterns'.

        Args:
            path: the root path to start the search from
            file_patterns: file name patterns to match against

        Returns:
            A set object containing all files found.
        """
        files_to_return = set()

        for pattern in file_patterns:
            matches = path.rglob(pattern)
            for m in matches:
                if m.is_file():
                    files_to_return.add(m)

        return files_to_return

    @staticmethod
    def get_all_variables_from_module(module_path: Path, variables_file_name: str = "variables.tf") -> List[str]:
        """Given a module path, extract variable names from its variables file

        Args:
            module_path: the path to the module folder.
            variables_file_name: the name of the file holding ONLY variable definitions inside the module.

        Returns:
            A list of strings in which each element is the var name for the root module
        """
        with open(f"{module_path}/{variables_file_name}", "r") as vars_tf_file:
            lines = vars_tf_file.readlines()
            variables = [line.split('"')[1].strip() for line in lines if line.startswith("variable")]

        return variables