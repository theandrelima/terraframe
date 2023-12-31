from typing import List, Set, Dict, Type, Iterable, Tuple, Any

import yaml
import sys
import inspect
from pathlib import Path
from terraframe.custom_collections import HashableDict


def get_all_matching_files_for_path(
        path: Path, file_patterns: Iterable[str]
) -> Set[Path]:
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


def yaml_to_dict(yaml_file_path: Path) -> dict:
    """Parses a YAML file into a python dict."""
    with open(yaml_file_path, "r") as f:
        dictionary = yaml.load(f, Loader=yaml.FullLoader)

    return dictionary


def expand_deployment_templates(loaded_dict: dict) -> None:
    """Takes a parsed YAML file as a dict and expands 'deployment_templates' into 'deployments'."""

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
    for _, obj in inspect.getmembers(sys.modules["terraframe.models"]):
        try:
            m_name = getattr(obj, "_yaml_directive").get_default()
            if inspect.isclass(obj) and m_name:
                model_classes[m_name] = obj
        except AttributeError:
            continue

    return model_classes


def create_all_models_from_yaml(
        yaml_dict: dict, key_to_model_mapping: Dict[str, Type["TerraFrameBaseModel"]]
) -> None:
    for yaml_key in yaml_dict:
        model_cls = key_to_model_mapping.get(yaml_key)
        if model_cls:
            if isinstance(yaml_dict[yaml_key], list):
                for dict_element in yaml_dict[yaml_key]:
                    create_all_models_from_yaml(dict_element, key_to_model_mapping)

            model_cls.factory_for_yaml_data(yaml_dict[yaml_key])


#################################
### TERRAFRAME SPECIFIC UTILS ###
#################################
def get_all_variables_from_module(
        module_path: Path, variables_file_name: str = "variables.tf"
) -> List[str]:
    """Given a module path, extract variable names from its variables file

    Args:
        module_path: the path to the module folder.
        variables_file_name: the name of the file holding ONLY variable definitions inside the module.

    Returns:
        A list of strings in which each element is the var name for the root module
    """
    with open(f"{module_path}/{variables_file_name}", "r") as vars_tf_file:
        lines = vars_tf_file.readlines()
        variables = [
            line.split('"')[1].strip() for line in lines if line.startswith("variable")
        ]

    return variables


def create_child_module_var_models(module_path: str) -> Tuple["ChildModuleVarModel", ...]:
    """
    Avails of .get_all_variables_from_module() to retrieve all variables names from a terraform module, and then
    creates all ChildModuleVarModel objects for each.

    Args:
        module_path: a string representing the system path to the terraform Module.

    Returns: a tuple containing all the created ChildModuleVarModel objects.

    """
    # importing here to avoid circular imports
    from terraframe.models import ChildModuleVarModel

    return tuple(
        [
            ChildModuleVarModel.create(dict_args={"name": var})
            for var in get_all_variables_from_module(
            Path(module_path).absolute()
        )
        ]
    )


def create_remote_state_input_models(remote_state_inputs: List[Dict[str, str]]) -> Tuple["RemoteStateInputModel", ...]:
    """
    Creates RemoteStateInputModel objects represented by each element of 'remote_state_inputs'.

    Args:
        remote_state_inputs: a list of dictionaries as follows:
            {
                remote_state: str
                var: str
                output: str
            }

    Returns: a tuple containing all created RemoteStateInputModel objects.

    """
    # importing here to avoid circular imports
    from terraframe.models import ChildModuleVarModel
    from terraframe.models import ChildModuleOutputModel
    from terraframe.models import RemoteStatateInputModel
    from terraframe.models import RemoteStateModel

    return tuple(
        [
            RemoteStatateInputModel.create(
                {
                    "var": ChildModuleVarModel.get({"name": rs_input["var"]}),
                    "output": ChildModuleOutputModel.create(
                        {
                            "name": rs_input["output"],
                            "remote_state": RemoteStateModel.get(
                                {"name": rs_input["remote_state"]}
                            ),
                        }
                    ),
                }
            )
            for rs_input in remote_state_inputs
        ]
    )
