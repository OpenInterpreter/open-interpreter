from __future__ import annotations

import dataclasses

from typing import Optional
from typing import Sequence
from typing import Tuple
from typing import Union


# Release phase IDs according to PEP440
RELEASE_PHASE_ID_ALPHA = "a"
RELEASE_PHASE_ID_BETA = "b"
RELEASE_PHASE_ID_RC = "rc"
RELEASE_PHASE_ID_POST = "post"
RELEASE_PHASE_ID_DEV = "dev"

RELEASE_PHASE_SPELLINGS = {
    RELEASE_PHASE_ID_ALPHA: {RELEASE_PHASE_ID_ALPHA, "alpha"},
    RELEASE_PHASE_ID_BETA: {RELEASE_PHASE_ID_BETA, "beta"},
    RELEASE_PHASE_ID_RC: {RELEASE_PHASE_ID_RC, "c", "pre", "preview"},
    RELEASE_PHASE_ID_POST: {RELEASE_PHASE_ID_POST, "r", "rev", "-"},
    RELEASE_PHASE_ID_DEV: {RELEASE_PHASE_ID_DEV},
}
RELEASE_PHASE_NORMALIZATIONS = {
    s: id_ for id_, spellings in RELEASE_PHASE_SPELLINGS.items() for s in spellings
}


@dataclasses.dataclass(frozen=True, eq=True, order=True)
class Release:
    major: int = dataclasses.field(default=0, compare=False)
    minor: int | None = dataclasses.field(default=None, compare=False)
    patch: int | None = dataclasses.field(default=None, compare=False)
    # some projects use non-semver versioning schemes, eg: 1.2.3.4
    extra: tuple[int, ...] = dataclasses.field(default=(), compare=False)
    precision: int = dataclasses.field(init=False, compare=False)
    text: str = dataclasses.field(init=False, compare=False)
    _compare_key: tuple[int, ...] = dataclasses.field(init=False, compare=True)

    def __post_init__(self) -> None:
        if self.extra:
            if self.minor is None:
                object.__setattr__(self, "minor", 0)
            if self.patch is None:
                object.__setattr__(self, "patch", 0)
        parts = [
            str(part)
            for part in (self.major, self.minor, self.patch, *self.extra)
            if part is not None
        ]
        object.__setattr__(self, "text", ".".join(parts))
        object.__setattr__(self, "precision", len(parts))

        compare_key = [self.major, self.minor or 0, self.patch or 0, *self.extra]
        while compare_key and compare_key[-1] == 0:
            del compare_key[-1]
        object.__setattr__(self, "_compare_key", tuple(compare_key))

    @classmethod
    def from_parts(cls, *parts: int) -> Release:
        if not parts:
            return cls()

        return cls(
            major=parts[0],
            minor=parts[1] if len(parts) > 1 else None,
            patch=parts[2] if len(parts) > 2 else None,
            extra=parts[3:],
        )

    def to_parts(self) -> Sequence[int]:
        return tuple(
            part
            for part in [self.major, self.minor, self.patch, *self.extra]
            if part is not None
        )

    def to_string(self) -> str:
        return self.text

    def next_major(self) -> Release:
        return dataclasses.replace(
            self,
            major=self.major + 1,
            minor=0 if self.minor is not None else None,
            patch=0 if self.patch is not None else None,
            extra=tuple(0 for _ in self.extra),
        )

    def next_minor(self) -> Release:
        return dataclasses.replace(
            self,
            major=self.major,
            minor=self.minor + 1 if self.minor is not None else 1,
            patch=0 if self.patch is not None else None,
            extra=tuple(0 for _ in self.extra),
        )

    def next_patch(self) -> Release:
        return dataclasses.replace(
            self,
            major=self.major,
            minor=self.minor if self.minor is not None else 0,
            patch=self.patch + 1 if self.patch is not None else 1,
            extra=tuple(0 for _ in self.extra),
        )

    def next(self) -> Release:
        if self.precision == 1:
            return self.next_major()

        if self.precision == 2:
            return self.next_minor()

        if self.precision == 3:
            return self.next_patch()

        return dataclasses.replace(
            self,
            major=self.major,
            minor=self.minor,
            patch=self.patch,
            extra=(*self.extra[:-1], self.extra[-1] + 1),
        )


@dataclasses.dataclass(frozen=True, eq=True, order=True)
class ReleaseTag:
    phase: str
    number: int = dataclasses.field(default=0)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "phase", RELEASE_PHASE_NORMALIZATIONS.get(self.phase, self.phase)
        )

    def to_string(self, short: bool = False) -> str:
        if short:
            import warnings

            warnings.warn(
                (
                    "Parameter 'short' has no effect and will be removed. "
                    "(Release tags are always normalized according to PEP 440 now.)"
                ),
                DeprecationWarning,
                stacklevel=2,
            )

        return f"{self.phase}{self.number}"

    def next(self) -> ReleaseTag:
        return dataclasses.replace(self, phase=self.phase, number=self.number + 1)

    def next_phase(self) -> ReleaseTag | None:
        if self.phase in [
            RELEASE_PHASE_ID_POST,
            RELEASE_PHASE_ID_RC,
            RELEASE_PHASE_ID_DEV,
        ]:
            return None

        if self.phase == RELEASE_PHASE_ID_ALPHA:
            _phase = RELEASE_PHASE_ID_BETA
        elif self.phase == RELEASE_PHASE_ID_BETA:
            _phase = RELEASE_PHASE_ID_RC
        else:
            return None

        return self.__class__(phase=_phase, number=0)


LocalSegmentType = Optional[Union[str, int, Tuple[Union[str, int], ...]]]
