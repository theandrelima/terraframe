from sortedcontainers import SortedSet


class HashableDict(dict):

    def __hash__(self):
        return hash((frozenset(self), frozenset(self.values())))


class TerraframeSortedSet(SortedSet):

    def __init__(self, *args, **kwargs):
        super().__init__(key=lambda model_obj: model_obj.key, *args, **kwargs)
