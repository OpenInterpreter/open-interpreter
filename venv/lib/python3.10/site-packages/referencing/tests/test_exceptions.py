import itertools

import pytest

from referencing import Resource, exceptions


def pairs(*choices):
    return itertools.combinations(choices, 2)


@pytest.mark.parametrize(
    "one, two",
    pairs(
        exceptions.NoSuchResource("urn:example:foo"),
        exceptions.NoInternalID(Resource.opaque({})),
        exceptions.Unresolvable("urn:example:foo"),
    ),
)
def test_eq_incompatible_types(one, two):
    assert one != two
