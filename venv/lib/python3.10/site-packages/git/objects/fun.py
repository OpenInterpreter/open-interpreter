"""Module with functions which are supposed to be as fast as possible"""
from stat import S_ISDIR


from git.compat import safe_decode, defenc

# typing ----------------------------------------------

from typing import (
    Callable,
    List,
    MutableSequence,
    Sequence,
    Tuple,
    TYPE_CHECKING,
    Union,
    overload,
)

if TYPE_CHECKING:
    from _typeshed import ReadableBuffer
    from git import GitCmdObjectDB

EntryTup = Tuple[bytes, int, str]  # same as TreeCacheTup in tree.py
EntryTupOrNone = Union[EntryTup, None]

# ---------------------------------------------------


__all__ = (
    "tree_to_stream",
    "tree_entries_from_data",
    "traverse_trees_recursive",
    "traverse_tree_recursive",
)


def tree_to_stream(entries: Sequence[EntryTup], write: Callable[["ReadableBuffer"], Union[int, None]]) -> None:
    """Write the give list of entries into a stream using its write method

    :param entries: **sorted** list of tuples with (binsha, mode, name)
    :param write: write method which takes a data string"""
    ord_zero = ord("0")
    bit_mask = 7  # 3 bits set

    for binsha, mode, name in entries:
        mode_str = b""
        for i in range(6):
            mode_str = bytes([((mode >> (i * 3)) & bit_mask) + ord_zero]) + mode_str
        # END for each 8 octal value

        # git slices away the first octal if its zero
        if mode_str[0] == ord_zero:
            mode_str = mode_str[1:]
        # END save a byte

        # here it comes:  if the name is actually unicode, the replacement below
        # will not work as the binsha is not part of the ascii unicode encoding -
        # hence we must convert to an utf8 string for it to work properly.
        # According to my tests, this is exactly what git does, that is it just
        # takes the input literally, which appears to be utf8 on linux.
        if isinstance(name, str):
            name_bytes = name.encode(defenc)
        else:
            name_bytes = name  # type: ignore[unreachable]  # check runtime types - is always str?
        write(b"".join((mode_str, b" ", name_bytes, b"\0", binsha)))
    # END for each item


def tree_entries_from_data(data: bytes) -> List[EntryTup]:
    """Reads the binary representation of a tree and returns tuples of Tree items

    :param data: data block with tree data (as bytes)
    :return: list(tuple(binsha, mode, tree_relative_path), ...)"""
    ord_zero = ord("0")
    space_ord = ord(" ")
    len_data = len(data)
    i = 0
    out = []
    while i < len_data:
        mode = 0

        # read mode
        # Some git versions truncate the leading 0, some don't
        # The type will be extracted from the mode later
        while data[i] != space_ord:
            # move existing mode integer up one level being 3 bits
            # and add the actual ordinal value of the character
            mode = (mode << 3) + (data[i] - ord_zero)
            i += 1
        # END while reading mode

        # byte is space now, skip it
        i += 1

        # parse name, it is NULL separated

        ns = i
        while data[i] != 0:
            i += 1
        # END while not reached NULL

        # default encoding for strings in git is utf8
        # Only use the respective unicode object if the byte stream was encoded
        name_bytes = data[ns:i]
        name = safe_decode(name_bytes)

        # byte is NULL, get next 20
        i += 1
        sha = data[i : i + 20]
        i = i + 20
        out.append((sha, mode, name))
    # END for each byte in data stream
    return out


def _find_by_name(tree_data: MutableSequence[EntryTupOrNone], name: str, is_dir: bool, start_at: int) -> EntryTupOrNone:
    """return data entry matching the given name and tree mode
    or None.
    Before the item is returned, the respective data item is set
    None in the tree_data list to mark it done"""

    try:
        item = tree_data[start_at]
        if item and item[2] == name and S_ISDIR(item[1]) == is_dir:
            tree_data[start_at] = None
            return item
    except IndexError:
        pass
    # END exception handling
    for index, item in enumerate(tree_data):
        if item and item[2] == name and S_ISDIR(item[1]) == is_dir:
            tree_data[index] = None
            return item
        # END if item matches
    # END for each item
    return None


