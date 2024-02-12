from typing import List, Set, Dict, Iterable, Tuple

import os
from pathlib import Path


def get_all_matching_files_for_path(
        path: Path, file_patterns: Iterable[str]
) -> Set[Path]:
    """Recursivelly search and return all files under 'path' folder 
    that match a pattern in 'file_patterns'.

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


def expand_deployment_templates(loaded_dict: dict) -> None:
    """Takes a parsed YAML file as a dict and expands 'deployment_templates' 
    into 'deployments'."""

    def _get_template(deployment_dict: dict) -> bool:
        return deployment_dict.pop("deployment_template", None)

    templates = loaded_dict["deployment_templates"]

    if templates:
        for deployment in loaded_dict["deployments"]:
            template_name = _get_template(deployment)
            if template_name:
                deployment.update(templates[template_name])

        loaded_dict.pop("deployment_templates")


def get_all_variables_from_module(
        module_rel_path: Path, variables_file_name: str = "variables.tf"
) -> List[str]:
    """Given a Path object that represents the relative system path to a 
    terraform module, extract variable names from its variables file

    Args:
        module_rel_path: a Path object that points to the terraform module
        where the variables file will be read from. It must be relative to 
        the directory where the terraframe.yaml file exists.
        variables_file_name: the name of the file holding ONLY variable 
        definitions inside the module.

    Returns:
        A list of strings in which each element is the var name for the root module
    """
    abs_path_to_tf_module = (Path(os.getenv("PROJECT_FOLDER_PATH", "")) / module_rel_path).resolve()
    
    with open(f"{abs_path_to_tf_module}/{variables_file_name}", "r") as vars_tf_file:
        lines = vars_tf_file.readlines()
        variables = [
            line.split('"')[1].strip() for line in lines if line.startswith("variable")
        ]

    return variables


def create_child_module_var_models(module_rel_path_str: str) -> Tuple["ChildModuleVarModel", ...]:
    """
    Avails of .get_all_variables_from_module() to retrieve all variables 
    names from a terraform module, and then creates all ChildModuleVarModel 
    objects for each.

    Args:
        module_rel_path_str: a string representing the relative path to the 
        terraform parent Module.

    Returns: a tuple containing all the created ChildModuleVarModel objects.

    """
    # importing here to avoid circular imports
    from terraframe.models import ChildModuleVarModel

    return tuple(
        [
            ChildModuleVarModel.create(dict_args={"name": var})
            for var in get_all_variables_from_module(
            Path(module_rel_path_str)
        )
        ]
    )


def create_remote_state_input_models(remote_state_inputs: List[Dict[str, str]]) -> Tuple["RemoteStateInputModel", ...]:
    """
    Creates RemoteStateInputModel objects represented by each element 
    of 'remote_state_inputs'.

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
