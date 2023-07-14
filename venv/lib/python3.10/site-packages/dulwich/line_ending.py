# line_ending.py -- Line ending conversion functions
# Copyright (C) 2018-2018 Boris Feld <boris.feld@comet.ml>
#
# Dulwich is dual-licensed under the Apache License, Version 2.0 and the GNU
# General Public License as public by the Free Software Foundation; version 2.0
# or (at your option) any later version. You can redistribute it and/or
# modify it under the terms of either of these two licenses.
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# You should have received a copy of the licenses; if not, see
# <http://www.gnu.org/licenses/> for a copy of the GNU General Public License
# and <http://www.apache.org/licenses/LICENSE-2.0> for a copy of the Apache
# License, Version 2.0.
#
"""All line-ending related functions, from conversions to config processing

Line-ending normalization is a complex beast. Here is some notes and details
about how it seems to work.

The normalization is a two-fold process that happens at two moments:

- When reading a file from the index and to the working directory. For example
  when doing a ``git clone`` or ``git checkout`` call. We call this process the
  read filter in this module.
- When writing a file to the index from the working directory. For example
  when doing a ``git add`` call. We call this process the write filter in this
  module.

Note that when checking status (getting unstaged changes), whether or not
normalization is done on write depends on whether or not the file in the
working dir has also been normalized on read:

- For autocrlf=true all files are always normalized on both read and write.
- For autocrlf=input files are only normalized on write if they are newly
  "added". Since files which are already committed are not normalized on
  checkout into the working tree, they are also left alone when staging
  modifications into the index.

One thing to know is that Git does line-ending normalization only on text
files. How does Git know that a file is text? We can either mark a file as a
text file, a binary file or ask Git to automatically decides. Git has an
heuristic to detect if a file is a text file or a binary file. It seems based
on the percentage of non-printable characters in files.

The code for this heuristic is here:
https://git.kernel.org/pub/scm/git/git.git/tree/convert.c#n46

Dulwich have an implementation with a slightly different heuristic, the
`dulwich.patch.is_binary` function.

The binary detection heuristic implementation is close to the one in JGit:
https://github.com/eclipse/jgit/blob/f6873ffe522bbc3536969a3a3546bf9a819b92bf/org.eclipse.jgit/src/org/eclipse/jgit/diff/RawText.java#L300

There is multiple variables that impact the normalization.

First, a repository can contains a ``.gitattributes`` file (or more than one...)
that can further customize the operation on some file patterns, for example:

    \\*.txt text

Force all ``.txt`` files to be treated as text files and to have their lines
endings normalized.

    \\*.jpg -text

Force all ``.jpg`` files to be treated as binary files and to not have their
lines endings converted.

    \\*.vcproj text eol=crlf

Force all ``.vcproj`` files to be treated as text files and to have their lines
endings converted into ``CRLF`` in working directory no matter the native EOL of
the platform.

    \\*.sh text eol=lf

Force all ``.sh`` files to be treated as text files and to have their lines
endings converted into ``LF`` in working directory no matter the native EOL of
the platform.

If the ``eol`` attribute is not defined, Git uses the ``core.eol`` configuration
value described later.

    \\* text=auto

Force all files to be scanned by the text file heuristic detection and to have
their line endings normalized in case they are detected as text files.

Git also have a obsolete attribute named ``crlf`` that can be translated to the
corresponding text attribute value.

Then there are some configuration option (that can be defined at the
repository or user level):

- core.autocrlf
- core.eol

``core.autocrlf`` is taken into account for all files that doesn't have a ``text``
attribute defined in ``.gitattributes``; it takes three possible values:

    - ``true``: This forces all files on the working directory to have CRLF
      line-endings in the working directory and convert line-endings to LF
      when writing to the index. When autocrlf is set to true, eol value is
      ignored.
    - ``input``: Quite similar to the ``true`` value but only force the write
      filter, ie line-ending of new files added to the index will get their
      line-endings converted to LF.
    - ``false`` (default): No normalization is done.

``core.eol`` is the top-level configuration to define the line-ending to use
when applying the read_filer. It takes three possible values:

    - ``lf``: When normalization is done, force line-endings to be ``LF`` in the
      working directory.
    - ``crlf``: When normalization is done, force line-endings to be ``CRLF`` in
      the working directory.
    - ``native`` (default): When normalization is done, force line-endings to be
      the platform's native line ending.

One thing to remember is when line-ending normalization is done on a file, Git
always normalize line-ending to ``LF`` when writing to the index.

There are sources that seems to indicate that Git won't do line-ending
normalization when a file contains mixed line-endings. I think this logic
might be in text / binary detection heuristic but couldn't find it yet.

Sources:
- https://git-scm.com/docs/git-config#git-config-coreeol
- https://git-scm.com/docs/git-config#git-config-coreautocrlf
- https://git-scm.com/docs/gitattributes#_checking_out_and_checking_in
- https://adaptivepatchwork.com/2012/03/01/mind-the-end-of-your-line/
"""

