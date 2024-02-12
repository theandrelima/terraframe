from typing import Optional, List, Dict, Any, Tuple, Union

from sortedcontainers import SortedSet

from pydantic_wrangler import PydanticWranglerBaseModel
from pydantic_wrangler import PydanticWranglerRenderableModel
from pydantic_wrangler import HashableDict, HashableDictType

from terraframe.utils import create_child_module_var_models, create_remote_state_input_models


class ChildModuleOutputModel(PydanticWranglerBaseModel):
    """Stores data of a Child Module's output. An instance of this model 
    is used as the `output` attribute of a `RemoteStatateInputModel`.
    
    This model does not have a _directive attribute because it is not meant
    to be created directly from a YAML file. It is created as part of the
    `ChildModuleModel.create` method.
    """

    name: str
    remote_state: "RemoteStateModel"



# TODO: make this a config/setting
TEMPLATES_DIR = "terraframe/templates"



class ChildModuleVarModel(PydanticWranglerRenderableModel):
    """Stores data of a Child Module's variable. An instance of this model
    is used as the `var` attribute of a `RemoteStatateInputModel`, as well
    as one of the elements in the `child_module_vars` attribute of a 
    `ChildModuleModel`.
    
    This model does not have a _directive attribute because it is not meant
    to be created directly from a YAML file. It is created as part of the 
    `ChildModuleModel.create` method.

    """

    name: str

    # TODO: currently not adding type and description, 
    # but set here for future development
    type: Optional[str] = None
    description: Optional[str] = None

    _template_name: str = "variables"


class RemoteStatateInputModel(PydanticWranglerRenderableModel):
    """Identifies a variable that should take it's input from a specific output
    accessible via a `terraform_remote_state` resource
    
    This model does not have a _directive attribute because it is not meant
    to be created directly from a YAML file. It is created as part of the 
    `ChildModuleModel.create` method.
    """

    _key: Tuple = ("var", "output")
    var: ChildModuleVarModel
    output: ChildModuleOutputModel


class RemoteStateModel(PydanticWranglerRenderableModel):
    """Stores data of a terraform_remote_state resource"""

    _directive: str = "remote_states"

    name: str
    backend: str
    config: HashableDictType


class ChildModuleModel(PydanticWranglerRenderableModel):
    _directive: str = "child_modules"
    name: str
    source: str
    child_module_vars: Tuple[ChildModuleVarModel, ...]
    remote_states_inputs: Tuple[RemoteStatateInputModel, ...] = tuple()

    # noinspection PyTypeChecker
    @classmethod
    def create(cls, dict_args: Dict[str, Any], *args, **kwargs) -> "ChildModuleModel":
        _child_module_vars = create_child_module_var_models(dict_args["source"])
        _remote_states_inputs = create_remote_state_input_models(dict_args["remote_state_inputs"])

        dict_args.update(
            {
                "child_module_vars": _child_module_vars,
                "remote_states_inputs": _remote_states_inputs,
            }
        )

        return super().create(dict_args=dict_args, *args, **kwargs)


class DeploymentModel(PydanticWranglerRenderableModel):
    _key: Tuple = ("index", "name")
    _directive: str = "deployments"
    _err_on_duplicate: bool = True
    # _dependencies: Tuple = ("remote_states", "child_modules")

    index: int
    name: str
    prefix: Optional[str] = ""
    child_modules: Tuple[ChildModuleModel, ...]
    remote_states: Optional[Tuple[RemoteStateModel, ...]] = tuple()

    # The following field will not exist in the YAML file but rather initialized
    # with each DeploymentModel object instantiated inside the .create() method.
    # The idea is to have var names as keys and a tuple as their associated value:
    #   - the first element in the tuple holds the given name of the
    #     terraform_remote_state resource;
    #   - the second holds the name of an output that should be taken
    #     from the tfstate file pointed by that resource.
    remote_state_inputs_dict: HashableDictType = HashableDict()

    @classmethod
    def create_from_loaded_data(cls, data: List[Dict[str, Any]]) -> None:
        """
        For the case of DeploymentModel, we absolutely wait for a list of dicts with
        each containing data about one deployment
        """
        index = 0
        for deployment in data:
            deployment.update({"index": index})
            cls.create(dict_args=deployment)
            index += 1

    # noinspection PyTypeChecker
    @classmethod
    def create(cls, dict_args: Dict[str, Any], *args, **kwargs) -> "DeploymentModel":
        _child_modules = SortedSet()
        _remote_states = SortedSet()

        for cm in dict_args["child_modules"]:
            _child_modules.add(ChildModuleModel.get({"name": cm["name"]}))

            for rs in cm["remote_state_inputs"]:
                _remote_states.add(RemoteStateModel.get({"name": rs["remote_state"]}))

        dict_args.update(
            {
                "child_modules": tuple(_child_modules),
                "remote_states": tuple(_remote_states),
            }
        )

        new_model = super().create(dict_args=dict_args)
        new_model.set_remote_state_inputs_dict()
        return new_model

    def set_remote_state_inputs_dict(self):
        for cm in self.child_modules:
            for rsi in cm.remote_states_inputs:
                self.remote_state_inputs_dict[rsi.var.name] = (
                    rsi.output.remote_state.name,
                    rsi.output.name,
                )
