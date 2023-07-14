from typing import (
    Any,
    Collection,
    Generic,
    Iterable,
    Iterator,
    Mapping,
    Optional,
    Protocol,
    Union,
)

from .reporters import BaseReporter
from .resolvers import RequirementInformation
from .structs import KT, RT, CT, Matches

class Preference(Protocol):
    def __lt__(self, __other: Any) -> bool: ...

class AbstractProvider(Generic[RT, CT, KT]):
    def identify(self, requirement_or_candidate: Union[RT, CT]) -> KT: ...
    def get_preference(
        self,
        identifier: KT,
        resolutions: Mapping[KT, CT],
        candidates: Mapping[KT, Iterator[CT]],
        information: Mapping[KT, Iterator[RequirementInformation[RT, CT]]],
    ) -> Preference: ...
    def find_matches(
        self,
        identifier: KT,
        requirements: Mapping[KT, Iterator[RT]],
        incompatibilities: Mapping[KT, Iterator[CT]],
    ) -> Matches: ...
    def is_satisfied_by(self, requirement: RT, candidate: CT) -> bool: ...
    def get_dependencies(self, candidate: CT) -> Iterable[RT]: ...

class AbstractResolver(Generic[RT, CT, KT]):
    base_exception = Exception
    provider: AbstractProvider[RT, CT, KT]
    reporter: BaseReporter
    def __init__(
        self, provider: AbstractProvider[RT, CT, KT], reporter: BaseReporter
    ): ...