from .object_store import iter_tree_contents
from .objects import Blob
from .patch import is_binary

CRLF = b"\r\n"
LF = b"\n"


def convert_crlf_to_lf(text_hunk):
    """Convert CRLF in text hunk into LF

    Args:
      text_hunk: A bytes string representing a text hunk
    Returns: The text hunk with the same type, with CRLF replaced into LF
    """
    return text_hunk.replace(CRLF, LF)


def convert_lf_to_crlf(text_hunk):
    """Convert LF in text hunk into CRLF

    Args:
      text_hunk: A bytes string representing a text hunk
    Returns: The text hunk with the same type, with LF replaced into CRLF
    """
    # TODO find a more efficient way of doing it
    intermediary = text_hunk.replace(CRLF, LF)
    return intermediary.replace(LF, CRLF)


def get_checkout_filter(core_eol, core_autocrlf, git_attributes):
    """Returns the correct checkout filter based on the passed arguments"""
    # TODO this function should process the git_attributes for the path and if
    # the text attribute is not defined, fallback on the
    # get_checkout_filter_autocrlf function with the autocrlf value
    return get_checkout_filter_autocrlf(core_autocrlf)


def get_checkin_filter(core_eol, core_autocrlf, git_attributes):
    """Returns the correct checkin filter based on the passed arguments"""
    # TODO this function should process the git_attributes for the path and if
    # the text attribute is not defined, fallback on the
    # get_checkin_filter_autocrlf function with the autocrlf value
    return get_checkin_filter_autocrlf(core_autocrlf)


def get_checkout_filter_autocrlf(core_autocrlf):
    """Returns the correct checkout filter base on autocrlf value

    Args:
      core_autocrlf: The bytes configuration value of core.autocrlf.
        Valid values are: b'true', b'false' or b'input'.
    Returns: Either None if no filter has to be applied or a function
        accepting a single argument, a binary text hunk
    """

    if core_autocrlf == b"true":
        return convert_lf_to_crlf

    return None


def get_checkin_filter_autocrlf(core_autocrlf):
    """Returns the correct checkin filter base on autocrlf value

    Args:
      core_autocrlf: The bytes configuration value of core.autocrlf.
        Valid values are: b'true', b'false' or b'input'.
    Returns: Either None if no filter has to be applied or a function
        accepting a single argument, a binary text hunk
    """

    if core_autocrlf == b"true" or core_autocrlf == b"input":
        return convert_crlf_to_lf

    # Checking filter should never be `convert_lf_to_crlf`
    return None


class BlobNormalizer:
    """An object to store computation result of which filter to apply based
    on configuration, gitattributes, path and operation (checkin or checkout)
    """

    def __init__(self, config_stack, gitattributes):
        self.config_stack = config_stack
        self.gitattributes = gitattributes

        # Compute which filters we needs based on parameters
        try:
            core_eol = config_stack.get("core", "eol")
        except KeyError:
            core_eol = "native"

        try:
            core_autocrlf = config_stack.get("core", "autocrlf").lower()
        except KeyError:
            core_autocrlf = False

        self.fallback_read_filter = get_checkout_filter(
            core_eol, core_autocrlf, self.gitattributes
        )
        self.fallback_write_filter = get_checkin_filter(
            core_eol, core_autocrlf, self.gitattributes
        )

    def checkin_normalize(self, blob, tree_path):
        """Normalize a blob during a checkin operation"""
        if self.fallback_write_filter is not None:
            return normalize_blob(
                blob, self.fallback_write_filter, binary_detection=True
            )

        return blob

    def checkout_normalize(self, blob, tree_path):
        """Normalize a blob during a checkout operation"""
        if self.fallback_read_filter is not None:
            return normalize_blob(
                blob, self.fallback_read_filter, binary_detection=True
            )

        return blob


def normalize_blob(blob, conversion, binary_detection):
    """Takes a blob as input returns either the original blob if
    binary_detection is True and the blob content looks like binary, else
    return a new blob with converted data
    """
    # Read the original blob
    data = blob.data

    # If we need to detect if a file is binary and the file is detected as
    # binary, do not apply the conversion function and return the original
    # chunked text
    if binary_detection is True:
        if is_binary(data):
            return blob

    # Now apply the conversion
    converted_data = conversion(data)

    new_blob = Blob()
    new_blob.data = converted_data

    return new_blob


class TreeBlobNormalizer(BlobNormalizer):
    def __init__(self, config_stack, git_attributes, object_store, tree=None):
        super().__init__(config_stack, git_attributes)
        if tree:
            self.existing_paths = {
                name
                for name, _, _ in iter_tree_contents(object_store, tree)
            }
        else:
            self.existing_paths = set()

    def checkin_normalize(self, blob, tree_path):
        # Existing files should only be normalized on checkin if it was
        # previously normalized on checkout
        if (
            self.fallback_read_filter is not None
            or tree_path not in self.existing_paths
        ):
            return super().checkin_normalize(blob, tree_path)
        return blob
