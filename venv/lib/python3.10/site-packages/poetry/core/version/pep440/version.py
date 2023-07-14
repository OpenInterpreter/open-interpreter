from __future__ import annotations

import dataclasses
import functools
import warnings

from typing import TYPE_CHECKING
from typing import Any
from typing import Sequence
from typing import TypeVar

from poetry.core.version.pep440.segments import RELEASE_PHASE_ID_ALPHA
from poetry.core.version.pep440.segments import RELEASE_PHASE_ID_DEV
from poetry.core.version.pep440.segments import RELEASE_PHASE_ID_POST
from poetry.core.version.pep440.segments import Release
from poetry.core.version.pep440.segments import ReleaseTag


if TYPE_CHECKING:
    from poetry.core.version.pep440.segments import LocalSegmentType


@functools.total_ordering
class AlwaysSmaller:
    def __lt__(self, other: object) -> bool:
        return True


@functools.total_ordering
class AlwaysGreater:
    def __gt__(self, other: object) -> bool:
        return True


class Infinity(AlwaysGreater, int):
    pass


class NegativeInfinity(AlwaysSmaller, int):
    pass


T = TypeVar("T", bound="PEP440Version")

# we use the phase "z" to ensure we always sort this after other phases
_INF_TAG = ReleaseTag("z", Infinity())
# we use the phase "" to ensure we always sort this before other phases
_NEG_INF_TAG = ReleaseTag("", NegativeInfinity())