@overload
def _to_full_path(item: None, path_prefix: str) -> None:
    ...


@overload
def _to_full_path(item: EntryTup, path_prefix: str) -> EntryTup:
    ...


def _to_full_path(item: EntryTupOrNone, path_prefix: str) -> EntryTupOrNone:
    """Rebuild entry with given path prefix"""
    if not item:
        return item
    return (item[0], item[1], path_prefix + item[2])


def traverse_trees_recursive(
    odb: "GitCmdObjectDB", tree_shas: Sequence[Union[bytes, None]], path_prefix: str
) -> List[Tuple[EntryTupOrNone, ...]]:
    """
    :return: list of list with entries according to the given binary tree-shas.
        The result is encoded in a list
        of n tuple|None per blob/commit, (n == len(tree_shas)), where
        * [0] == 20 byte sha
        * [1] == mode as int
        * [2] == path relative to working tree root
        The entry tuple is None if the respective blob/commit did not
        exist in the given tree.
    :param tree_shas: iterable of shas pointing to trees. All trees must
        be on the same level. A tree-sha may be None in which case None
    :param path_prefix: a prefix to be added to the returned paths on this level,
        set it '' for the first iteration
    :note: The ordering of the returned items will be partially lost"""
    trees_data: List[List[EntryTupOrNone]] = []

    nt = len(tree_shas)
    for tree_sha in tree_shas:
        if tree_sha is None:
            data: List[EntryTupOrNone] = []
        else:
            # make new list for typing as list invariant
            data = list(tree_entries_from_data(odb.stream(tree_sha).read()))
        # END handle muted trees
        trees_data.append(data)
    # END for each sha to get data for

    out: List[Tuple[EntryTupOrNone, ...]] = []

    # find all matching entries and recursively process them together if the match
    # is a tree. If the match is a non-tree item, put it into the result.
    # Processed items will be set None
    for ti, tree_data in enumerate(trees_data):

        for ii, item in enumerate(tree_data):
            if not item:
                continue
            # END skip already done items
            entries: List[EntryTupOrNone]
            entries = [None for _ in range(nt)]
            entries[ti] = item
            _sha, mode, name = item
            is_dir = S_ISDIR(mode)  # type mode bits

            # find this item in all other tree data items
            # wrap around, but stop one before our current index, hence
            # ti+nt, not ti+1+nt
            for tio in range(ti + 1, ti + nt):
                tio = tio % nt
                entries[tio] = _find_by_name(trees_data[tio], name, is_dir, ii)

            # END for each other item data
            # if we are a directory, enter recursion
            if is_dir:
                out.extend(
                    traverse_trees_recursive(
                        odb,
                        [((ei and ei[0]) or None) for ei in entries],
                        path_prefix + name + "/",
                    )
                )
            else:
                out.append(tuple(_to_full_path(e, path_prefix) for e in entries))

            # END handle recursion
            # finally mark it done
            tree_data[ii] = None
        # END for each item

        # we are done with one tree, set all its data empty
        del tree_data[:]
    # END for each tree_data chunk
    return out


def traverse_tree_recursive(odb: "GitCmdObjectDB", tree_sha: bytes, path_prefix: str) -> List[EntryTup]:
    """
    :return: list of entries of the tree pointed to by the binary tree_sha. An entry
        has the following format:
        * [0] 20 byte sha
        * [1] mode as int
        * [2] path relative to the repository
    :param path_prefix: prefix to prepend to the front of all returned paths"""
    entries = []
    data = tree_entries_from_data(odb.stream(tree_sha).read())

    # unpacking/packing is faster than accessing individual items
    for sha, mode, name in data:
        if S_ISDIR(mode):
            entries.extend(traverse_tree_recursive(odb, sha, path_prefix + name + "/"))
        else:
            entries.append((sha, mode, path_prefix + name))
    # END for each item

    return entries
