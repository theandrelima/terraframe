import sys
from typing import List, Set, Dict, Optional, Type

import yaml
import json
import sys
import inspect
from pathlib import Path
from custom_collections import HashableDict


def get_all_variables_from_module(
    module_path: Path, variables_file_name: Optional[str] = "variables.tf"
) -> List[str]:
    """Given a module path, extract variable names from its variables file

    Args:
        module_path (Path): the path to the module folder.
        variables_file_name (Optional[str]): the name of the file holding ONLY variable definitions inside the module.
        defaults to 'variables.tf'

    Returns:
        List[str]: each element is the var name for the root module
    """
    with open(f"{module_path}/{variables_file_name}", "r") as vars_tf_file:
        lines = vars_tf_file.readlines()
        variables = [
            line.split('"')[1].strip() for line in lines if line.startswith("variable")
        ]

    return variables


def get_variable_names_for_root_module_based_on_child_module(
    root_module_var_prefix: str,
    child_module_path: Path,
    child_module_var_file_name: Optional[str] = "variables.tf",
) -> List[str]:
    """Generates names for terraform variables to be used by a module that inherits from a child module.

    Args:
        root_module_var_prefix (str): a prefix to be appended to each of the child's module var names
        child_module_path (Path): the path to the child module folder.
        child_module_var_file_name: (Optional[str]): the name of the file holding ONLY variable definitions inside the module.
        defaults to 'variables.tf'

    Returns:
        List[str]: each element is the var name for the root module
    """
    return [
        f"{root_module_var_prefix}{var_name}"
        for var_name in get_all_variables_from_module(
            child_module_path, child_module_var_file_name
        )
    ]


def create_variables_dot_tf_file_for_root_module_based_on_child_module(
    root_module_path: Path,
    root_module_vars_prefix: str,
    child_module_path: Path,
    child_module_var_file_name: Optional[str] = "variables.tf",
) -> None:
    """Creates a .tf file under root_module_path containing all the same variable definitions
    as seen in child_module_path/child_module_var_file_name.

    The name of each variable will be prefixed with the root_modules first characters seen before
    a '_' (underscore) character. For example, if the root_module_path is 'terraform/virtual_colo/dmz_ha_pair',
    each variable in its variables file will start with 'dmz_'.

    The name of this new file will be the same as child_module_var_file_name.

    NOTE: 'description' and 'default_value' fields are not included.

    Args:
        root_module_path (Path): the path to the root module folder.
        root_module_vars_prefix (str): the prefix that should be appended each of the root module's vars.
        child_module_path (Path): the path to the child module folder.
        child_module_var_file_name (Optional[str], optional): the name of the file holding ONLY variable definitions inside the module.
        defaults to 'variables.tf'.
    """

    with open(f"{root_module_path}/{child_module_var_file_name}", "w") as vars_tf_file:
        for variable in get_variable_names_for_root_module_based_on_child_module(
            root_module_vars_prefix, child_module_path
        ):
            vars_tf_file.write(f'variable "{variable}"' + "{\n}\n\n")


def generate_str_for_root_module_input_vars(
    root_module_path: Path, root_module_vars_prefix: str, variables_file: Optional[str] = "variables.tf"
) -> str:
    """Generates a string that can be copied and pasted into a module's call.

    Args:
        root_module_path (Path): the path to the root module folder.
        root_module_vars_prefix (str): the prefix that should be appended each of the root module's vars.
        variables_file (Optional[str], optional): the name of the file holding ONLY variable definitions inside the module. Defaults to "variables.tf".

    Returns:
        str: a multiline string. For each variable named <prefix_var_name> in root_module_path/variables_file,
        appends a new line to a string with format: 'var_name = var.prefix_var_name'
    """

    return_str = """"""
    all_vars = get_all_variables_from_module(root_module_path, variables_file)
    prefix_end_position = len(root_module_vars_prefix)

    for var in all_vars:
        return_str += f"""\n{var[prefix_end_position:]} = var.{var}"""

    return return_str


