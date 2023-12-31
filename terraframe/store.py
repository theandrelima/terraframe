from typing import Any, Optional, Dict, Type, TYPE_CHECKING

from functools import cache
from collections import defaultdict
from terraframe.custom_collections import TerraframeSortedSet

if TYPE_CHECKING:
    from models import TerraFrameBaseModel


class TFModelsGlobalStore:
    _records = defaultdict(TerraframeSortedSet)

    @property
    def records(self) -> defaultdict[TerraframeSortedSet]:
        return self._records

    @records.setter
    def records(self, _):
        raise Exception(
            "Cannot directly assign to attribute 'records' of a TFModelsGlobalStore object."
        )

    def save(self, obj) -> None:
        if obj in self.records[obj.__class__] and obj._err_on_duplicate:
            raise Exception(
                f"{obj.__class__.__name__}: duplicates not allowed. Make sure there's no other {obj.__class__.__name__} with fields {obj._key} associated with values {obj.key}, respectively."
            )
        self.records[obj.__class__].add(obj)

    def _search(
        self,
        obj_class: Type["TerraFrameBaseModel"],
        search_params: Optional[Dict[Any, Any]] = None,
    ) -> TerraframeSortedSet:
        if search_params:
            # we only take the first k,v pair from search_params
            search_k, value = list(search_params.items())[0]
            return TerraframeSortedSet(
                [x for x in self.records[obj_class] if getattr(x, search_k) == value]
            )

        return self.records[obj_class]

    def filter(
        self, obj_class: Type["TerraFrameBaseModel"], search_params: Dict[Any, Any]
    ) -> TerraframeSortedSet:
        return self._search(obj_class, search_params)

    def get(
        self, obj_class: Type["TerraFrameBaseModel"], search_params: Dict[Any, Any]
    ) -> "TerraFrameBaseModel":
        search = self.filter(obj_class, search_params)

        # TODO: custome exceptions
        if not search:
            raise Exception(
                f"A {obj_class.__name__} object was not found matching params: {search_params}"
            )

        if len(search) > 1:
            raise Exception("More than one element found")

        return search[0]

    def get_all(self, obj_class: Type["TerraFrameBaseModel"]) -> TerraframeSortedSet:
        return self._search(obj_class)


SHARED_DATA_STORE = None


@cache
def get_shared_data_store():
    global SHARED_DATA_STORE

    if SHARED_DATA_STORE is None:
        SHARED_DATA_STORE = TFModelsGlobalStore()

    return SHARED_DATA_STORE