@dataclasses.dataclass(frozen=True, eq=True, order=True)
class PEP440Version:
    epoch: int = dataclasses.field(default=0, compare=False)
    release: Release = dataclasses.field(default_factory=Release, compare=False)
    pre: ReleaseTag | None = dataclasses.field(default=None, compare=False)
    post: ReleaseTag | None = dataclasses.field(default=None, compare=False)
    dev: ReleaseTag | None = dataclasses.field(default=None, compare=False)
    local: LocalSegmentType = dataclasses.field(default=None, compare=False)
    text: str = dataclasses.field(default="", compare=False)
    _compare_key: tuple[
        int, Release, ReleaseTag, ReleaseTag, ReleaseTag, tuple[int | str, ...]
    ] = dataclasses.field(init=False, compare=True)

    def __post_init__(self) -> None:
        if self.local is not None and not isinstance(self.local, tuple):
            object.__setattr__(self, "local", (self.local,))

        if isinstance(self.release, tuple):
            object.__setattr__(self, "release", Release(*self.release))

        # we do this here to handle both None and tomlkit string values
        object.__setattr__(
            self, "text", self.to_string() if not self.text else str(self.text)
        )

        object.__setattr__(self, "_compare_key", self._make_compare_key())

    def _make_compare_key(
        self,
    ) -> tuple[
        int,
        Release,
        ReleaseTag,
        ReleaseTag,
        ReleaseTag,
        tuple[tuple[int, int | str], ...],
    ]:
        """
        This code is based on the implementation of packaging.version._cmpkey(..)
        """
        # We need to "trick" the sorting algorithm to put 1.0.dev0 before 1.0a0.
        # We'll do this by abusing the pre segment, but we _only_ want to do this
        # if there is not a pre or a post segment. If we have one of those then
        # the normal sorting rules will handle this case correctly.
        if self.pre is None and self.post is None and self.dev is not None:
            _pre = _NEG_INF_TAG
        # Versions without a pre-release (except as noted above) should sort after
        # those with one.
        elif self.pre is None:
            _pre = _INF_TAG
        else:
            _pre = self.pre

        # Versions without a post segment should sort before those with one.
        _post = _NEG_INF_TAG if self.post is None else self.post

        # Versions without a development segment should sort after those with one.
        _dev = _INF_TAG if self.dev is None else self.dev

        _local: tuple[tuple[int, int | str], ...]
        if self.local is None:
            # Versions without a local segment should sort before those with one.
            _local = ((NegativeInfinity(), ""),)
        else:
            # Versions with a local segment need that segment parsed to implement
            # the sorting rules in PEP440.
            # - Alpha numeric segments sort before numeric segments
            # - Alpha numeric segments sort lexicographically
            # - Numeric segments sort numerically
            # - Shorter versions sort before longer versions when the prefixes
            #   match exactly
            assert isinstance(self.local, tuple)
            # We convert strings that are integers so that they can be compared
            _local = tuple(
                (int(i), "") if str(i).isnumeric() else (NegativeInfinity(), i)
                for i in self.local
            )
        return self.epoch, self.release, _pre, _post, _dev, _local

    @property
    def major(self) -> int:
        return self.release.major

    @property
    def minor(self) -> int | None:
        return self.release.minor

    @property
    def patch(self) -> int | None:
        return self.release.patch

    @property
    def non_semver_parts(self) -> Sequence[int]:
        return self.release.extra

    @property
    def parts(self) -> Sequence[int]:
        return self.release.to_parts()

    def to_string(self, short: bool = False) -> str:
        if short:
            import warnings

            warnings.warn(
                (
                    "Parameter 'short' has no effect and will be removed. "
                    "(Versions are always normalized according to PEP 440 now.)"
                ),
                DeprecationWarning,
                stacklevel=2,
            )

        version_string = self.release.to_string()

        if self.epoch:
            # if epoch is non-zero we should include it
            version_string = f"{self.epoch}!{version_string}"

        if self.pre:
            version_string += self.pre.to_string()

        if self.post:
            version_string = f"{version_string}.{self.post.to_string()}"

        if self.dev:
            version_string = f"{version_string}.{self.dev.to_string()}"

        if self.local:
            assert isinstance(self.local, tuple)
            version_string += "+" + ".".join(map(str, self.local))

        return version_string.lower()

    @classmethod
    def parse(cls: type[T], value: str) -> T:
        from poetry.core.version.pep440.parser import parse_pep440

        return parse_pep440(value, cls)

    def is_prerelease(self) -> bool:
        return self.pre is not None

    def is_postrelease(self) -> bool:
        return self.post is not None

    def is_devrelease(self) -> bool:
        return self.dev is not None

    def is_local(self) -> bool:
        return self.local is not None

    def is_no_suffix_release(self) -> bool:
        return not (self.pre or self.post or self.dev)

    def is_unstable(self) -> bool:
        return self.is_prerelease() or self.is_devrelease()

    def is_stable(self) -> bool:
        return not self.is_unstable()

    def _is_increment_required(self) -> bool:
        return self.is_stable() or (not self.is_prerelease() and self.is_postrelease())

    def next_major(self: T) -> T:
        release = self.release
        if self._is_increment_required() or Release(release.major, 0, 0) < release:
            release = release.next_major()
        return self.__class__(epoch=self.epoch, release=release)

    def next_minor(self: T) -> T:
        release = self.release
        if (
            self._is_increment_required()
            or Release(release.major, release.minor, 0) < release
        ):
            release = release.next_minor()
        return self.__class__(epoch=self.epoch, release=release)

    def next_patch(self: T) -> T:
        release = self.release
        if (
            self._is_increment_required()
            or Release(release.major, release.minor, release.patch) < release
        ):
            release = release.next_patch()
        return self.__class__(epoch=self.epoch, release=release)

    def next_stable(self: T) -> T:
        release = self.release.next() if self.is_stable() else self.release
        return self.__class__(epoch=self.epoch, release=release, local=self.local)

    def next_prerelease(self: T, next_phase: bool = False) -> T:
        if self.is_stable():
            warnings.warn(
                (
                    "Calling next_prerelease() on a stable release is deprecated for"
                    " its ambiguity. Use next_major(), next_minor(), etc. together with"
                    " first_prerelease()"
                ),
                DeprecationWarning,
                stacklevel=2,
            )
        if self.is_prerelease():
            assert self.pre is not None
            if not self.is_devrelease() or self.is_postrelease():
                pre = self.pre.next_phase() if next_phase else self.pre.next()
            else:
                pre = self.pre
        else:
            pre = ReleaseTag(RELEASE_PHASE_ID_ALPHA)
        return self.__class__(epoch=self.epoch, release=self.release, pre=pre)

    def next_postrelease(self: T) -> T:
        if self.is_postrelease():
            assert self.post is not None
            post = self.post.next() if self.dev is None else self.post
        else:
            post = ReleaseTag(RELEASE_PHASE_ID_POST)
        return self.__class__(
            epoch=self.epoch,
            release=self.release,
            pre=self.pre,
            post=post,
        )

    def next_devrelease(self: T) -> T:
        if self.is_devrelease():
            assert self.dev is not None
            dev = self.dev.next()
        else:
            warnings.warn(
                (
                    "Calling next_devrelease() on a non dev release is deprecated for"
                    " its ambiguity. Use next_major(), next_minor(), etc. together with"
                    " first_devrelease()"
                ),
                DeprecationWarning,
                stacklevel=2,
            )
            dev = ReleaseTag(RELEASE_PHASE_ID_DEV)
        return self.__class__(
            epoch=self.epoch,
            release=self.release,
            pre=self.pre,
            post=self.post,
            dev=dev,
        )

    def first_prerelease(self: T) -> T:
        return self.__class__(
            epoch=self.epoch,
            release=self.release,
            pre=ReleaseTag(RELEASE_PHASE_ID_ALPHA),
        )

    def first_devrelease(self: T) -> T:
        return self.__class__(
            epoch=self.epoch,
            release=self.release,
            pre=self.pre,
            post=self.post,
            dev=ReleaseTag(RELEASE_PHASE_ID_DEV),
        )

    def replace(self: T, **kwargs: Any) -> T:
        return self.__class__(
            **{
                **{
                    k: getattr(self, k)
                    for k in self.__dataclass_fields__
                    if k not in ("_compare_key", "text")
                },  # setup defaults with current values, excluding compare keys and text  # noqa: E501
                **kwargs,  # keys to replace
            }
        )

    def without_local(self: T) -> T:
        return self.replace(local=None)

    def without_postrelease(self: T) -> T:
        if self.is_postrelease():
            return self.replace(post=None, dev=None)
        return self

    def without_devrelease(self: T) -> T:
        return self.replace(dev=None)
