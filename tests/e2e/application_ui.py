"""Product API inventory beside external desktop providers in installed tests."""

try:
    from application_ui_support import ApplicationUI, ApplicationNode, PRODUCT_APPLICATIONS, UIClientError
except ImportError:
    from tests.support.application_ui import ApplicationUI, ApplicationNode, PRODUCT_APPLICATIONS, UIClientError


class InterfaceCalls:
    """Preserve the shared reader's interface syntax with polymorphic dispatch."""

    def __getattr__(self, operation):
        return lambda node, *args: getattr(node, operation)(*args)


class Desktop:
    """A read boundary containing product API inventories and external providers."""

    def __init__(self, external, catalog, ownership):
        self.external, self.catalog, self.ownership = external, catalog, ownership
        self.children = None

    def _children(self):
        if self.children is None:
            external = []
            for index in range(self.external.get_child_count()):
                node = self.external.get_child_at_index(index)
                if node is None:
                    from public_atspi import IncompleteTree
                    raise IncompleteTree('ui:incomplete-tree')
                if node.get_accessible_id() not in PRODUCT_APPLICATIONS:
                    external.append(node)
            self.children = external + self.catalog.applications(**self.ownership)
        return self.children

    def get_child_count(self):
        return len(self._children())

    def get_child_at_index(self, index):
        return self._children()[index]

    def __getattr__(self, name):
        return getattr(self.external, name)

    def __eq__(self, other):
        return self.external == (other.external if isinstance(other, Desktop) else other)

    def __hash__(self):
        return hash(self.external)
