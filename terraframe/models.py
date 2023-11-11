from typing import Optional, List, Dict, Any, Tuple, Union

import re
from pathlib import Path
from functools import total_ordering

from pydantic import BaseModel, ConfigDict
from jinja2 import Environment, FileSystemLoader, Template
from jinja2.exceptions import TemplateNotFound

from terraframe.custom_collections import TerraframeSortedSet
from terraframe.utils import get_all_variables_from_module, convert_nested_dict_to_hashabledict
from terraframe.store import TFModelsGlobalStore, get_shared_data_store
from terraframe.custom_collections import HashableDict
from sortedcontainers import SortedSet

#############################
### Base Model ###
#############################


@total_ordering
class TerraFrameBaseModel(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    _yaml_directive: str = None
    _data_store: TFModelsGlobalStore = get_shared_data_store()
    _key: Tuple = tuple(
        ["name"]
    )  # even though this class doesn't have a 'name' attr, most (if not all) child classes will.
    _err_on_duplicate: bool = False
    # _dependencies: Tuple = tuple()

    def __hash__(self):
        return hash((type(self),) + tuple(self.__dict__.values()))

    def __lt__(self, other):
        return self.key <= other.key

    def __eq__(self, other):
        return str(self) == str(other)

    @property
    def yaml_directive(self) -> str:
        return self._yaml_directive

    # @property
    # def data_store(self) -> TFModelsGlobalStore:
    #     return self._data_store

    @property
    def key(self) -> Tuple:
        # this is probably a little wrong: we are not return the actual cls._key attribute
        # but rather the objects (values) associated with attribute names listed in cls._key
        return tuple([getattr(self, attr) for attr in self._key])

    @classmethod
    def factory_for_yaml_data(
        cls, yaml_data: Union[Dict[str, Any], List[Dict[str, Any]]]
    ) -> None:
        if not isinstance(yaml_data, dict) and not isinstance(yaml_data, list):
            raise Exception(
                f"Data passed to {cls.__name__} must be of type 'dict' or 'list', but was {type(yaml_data)}"
            )

        if isinstance(yaml_data, list):
            for _dict in yaml_data:
                cls.create(dict_args=_dict)
            return

        cls.create(dict_args=yaml_data)

    @classmethod
    def ds(cls) -> TFModelsGlobalStore:
        # because _data_store is implicitly a 'pydantic.Fields.ModelPrivateAttr'
        # we have to use .get_default() method here.
        return cls._data_store.get_default()

    # @classmethod
    # def get_model_dependencies(cls):
    #     return cls._dependencies.get_default()

    @classmethod
    def create(
        cls, dict_args: Dict[Any, Any], *args, **kwargs
    ) -> "TerraFrameBaseModel":
        if cls == TerraFrameBaseModel:
            raise Exception("Cannot instantiate TerraFrameBaseModel directly")

        convert_nested_dict_to_hashabledict(dict_args)
        new_obj_model = cls.model_validate(dict_args, strict=True, *args, **kwargs)
        new_obj_model.ds().save(new_obj_model)
        return new_obj_model

    @classmethod
    def filter(cls, search_params: Dict[Any, Any]) -> TerraframeSortedSet:
        return cls.ds().filter(cls, search_params)

    @classmethod
    def get(cls, search_params: Dict[Any, Any]) -> "TerraFrameBaseModel":
        return cls.ds().get(cls, search_params)

    @classmethod
    def get_all(cls) -> TerraframeSortedSet:
        return cls.ds().get_all(cls)


#############################
### NON-Renderable Models ###
#############################


class ChildModuleOutputModel(TerraFrameBaseModel):
    """Stores data of a Child Module's output"""

    name: str
    remote_state: "RemoteStateModel"


#########################
### Renderable Models ###
#########################

# TODO: make this a config/setting
TEMPLATES_DIR = "terraframe/templates"


class RenderableModel(TerraFrameBaseModel):
    # noinspection PyTypeChecker
    @classmethod
    def create(cls, dict_args: Dict[Any, Any], *args, **kwargs) -> "RenderableModel":
        cls._set_template(**dict_args)
        return super().create(dict_args, *args, **kwargs)

    @classmethod
    def _set_template(cls, **kwargs):
        try:
            getattr(cls, "_template_name")
        except AttributeError:
            informed_template_name = kwargs.get("template_name")

            if informed_template_name:
                cls._template_name = informed_template_name

            else:
                splitted_cls_name = re.findall("[A-Z][^A-Z]*", cls.__name__)

                if "Model" in splitted_cls_name:
                    splitted_cls_name.remove("Model")

                cls._template_name = "_".join(splitted_cls_name).lower()

    @property
    def template_name(self):
        return self._template_name

    def get_rendered_str(self, extra_vars_dict: Optional[Dict[str, Any]] = None) -> str:
        if extra_vars_dict:
            _dict_to_render = dict(self)
            _dict_to_render.update(extra_vars_dict)
            return self._get_jinja_template().render(_dict_to_render)

        return self._get_jinja_template().render(dict(self))

    def _get_jinja_template(self) -> Template:
        # TODO: this needs to evolve to allow custom templates
        # the order should be: look first on user informed custom templates directory
        # if nothing is found, look at terraframe's package.
        env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))
        try:
            return env.get_template(f"{self.template_name}.j2")
        except TemplateNotFound as err:
            # TODO: custom exceptions
            raise err


class ChildModuleVarModel(RenderableModel):
    """Stores data of a Child Module's variable"""

    name: str
    type: Optional[str] = None
    description: Optional[str] = None

    _template_name: str = "variables"


class RemoteStatateInputModel(RenderableModel):
    """Identifies a variable that should take it's input from a specific output
    accessible via a `terraform_remote_state` resource"""

    _key: Tuple = ("var", "output")
    var: ChildModuleVarModel
    output: ChildModuleOutputModel


class RemoteStateModel(RenderableModel):
    _yaml_directive: str = "remote_states"

    name: str
    backend: str
    config: HashableDict


class ChildModuleModel(RenderableModel):
    _yaml_directive: str = "child_modules"
    name: str
    source: str
    child_module_vars: Tuple[ChildModuleVarModel, ...]
    remote_states_inputs: Tuple[RemoteStatateInputModel, ...] = tuple()

    # noinspection PyTypeChecker
    @classmethod
    def create(cls, dict_args: Dict[str, Any], *args, **kwargs) -> "ChildModuleModel":
        # TODO: for better readability, abstract this code into functions in utils
        _child_module_vars = tuple(
            [
                ChildModuleVarModel.create(dict_args={"name": var})
                for var in get_all_variables_from_module(
                    Path(dict_args["source"]).absolute()
                )
            ]
        )

        _remote_states_inputs = tuple(
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
                for rs_input in dict_args["remote_state_inputs"]
            ]
        )

        dict_args.update(
            {
                "child_module_vars": _child_module_vars,
                "remote_states_inputs": _remote_states_inputs,
            }
        )

        return super().create(dict_args=dict_args, *args, **kwargs)


class DeploymentModel(RenderableModel):
    _key: Tuple = ("index", "name")
    _yaml_directive: str = "deployments"
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
    remote_state_inputs_dict: HashableDict = HashableDict()

    @classmethod
    def factory_for_yaml_data(cls, yaml_data: List[Dict[str, Any]]) -> None:
        """
        For the case of DeploymentModel, we absolutely wait for a list of dicts with
        each containing data about one deployment
        """
        index = 0
        for deployment in yaml_data:
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
