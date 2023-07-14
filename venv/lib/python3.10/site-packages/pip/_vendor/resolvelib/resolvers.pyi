from typing import (
    Collection,
    Generic,
    Iterable,
    Iterator,
    List,
    Mapping,
    Optional,
)

from .providers import AbstractProvider, AbstractResolver
from .structs import (
    CT,
    KT,
    RT,
    DirectedGraph,
    IterableView,
)

# This should be a NamedTuple, but Python 3.6 has a bug that prevents it.
# https://stackoverflow.com/a/50531189/1376863
class RequirementInformation(tuple, Generic[RT, CT]):
    requirement: RT
    parent: Optional[CT]

class Criterion(Generic[RT, CT, KT]):
    candidates: IterableView[CT]
    information: Collection[RequirementInformation[RT, CT]]
    incompatibilities: List[CT]
    @classmethod
    def from_requirement(
        cls,
        provider: AbstractProvider[RT, CT, KT],
        requirement: RT,
        parent: Optional[CT],
    ) -> Criterion[RT, CT, KT]: ...
    def iter_requirement(self) -> Iterator[RT]: ...
    def iter_parent(self) -> Iterator[Optional[CT]]: ...
    def merged_with(
        self,
        provider: AbstractProvider[RT, CT, KT],
        requirement: RT,
        parent: Optional[CT],
    ) -> Criterion[RT, CT, KT]: ...
    def excluded_of(self, candidates: List[CT]) -> Criterion[RT, CT, KT]: ...

class ResolverException(Exception): ...

class RequirementsConflicted(ResolverException, Generic[RT, CT, KT]):
    criterion: Criterion[RT, CT, KT]

class ResolutionError(ResolverException): ...

class InconsistentCandidate(ResolverException, Generic[RT, CT, KT]):
    candidate: CT
    criterion: Criterion[RT, CT, KT]

class ResolutionImpossible(ResolutionError, Generic[RT, CT]):
    causes: List[RequirementInformation[RT, CT]]

class ResolutionTooDeep(ResolutionError):
    round_count: int

class Result(Generic[RT, CT, KT]):
    mapping: Mapping[KT, CT]
    graph: DirectedGraph[Optional[KT]]
    criteria: Mapping[KT, Criterion[RT, CT, KT]]

class Resolver(AbstractResolver, Generic[RT, CT, KT]):
    base_exception = ResolverException
    def resolve(
        self, requirements: Iterable[RT], max_rounds: int = 100
    ) -> Result[RT, CT, KT]: ...
