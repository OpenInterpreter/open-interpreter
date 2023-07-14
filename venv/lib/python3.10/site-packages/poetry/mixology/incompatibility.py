from typing import Dict
from typing import Generator
from typing import List

from .incompatibility_cause import ConflictCause
from .incompatibility_cause import DependencyCause
from .incompatibility_cause import IncompatibilityCause
from .incompatibility_cause import NoVersionsCause
from .incompatibility_cause import PackageNotFoundCause
from .incompatibility_cause import PlatformCause
from .incompatibility_cause import PythonCause
from .incompatibility_cause import RootCause
from .term import Term


class Incompatibility:
    def __init__(
        self, terms, cause
    ):  # type: (List[Term], IncompatibilityCause) -> None
        # Remove the root package from generated incompatibilities, since it will
        # always be satisfied. This makes error reporting clearer, and may also
        # make solving more efficient.
        if (
            len(terms) != 1
            and isinstance(cause, ConflictCause)
            and any([term.is_positive() and term.dependency.is_root for term in terms])
        ):
            terms = [
                term
                for term in terms
                if not term.is_positive() or not term.dependency.is_root
            ]

        if (
            len(terms) == 1
            # Short-circuit in the common case of a two-term incompatibility with
            # two different packages (for example, a dependency).
            or len(terms) == 2
            and terms[0].dependency.complete_name != terms[-1].dependency.complete_name
        ):
            pass
        else:
            # Coalesce multiple terms about the same package if possible.
            by_name = {}  # type: Dict[str, Dict[str, Term]]
            for term in terms:
                if term.dependency.complete_name not in by_name:
                    by_name[term.dependency.complete_name] = {}

                by_ref = by_name[term.dependency.complete_name]
                ref = term.dependency.complete_name

                if ref in by_ref:
                    by_ref[ref] = by_ref[ref].intersect(term)

                    # If we have two terms that refer to the same package but have a null
                    # intersection, they're mutually exclusive, making this incompatibility
                    # irrelevant, since we already know that mutually exclusive version
                    # ranges are incompatible. We should never derive an irrelevant
                    # incompatibility.
                    assert by_ref[ref] is not None
                else:
                    by_ref[ref] = term

            new_terms = []
            for by_ref in by_name.values():
                positive_terms = [
                    term for term in by_ref.values() if term.is_positive()
                ]
                if positive_terms:
                    new_terms += positive_terms
                    continue

                new_terms += list(by_ref.values())

            terms = new_terms

        self._terms = terms
        self._cause = cause

    @property
    def terms(self):  # type: () -> List[Term]
        return self._terms

    @property
    def cause(self):  # type: () -> IncompatibilityCause
        return self._cause

    @property
    def external_incompatibilities(self):  # type: () -> Generator[Incompatibility]
        """
        Returns all external incompatibilities in this incompatibility's
        derivation graph.
        """
        if isinstance(self._cause, ConflictCause):
            cause = self._cause  # type: ConflictCause
            for incompatibility in cause.conflict.external_incompatibilities:
                yield incompatibility

            for incompatibility in cause.other.external_incompatibilities:
                yield incompatibility
        else:
            yield self

    def is_failure(self):  # type: () -> bool
        return len(self._terms) == 0 or (
            len(self._terms) == 1 and self._terms[0].dependency.is_root
        )

    def __str__(self):
        if isinstance(self._cause, DependencyCause):
            assert len(self._terms) == 2

            depender = self._terms[0]
            dependee = self._terms[1]
            assert depender.is_positive()
            assert not dependee.is_positive()

            return "{} depends on {}".format(
                self._terse(depender, allow_every=True), self._terse(dependee)
            )
        elif isinstance(self._cause, PythonCause):
            assert len(self._terms) == 1
            assert self._terms[0].is_positive()

            cause = self._cause  # type: PythonCause
            text = "{} requires ".format(self._terse(self._terms[0], allow_every=True))
            text += "Python {}".format(cause.python_version)

            return text
        elif isinstance(self._cause, PlatformCause):
            assert len(self._terms) == 1
            assert self._terms[0].is_positive()

            cause = self._cause  # type: PlatformCause
            text = "{} requires ".format(self._terse(self._terms[0], allow_every=True))
            text += "platform {}".format(cause.platform)

            return text
        elif isinstance(self._cause, NoVersionsCause):
            assert len(self._terms) == 1
            assert self._terms[0].is_positive()

            return "no versions of {} match {}".format(
                self._terms[0].dependency.name, self._terms[0].constraint
            )
        elif isinstance(self._cause, PackageNotFoundCause):
            assert len(self._terms) == 1
            assert self._terms[0].is_positive()

            return "{} doesn't exist".format(self._terms[0].dependency.name)
        elif isinstance(self._cause, RootCause):
            assert len(self._terms) == 1
            assert not self._terms[0].is_positive()
            assert self._terms[0].dependency.is_root

            return "{} is {}".format(
                self._terms[0].dependency.name, self._terms[0].dependency.constraint
            )
        elif self.is_failure():
            return "version solving failed"

        if len(self._terms) == 1:
            term = self._terms[0]
            if term.constraint.is_any():
                return "{} is {}".format(
                    term.dependency.name,
                    "forbidden" if term.is_positive() else "required",
                )
            else:
                return "{} is {}".format(
                    term.dependency.name,
                    "forbidden" if term.is_positive() else "required",
                )

        if len(self._terms) == 2:
            term1 = self._terms[0]
            term2 = self._terms[1]

            if term1.is_positive() == term2.is_positive():
                if term1.is_positive():
                    package1 = (
                        term1.dependency.name
                        if term1.constraint.is_any()
                        else self._terse(term1)
                    )
                    package2 = (
                        term2.dependency.name
                        if term2.constraint.is_any()
                        else self._terse(term2)
                    )

                    return "{} is incompatible with {}".format(package1, package2)
                else:
                    return "either {} or {}".format(
                        self._terse(term1), self._terse(term2)
                    )

        positive = []
        negative = []

        for term in self._terms:
            if term.is_positive():
                positive.append(self._terse(term))
            else:
                negative.append(self._terse(term))

        if positive and negative:
            if len(positive) == 1:
                positive_term = [term for term in self._terms if term.is_positive()][0]

                return "{} requires {}".format(
                    self._terse(positive_term, allow_every=True), " or ".join(negative)
                )
            else:
                return "if {} then {}".format(
                    " and ".join(positive), " or ".join(negative)
                )
        elif positive:
            return "one of {} must be false".format(" or ".join(positive))
        else:
            return "one of {} must be true".format(" or ".join(negative))

    def and_to_string(
        self, other, details, this_line, other_line
    ):  # type: (Incompatibility, dict, int, int) -> str
        requires_both = self._try_requires_both(other, details, this_line, other_line)
        if requires_both is not None:
            return requires_both

        requires_through = self._try_requires_through(
            other, details, this_line, other_line
        )
        if requires_through is not None:
            return requires_through

        requires_forbidden = self._try_requires_forbidden(
            other, details, this_line, other_line
        )
        if requires_forbidden is not None:
            return requires_forbidden

        buffer = [str(self)]
        if this_line is not None:
            buffer.append(" " + str(this_line))

        buffer.append(" and {}".format(str(other)))

        if other_line is not None:
            buffer.append(" " + str(other_line))

        return "\n".join(buffer)

    def _try_requires_both(
        self, other, details, this_line, other_line
    ):  # type: (Incompatibility, dict, int, int) -> str
        if len(self._terms) == 1 or len(other.terms) == 1:
            return

        this_positive = self._single_term_where(lambda term: term.is_positive())
        if this_positive is None:
            return

        other_positive = other._single_term_where(lambda term: term.is_positive())
        if other_positive is None:
            return

        if this_positive.dependency != other_positive.dependency:
            return

        this_negatives = " or ".join(
            [self._terse(term) for term in self._terms if not term.is_positive()]
        )

        other_negatives = " or ".join(
            [self._terse(term) for term in other.terms if not term.is_positive()]
        )

        buffer = [self._terse(this_positive, allow_every=True) + " "]
        is_dependency = isinstance(self.cause, DependencyCause) and isinstance(
            other.cause, DependencyCause
        )

        if is_dependency:
            buffer.append("depends on")
        else:
            buffer.append("requires")

        buffer.append(" both {}".format(this_negatives))
        if this_line is not None:
            buffer.append(" ({})".format(this_line))

        buffer.append(" and {}".format(other_negatives))

        if other_line is not None:
            buffer.append(" ({})".format(other_line))

        return "".join(buffer)

    def _try_requires_through(
        self, other, details, this_line, other_line
    ):  # type: (Incompatibility, dict, int, int) -> str
        if len(self._terms) == 1 or len(other.terms) == 1:
            return

        this_negative = self._single_term_where(lambda term: not term.is_positive())
        other_negative = other._single_term_where(lambda term: not term.is_positive())

        if this_negative is None and other_negative is None:
            return

        this_positive = self._single_term_where(lambda term: term.is_positive())
        other_positive = self._single_term_where(lambda term: term.is_positive())

        if (
            this_negative is not None
            and other_positive is not None
            and this_negative.dependency.name == other_positive.dependency.name
            and this_negative.inverse.satisfies(other_positive)
        ):
            prior = self
            prior_negative = this_negative
            prior_line = this_line
            latter = other
            latter_line = other_line
        elif (
            other_negative is not None
            and this_positive is not None
            and other_negative.dependency.name == this_positive.dependency.name
            and other_negative.inverse.satisfies(this_positive)
        ):
            prior = other
            prior_negative = other_negative
            prior_line = other_line
            latter = self
            latter_line = this_line
        else:
            return

        prior_positives = [term for term in prior.terms if term.is_positive()]

        buffer = []
        if len(prior_positives) > 1:
            prior_string = " or ".join([self._terse(term) for term in prior_positives])
            buffer.append("if {} then ".format(prior_string))
        else:
            if isinstance(prior.cause, DependencyCause):
                verb = "depends on"
            else:
                verb = "requires"

            buffer.append(
                "{} {} ".format(self._terse(prior_positives[0], allow_every=True), verb)
            )

        buffer.append(self._terse(prior_negative))
        if prior_line is not None:
            buffer.append(" ({})".format(prior_line))

        buffer.append(" which ")

        if isinstance(latter.cause, DependencyCause):
            buffer.append("depends on ")
        else:
            buffer.append("requires ")

        buffer.append(
            " or ".join(
                [self._terse(term) for term in latter.terms if not term.is_positive()]
            )
        )

        if latter_line is not None:
            buffer.append(" ({})".format(latter_line))

        return "".join(buffer)

    def _try_requires_forbidden(
        self, other, details, this_line, other_line
    ):  # type: (Incompatibility, dict, int, int) -> str
        if len(self._terms) != 1 and len(other.terms) != 1:
            return None

        if len(self.terms) == 1:
            prior = other
            latter = self
            prior_line = other_line
            latter_line = this_line
        else:
            prior = self
            latter = other
            prior_line = this_line
            latter_line = other_line

        negative = prior._single_term_where(lambda term: not term.is_positive())
        if negative is None:
            return

        if not negative.inverse.satisfies(latter.terms[0]):
            return

        positives = [t for t in prior.terms if t.is_positive()]

        buffer = []
        if len(positives) > 1:
            prior_string = " or ".join([self._terse(term) for term in positives])
            buffer.append("if {} then ".format(prior_string))
        else:
            buffer.append(self._terse(positives[0], allow_every=True))
            if isinstance(prior.cause, DependencyCause):
                buffer.append(" depends on ")
            else:
                buffer.append(" requires ")

        buffer.append(self._terse(latter.terms[0]) + " ")
        if prior_line is not None:
            buffer.append("({}) ".format(prior_line))

        if isinstance(latter.cause, PythonCause):
            cause = latter.cause  # type: PythonCause
            buffer.append("which requires Python {}".format(cause.python_version))
        elif isinstance(latter.cause, NoVersionsCause):
            buffer.append("which doesn't match any versions")
        elif isinstance(latter.cause, PackageNotFoundCause):
            buffer.append("which doesn't exist")
        else:
            buffer.append("which is forbidden")

        if latter_line is not None:
            buffer.append(" ({})".format(latter_line))

        return "".join(buffer)

    def _terse(self, term, allow_every=False):
        if allow_every and term.constraint.is_any():
            return "every version of {}".format(term.dependency.complete_name)

        if term.dependency.is_root:
            return term.dependency.pretty_name

        return "{} ({})".format(
            term.dependency.pretty_name, term.dependency.pretty_constraint
        )

    def _single_term_where(self, callable):  # type: (callable) -> Term
        found = None
        for term in self._terms:
            if not callable(term):
                continue

            if found is not None:
                return

            found = term

        return found

    def __repr__(self):
        return "<Incompatibility {}>".format(str(self))
