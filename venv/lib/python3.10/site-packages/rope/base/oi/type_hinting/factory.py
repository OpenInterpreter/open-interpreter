from rope.base import utils
from rope.base.oi.type_hinting import interfaces
from rope.base.oi.type_hinting.providers import (
    composite,
    docstrings,
    inheritance,
    numpydocstrings,
    pep0484_type_comments,
)
from rope.base.oi.type_hinting.resolvers import composite as composite_resolvers
from rope.base.oi.type_hinting.resolvers import types


class TypeHintingFactory(interfaces.ITypeHintingFactory):
    @utils.saveit
    def make_param_provider(self):
        providers = [
            docstrings.ParamProvider(
                docstrings.DocstringParamParser(), self.make_resolver()
            ),
            docstrings.ParamProvider(
                numpydocstrings.NumPyDocstringParamParser(), self.make_resolver()
            ),
        ]
        return inheritance.ParamProvider(composite.ParamProvider(*providers))

    @utils.saveit
    def make_return_provider(self):
        providers = [
            docstrings.ReturnProvider(
                docstrings.DocstringReturnParser(), self.make_resolver()
            ),
        ]
        return inheritance.ReturnProvider(composite.ReturnProvider(*providers))

    @utils.saveit
    def make_assignment_provider(self):
        providers = [
            pep0484_type_comments.AssignmentProvider(self.make_resolver()),
            docstrings.AssignmentProvider(
                docstrings.DocstringParamParser(), self.make_resolver()
            ),
            docstrings.AssignmentProvider(
                numpydocstrings.NumPyDocstringParamParser(), self.make_resolver()
            ),
        ]
        return inheritance.AssignmentProvider(composite.AssignmentProvider(*providers))

    @utils.saveit
    def make_resolver(self):
        """
        :rtype: rope.base.oi.type_hinting.resolvers.interfaces.IResolver
        """
        resolvers = [
            types.Resolver(),
        ]
        return composite_resolvers.Resolver(*resolvers)


default_type_hinting_factory = TypeHintingFactory()


class TypeHintingFactoryAccessor:
    def __call__(self, project):
        """
        :type project: rope.base.project.Project
        :rtype: rope.base.oi.type_hinting.interfaces.ITypeHintingFactory
        """
        factory_location = project.get_prefs().get(
            "type_hinting_factory",
            "rope.base.oi.type_hinting.factory.default_type_hinting_factory",
        )
        return self._get_factory(factory_location)

    @utils.cached(10)
    def _get_factory(self, factory_location):
        """
        :type factory_location: str
        :rtype: rope.base.oi.type_hinting.interfaces.ITypeHintingFactory
        """
        return utils.resolve(factory_location)


get_type_hinting_factory = TypeHintingFactoryAccessor()
