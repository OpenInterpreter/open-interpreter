__version__: str

from .providers import (
    AbstractResolver as AbstractResolver,
    AbstractProvider as AbstractProvider,
)
from .reporters import BaseReporter as BaseReporter
from .resolvers import (
    InconsistentCandidate as InconsistentCandidate,
    RequirementsConflicted as RequirementsConflicted,
    Resolver as Resolver,
    ResolutionError as ResolutionError,
    ResolutionImpossible as ResolutionImpossible,
    ResolutionTooDeep as ResolutionTooDeep,
)