def get_all_matching_files_for_path(path: Path, file_patterns: List[str]) -> Set[Path]:
    """Recursivelly search and return all files under 'path' folder that match a pattern in 'file_patterns'.

    Args:
        path (Path): the root path to start the search from
        file_patterns (List[str]): file name patterns to match against

    Returns:
        Set[Path]: a set of all files found
    """
    files_to_return = set()

    for pattern in file_patterns:
        matches = path.rglob(pattern)
        for m in matches:
            if m.is_file():
                files_to_return.add(m)

    return files_to_return


def create_empty_yml_vars_file(
    project_path: Path,
    file_name: str,
    variables_file_names: Optional[List[str]] = ["variables.tf"],
) -> None:
    """Creates a YAML file with 'file_name' under 'project_path' directory.
    This file will contain all variables read from files with a name in 'variables_file_name'
    found under project_path structure. All variables will have null value assigned.

    Args:
        project_path (Path): path to a folder that holds terraform modules (subfolders)
        file_name (str): the name of the .yml file to be created
        variables_file_names (Optional[List[str]]): A list of possible variable file names that will be scanned for variables.
        Defaults to ["variables.tf"].
    """
    module_folders = [folder for folder in project_path.iterdir() if folder.is_dir()]

    dict_structure = {}

    for module in module_folders:
        var_files = get_all_matching_files_for_path(module, variables_file_names)
        var_names = []

        for var_file in var_files:
            var_names += get_all_variables_from_module(module, var_file.name)

        dict_structure[module.name] = {var: None for var in var_names}

    with open(f"{project_path}/{file_name}", "w") as yaml_var_file:
        yaml_var_file.write(yaml.dump(dict_structure, indent=4))


def yaml_to_dict(yaml_file_path: Path) -> dict:
    """Parses a YAML file into a python dict."""
    print(yaml_file_path)
    with open(yaml_file_path, "r") as f:
        dictionary = yaml.load(f, Loader=yaml.FullLoader)
    
    return dictionary


def exapand_terraframe_templates(loaded_dict: dict) -> None:
    """Takes a parsed YAML file as a dict and expands 'deployment_templates' into 'deployments'. """


    def _get_template(deployment_dict: dict) -> bool:
        return deployment_dict.pop("deployment_template", None)
    
    templates = loaded_dict["deployment_templates"]
    
    if templates:
        for deployment in loaded_dict["deployments"]:
            template_name = _get_template(deployment)
            if template_name:
                deployment.update(templates[template_name])

        loaded_dict.pop("deployment_templates")


def convert_flat_dict_to_hashabledict(dict_obj: dict) -> HashableDict:
    if not dict_obj:
        return HashableDict()

    if not isinstance(dict_obj, HashableDict):
        dict_obj = HashableDict(dict_obj)

    return dict_obj


def convert_nested_dict_to_hashabledict(dict_obj: dict) -> HashableDict:
    for k in dict_obj:
        if isinstance(dict_obj[k], dict):
            convert_nested_dict_to_hashabledict(dict_obj[k])
            dict_obj[k] = convert_flat_dict_to_hashabledict(dict_obj[k])

    return convert_flat_dict_to_hashabledict(dict_obj)


def get_yaml_key_name_to_models_mapping():
    model_classes = {}
    # TODO: to allow extensibility, this should be a nested loop.
    #   - the outer FOR would loop through a list of possible models python modules.
    #   - the inner FOR is exactly like below
    for _, obj in inspect.getmembers(sys.modules["models"]):
        try:
            m_name = getattr(obj, "_yaml_directive").get_default()
            if inspect.isclass(obj) and m_name:
                model_classes[m_name] = obj
        except AttributeError:
            continue

    return model_classes


def create_all_models_from_yaml(yaml_dict: dict, key_to_model_mapping: Dict[str, Type["TerraFrameBaseModel"]]) -> None:
    for yaml_key in yaml_dict:
        model_cls = key_to_model_mapping.get(yaml_key)
        if model_cls:
            if isinstance(yaml_dict[yaml_key], list):
                for dict_element in yaml_dict[yaml_key]:
                    create_all_models_from_yaml(dict_element, key_to_model_mapping)

            model_cls.factory_for_yaml_data(yaml_dict[yaml_key])