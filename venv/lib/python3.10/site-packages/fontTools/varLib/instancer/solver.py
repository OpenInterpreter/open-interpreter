from fontTools.varLib.models import supportScalar, normalizeValue
from fontTools.misc.fixedTools import MAX_F2DOT14
from functools import lru_cache

__all__ = ["rebaseTent"]

EPSILON = 1 / (1 << 14)


def _reverse_negate(v):
    return (-v[2], -v[1], -v[0])


def _solve(tent, axisLimit, negative=False):
    axisMin, axisDef, axisMax = axisLimit
    lower, peak, upper = tent

    # Mirror the problem such that axisDef <= peak
    if axisDef > peak:
        return [
            (scalar, _reverse_negate(t) if t is not None else None)
            for scalar, t in _solve(
                _reverse_negate(tent), _reverse_negate(axisLimit), not negative
            )
        ]
    # axisDef <= peak

    # case 1: The whole deltaset falls outside the new limit; we can drop it
    #
    #                                          peak
    #  1.........................................o..........
    #                                           / \
    #                                          /   \
    #                                         /     \
    #                                        /       \
    #  0---|-----------|----------|-------- o         o----1
    #    axisMin     axisDef    axisMax   lower     upper
    #
    if axisMax <= lower and axisMax < peak:
        return []  # No overlap

    # case 2: Only the peak and outermost bound fall outside the new limit;
    # we keep the deltaset, update peak and outermost bound and and scale deltas
    # by the scalar value for the restricted axis at the new limit, and solve
    # recursively.
    #
    #                                  |peak
    #  1...............................|.o..........
    #                                  |/ \
    #                                  /   \
    #                                 /|    \
    #                                / |     \
    #  0--------------------------- o  |      o----1
    #                           lower  |      upper
    #                                  |
    #                                axisMax
    #
    # Convert to:
    #
    #  1............................................
    #                                  |
    #                                  o peak
    #                                 /|
    #                                /x|
    #  0--------------------------- o  o upper ----1
    #                           lower  |
    #                                  |
    #                                axisMax
    if axisMax < peak:
        mult = supportScalar({"tag": axisMax}, {"tag": tent})
        tent = (lower, axisMax, axisMax)
        return [(scalar * mult, t) for scalar, t in _solve(tent, axisLimit)]

    # lower <= axisDef <= peak <= axisMax

    gain = supportScalar({"tag": axisDef}, {"tag": tent})
    out = [(gain, None)]

    # First, the positive side

    # outGain is the scalar of axisMax at the tent.
    outGain = supportScalar({"tag": axisMax}, {"tag": tent})

    # Case 3a: Gain is more than outGain. The tent down-slope crosses
    # the axis into negative. We have to split it into multiples.
    #
    #                      | peak  |
    #  1...................|.o.....|..............
    #                      |/x\_   |
    #  gain................+....+_.|..............
    #                     /|    |y\|
    #  ................../.|....|..+_......outGain
    #                   /  |    |  | \
    #  0---|-----------o   |    |  |  o----------1
    #    axisMin    lower  |    |  |   upper
    #                      |    |  |
    #                axisDef    |  axisMax
    #                           |
    #                      crossing
    if gain > outGain:

        # Crossing point on the axis.
        crossing = peak + ((1 - gain) * (upper - peak) / (1 - outGain))

        loc = (axisDef, peak, crossing)
        scalar = 1

        # The part before the crossing point.
        out.append((scalar - gain, loc))

        # The part after the crossing point may use one or two tents,
        # depending on whether upper is before axisMax or not, in one
        # case we need to keep it down to eternity.

        # Case 3a1, similar to case 1neg; just one tent needed, as in
        # the drawing above.
        if upper >= axisMax:
            loc = (crossing, axisMax, axisMax)
            scalar = supportScalar({"tag": axisMax}, {"tag": tent})

            out.append((scalar - gain, loc))

        # Case 3a2: Similar to case 2neg; two tents needed, to keep
        # down to eternity.
        #
        #                      | peak             |
        #  1...................|.o................|...
        #                      |/ \_              |
        #  gain................+....+_............|...
        #                     /|    | \xxxxxxxxxxy|
        #                    / |    |  \_xxxxxyyyy|
        #                   /  |    |    \xxyyyyyy|
        #  0---|-----------o   |    |     o-------|--1
        #    axisMin    lower  |    |      upper  |
        #                      |    |             |
        #                axisDef    |             axisMax
        #                           |
        #                      crossing
        else:
            # A tent's peak cannot fall on axis default. Nudge it.
            if upper == axisDef:
                upper += EPSILON

            # Downslope.
            loc1 = (crossing, upper, axisMax)
            scalar1 = 0

            # Eternity justify.
            loc2 = (upper, axisMax, axisMax)
            scalar2 = supportScalar({"tag": axisMax}, {"tag": tent})

            out.append((scalar1 - gain, loc1))
            out.append((scalar2 - gain, loc2))

    # Case 3: Outermost limit still fits within F2Dot14 bounds;
    # we keep deltas as is and only scale the axes bounds. Deltas beyond -1.0
    # or +1.0 will never be applied as implementations must clamp to that range.
    #
    # A second tent is needed for cases when gain is positive, though we add it
    # unconditionally and it will be dropped because scalar ends up 0.
    #
    # TODO: See if we can just move upper closer to adjust the slope, instead of
    # second tent.
    #
    #            |           peak |
    #  1.........|............o...|..................
    #            |           /x\  |
    #            |          /xxx\ |
    #            |         /xxxxx\|
    #            |        /xxxxxxx+
    #            |       /xxxxxxxx|\
    #  0---|-----|------oxxxxxxxxx|xo---------------1
    #    axisMin |  lower         | upper
    #            |                |
    #          axisDef          axisMax
    #
    elif axisDef + (axisMax - axisDef) * 2 >= upper:

        if not negative and axisDef + (axisMax - axisDef) * MAX_F2DOT14 < upper:
            # we clamp +2.0 to the max F2Dot14 (~1.99994) for convenience
            upper = axisDef + (axisMax - axisDef) * MAX_F2DOT14
            assert peak < upper

        # Special-case if peak is at axisMax.
        if axisMax == peak:
            upper = peak

        loc1 = (max(axisDef, lower), peak, upper)
        scalar1 = 1

        loc2 = (peak, upper, upper)
        scalar2 = 0

        # Don't add a dirac delta!
        if axisDef < upper:
            out.append((scalar1 - gain, loc1))
        if peak < upper:
            out.append((scalar2 - gain, loc2))

    # Case 4: New limit doesn't fit; we need to chop into two tents,
    # because the shape of a triangle with part of one side cut off
    # cannot be represented as a triangle itself.
    #
    #            |   peak |
    #  1.........|......o.|...................
    #            |     /x\|
    #            |    |xxy|\_
    #            |   /xxxy|  \_
    #            |  |xxxxy|    \_
    #            |  /xxxxy|      \_
    #  0---|-----|-oxxxxxx|        o----------1
    #    axisMin | lower  |        upper
    #            |        |
    #          axisDef  axisMax
    #
    else:

        loc1 = (max(axisDef, lower), peak, axisMax)
        scalar1 = 1

        loc2 = (peak, axisMax, axisMax)
        scalar2 = supportScalar({"tag": axisMax}, {"tag": tent})

        out.append((scalar1 - gain, loc1))
        # Don't add a dirac delta!
        if peak < axisMax:
            out.append((scalar2 - gain, loc2))

    # Now, the negative side

    # Case 1neg: Lower extends beyond axisMin: we chop. Simple.
    #
    #                     |   |peak
    #  1..................|...|.o.................
    #                     |   |/ \
    #  gain...............|...+...\...............
    #                     |x_/|    \
    #                     |/  |     \
    #                   _/|   |      \
    #  0---------------o  |   |       o----------1
    #              lower  |   |       upper
    #                     |   |
    #               axisMin   axisDef
    #
    if lower <= axisMin:
        loc = (axisMin, axisMin, axisDef)
        scalar = supportScalar({"tag": axisMin}, {"tag": tent})

        out.append((scalar - gain, loc))

    # Case 2neg: Lower is betwen axisMin and axisDef: we add two
    # tents to keep it down all the way to eternity.
    #
    #      |               |peak
    #  1...|...............|.o.................
    #      |               |/ \
    #  gain|...............+...\...............
    #      |yxxxxxxxxxxxxx/|    \
    #      |yyyyyyxxxxxxx/ |     \
    #      |yyyyyyyyyyyx/  |      \
    #  0---|-----------o   |       o----------1
    #    axisMin    lower  |       upper
    #                      |
    #                    axisDef
    #
    else:
        # A tent's peak cannot fall on axis default. Nudge it.
        if lower == axisDef:
            lower -= EPSILON

        # Downslope.
        loc1 = (axisMin, lower, axisDef)
        scalar1 = 0

        # Eternity justify.
        loc2 = (axisMin, axisMin, lower)
        scalar2 = 0

        out.append((scalar1 - gain, loc1))
        out.append((scalar2 - gain, loc2))

    return out


@lru_cache(128)
def rebaseTent(tent, axisLimit):
    """Given a tuple (lower,peak,upper) "tent" and new axis limits
    (axisMin,axisDefault,axisMax), solves how to represent the tent
    under the new axis configuration.  All values are in normalized
    -1,0,+1 coordinate system. Tent values can be outside this range.

    Return value is a list of tuples. Each tuple is of the form
    (scalar,tent), where scalar is a multipler to multiply any
    delta-sets by, and tent is a new tent for that output delta-set.
    If tent value is None, that is a special deltaset that should
    be always-enabled (called "gain")."""

    axisMin, axisDef, axisMax = axisLimit
    assert -1 <= axisMin <= axisDef <= axisMax <= +1

    lower, peak, upper = tent
    assert -2 <= lower <= peak <= upper <= +2

    assert peak != 0

    sols = _solve(tent, axisLimit)

    n = lambda v: normalizeValue(v, axisLimit, extrapolate=True)
    sols = [
        (scalar, (n(v[0]), n(v[1]), n(v[2])) if v is not None else None)
        for scalar, v in sols
        if scalar
    ]

    return sols
