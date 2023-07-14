from __future__ import annotations

import dataclasses
import logging
import re

from pathlib import Path
from subprocess import CalledProcessError
from typing import TYPE_CHECKING
from urllib.parse import urljoin

from dulwich import porcelain
from dulwich.client import HTTPUnauthorized
from dulwich.client import get_transport_and_path
from dulwich.config import ConfigFile
from dulwich.config import parse_submodules
from dulwich.errors import NotGitRepository
from dulwich.refs import ANNOTATED_TAG_SUFFIX
from dulwich.repo import Repo

from poetry.console.exceptions import PoetryConsoleError
from poetry.utils.authenticator import get_default_authenticator
from poetry.utils.helpers import remove_directory


if TYPE_CHECKING:
    from dulwich.client import FetchPackResult
    from dulwich.client import GitClient


logger = logging.getLogger(__name__)


def is_revision_sha(revision: str | None) -> bool:
    return re.match(r"^\b[0-9a-f]{5,40}\b$", revision or "") is not None


def annotated_tag(ref: str | bytes) -> bytes:
    if isinstance(ref, str):
        ref = ref.encode("utf-8")
    return ref + ANNOTATED_TAG_SUFFIX


@dataclasses.dataclass
class GitRefSpec:
    branch: str | None = None
    revision: str | None = None
    tag: str | None = None
    ref: bytes = dataclasses.field(default_factory=lambda: b"HEAD")

    def resolve(self, remote_refs: FetchPackResult) -> None:
        """
        Resolve the ref using the provided remote refs.
        """
        self._normalise(remote_refs=remote_refs)
        self._set_head(remote_refs=remote_refs)

    def _normalise(self, remote_refs: FetchPackResult) -> None:
        """
        Internal helper method to determine if given revision is
            1. a branch or tag; if so, set corresponding properties.
            2. a short sha; if so, resolve full sha and set as revision
        """
        if self.revision:
            ref = f"refs/tags/{self.revision}".encode()
            if ref in remote_refs.refs or annotated_tag(ref) in remote_refs.refs:
                # this is a tag, incorrectly specified as a revision, tags take priority
                self.tag = self.revision
                self.revision = None
            elif (
                self.revision.encode("utf-8") in remote_refs.refs
                or f"refs/heads/{self.revision}".encode() in remote_refs.refs
            ):
                # this is most likely a ref spec or a branch incorrectly specified
                self.branch = self.revision
                self.revision = None
        elif (
            self.branch
            and f"refs/heads/{self.branch}".encode() not in remote_refs.refs
            and (
                f"refs/tags/{self.branch}".encode() in remote_refs.refs
                or annotated_tag(f"refs/tags/{self.branch}") in remote_refs.refs
            )
        ):
            # this is a tag incorrectly specified as a branch
            self.tag = self.branch
            self.branch = None

        if self.revision and self.is_sha_short:
            # revision is a short sha, resolve to full sha
            short_sha = self.revision.encode("utf-8")
            for sha in remote_refs.refs.values():
                if sha.startswith(short_sha):
                    self.revision = sha.decode("utf-8")
                    break

    def _set_head(self, remote_refs: FetchPackResult) -> None:
        """
        Internal helper method to populate ref and set it's sha as the remote's head
        and default ref.
        """
        self.ref = remote_refs.symrefs[b"HEAD"]

        if self.revision:
            head = self.revision.encode("utf-8")
        else:
            if self.tag:
                ref = f"refs/tags/{self.tag}".encode()
                annotated = annotated_tag(ref)
                self.ref = annotated if annotated in remote_refs.refs else ref
            elif self.branch:
                self.ref = (
                    self.branch.encode("utf-8")
                    if self.is_ref
                    else f"refs/heads/{self.branch}".encode()
                )
            head = remote_refs.refs[self.ref]

        remote_refs.refs[self.ref] = remote_refs.refs[b"HEAD"] = head

    @property
    def key(self) -> str:
        return self.revision or self.branch or self.tag or self.ref.decode("utf-8")

    @property
    def is_sha(self) -> bool:
        return is_revision_sha(revision=self.revision)

    @property
    def is_ref(self) -> bool:
        return self.branch is not None and self.branch.startswith("refs/")

    @property
    def is_sha_short(self) -> bool:
        return self.revision is not None and self.is_sha and len(self.revision) < 40


@dataclasses.dataclass
class GitRepoLocalInfo:
    repo: dataclasses.InitVar[Repo | Path]
    origin: str = dataclasses.field(init=False)
    revision: str = dataclasses.field(init=False)

    def __post_init__(self, repo: Repo | Path) -> None:
        repo = Git.as_repo(repo=repo) if not isinstance(repo, Repo) else repo
        self.origin = Git.get_remote_url(repo=repo, remote="origin")
        self.revision = Git.get_revision(repo=repo)


class Git:
    @staticmethod
    def as_repo(repo: Path) -> Repo:
        return Repo(str(repo))

    @staticmethod
    def get_remote_url(repo: Repo, remote: str = "origin") -> str:
        with repo:
            config = repo.get_config()
            section = (b"remote", remote.encode("utf-8"))

            url = ""
            if config.has_section(section):
                value = config.get(section, b"url")
                url = value.decode("utf-8")

            return url

    @staticmethod
    def get_revision(repo: Repo) -> str:
        with repo:
            return repo.head().decode("utf-8")

    @classmethod
    def info(cls, repo: Repo | Path) -> GitRepoLocalInfo:
        return GitRepoLocalInfo(repo=repo)

    @staticmethod
    def get_name_from_source_url(url: str) -> str:
        return re.sub(r"(.git)?$", "", url.rsplit("/", 1)[-1])

    @classmethod
    def _fetch_remote_refs(cls, url: str, local: Repo) -> FetchPackResult:
        """
        Helper method to fetch remote refs.
        """
        client: GitClient
        path: str

        kwargs: dict[str, str] = {}
        credentials = get_default_authenticator().get_credentials_for_git_url(url=url)

        if credentials.password and credentials.username:
            # we do this conditionally as otherwise, dulwich might complain if these
            # parameters are passed in for an ssh url
            kwargs["username"] = credentials.username
            kwargs["password"] = credentials.password

        config = local.get_config_stack()
        client, path = get_transport_and_path(url, config=config, **kwargs)

        with local:
            result: FetchPackResult = client.fetch(
                path,
                local,
                determine_wants=local.object_store.determine_wants_all,
            )
            return result

    @staticmethod
    def _clone_legacy(url: str, refspec: GitRefSpec, target: Path) -> Repo:
        """
        Helper method to facilitate fallback to using system provided git client via
        subprocess calls.
        """
        from poetry.vcs.git.system import SystemGit

        logger.debug("Cloning '%s' using system git client", url)

        if target.exists():
            remove_directory(path=target, force=True)

        revision = refspec.tag or refspec.branch or refspec.revision or "HEAD"

        try:
            SystemGit.clone(url, target)
        except CalledProcessError:
            raise PoetryConsoleError(
                f"Failed to clone {url}, check your git configuration and permissions"
                " for this repository."
            )

        if revision:
            revision.replace("refs/head/", "")
            revision.replace("refs/tags/", "")

        try:
            SystemGit.checkout(revision, target)
        except CalledProcessError:
            raise PoetryConsoleError(f"Failed to checkout {url} at '{revision}'")

        repo = Repo(str(target))
        return repo

    @classmethod
    def _clone(cls, url: str, refspec: GitRefSpec, target: Path) -> Repo:
        """
        Helper method to clone a remove repository at the given `url` at the specified
        ref spec.
        """
        local: Repo
        if not target.exists():
            local = Repo.init(str(target), mkdir=True)
            porcelain.remote_add(local, "origin", url)
        else:
            local = Repo(str(target))

        remote_refs = cls._fetch_remote_refs(url=url, local=local)

        logger.debug(
            "Cloning <c2>%s</> at '<c2>%s</>' to <c1>%s</>", url, refspec.key, target
        )

        try:
            refspec.resolve(remote_refs=remote_refs)
        except KeyError:  # branch / ref does not exist
            raise PoetryConsoleError(
                f"Failed to clone {url} at '{refspec.key}', verify ref exists on"
                " remote."
            )

        # ensure local HEAD matches remote
        local.refs[b"HEAD"] = remote_refs.refs[b"HEAD"]

        if refspec.is_ref:
            # set ref to current HEAD
            local.refs[refspec.ref] = local.refs[b"HEAD"]

        for base, prefix in {
            (b"refs/remotes/origin", b"refs/heads/"),
            (b"refs/tags", b"refs/tags"),
        }:
            local.refs.import_refs(
                base=base,
                other={
                    n[len(prefix) :]: v
                    for (n, v) in remote_refs.refs.items()
                    if n.startswith(prefix) and not n.endswith(ANNOTATED_TAG_SUFFIX)
                },
            )

        try:
            with local:
                local.reset_index()
        except (AssertionError, KeyError) as e:
            # this implies the ref we need does not exist or is invalid
            if isinstance(e, KeyError):
                # the local copy is at a bad state, lets remove it
                logger.debug(
                    (
                        "Removing local clone (<c1>%s</>) of repository as it is in a"
                        " broken state."
                    ),
                    local.path,
                )
                remove_directory(Path(local.path), force=True)

            if isinstance(e, AssertionError) and "Invalid object name" not in str(e):
                raise

            logger.debug(
                (
                    "\nRequested ref (<c2>%s</c2>) was not fetched to local copy and"
                    " cannot be used. The following error was"
                    " raised:\n\n\t<warning>%s</>"
                ),
                refspec.key,
                e,
            )

            raise PoetryConsoleError(
                f"Failed to clone {url} at '{refspec.key}', verify ref exists on"
                " remote."
            )

        return local

    @classmethod
    def _clone_submodules(cls, repo: Repo) -> None:
        """
        Helper method to identify configured submodules and clone them recursively.
        """
        repo_root = Path(repo.path)
        modules_config = repo_root.joinpath(".gitmodules")

        # A relative URL by definition starts with ../ or ./
        relative_submodule_regex = re.compile(r"^\.{1,2}/")

        if modules_config.exists():
            config = ConfigFile.from_path(str(modules_config))

            url: bytes
            path: bytes
            submodules = parse_submodules(config)

            for path, url, name in submodules:
                path_relative = Path(path.decode("utf-8"))
                path_absolute = repo_root.joinpath(path_relative)

                url_string = url.decode("utf-8")
                if relative_submodule_regex.search(url_string):
                    url_string = urljoin(f"{Git.get_remote_url(repo)}/", url_string)

                source_root = path_absolute.parent
                source_root.mkdir(parents=True, exist_ok=True)

                with repo:
                    try:
                        revision = repo.open_index()[path].sha.decode("utf-8")
                    except KeyError:
                        logger.debug(
                            "Skip submodule %s in %s, path %s not found",
                            name,
                            repo.path,
                            path,
                        )
                        continue

                cls.clone(
                    url=url_string,
                    source_root=source_root,
                    name=path_relative.name,
                    revision=revision,
                    clean=path_absolute.exists()
                    and not path_absolute.joinpath(".git").is_dir(),
                )

    @staticmethod
    def is_using_legacy_client() -> bool:
        from poetry.config.config import Config

        legacy_client: bool = Config.create().get(
            "experimental.system-git-client", False
        )
        return legacy_client

    @staticmethod
    def get_default_source_root() -> Path:
        from poetry.config.config import Config

        return Path(Config.create().get("cache-dir")) / "src"

    @classmethod
    def clone(
        cls,
        url: str,
        name: str | None = None,
        branch: str | None = None,
        tag: str | None = None,
        revision: str | None = None,
        source_root: Path | None = None,
        clean: bool = False,
    ) -> Repo:
        source_root = source_root or cls.get_default_source_root()
        source_root.mkdir(parents=True, exist_ok=True)

        name = name or cls.get_name_from_source_url(url=url)
        target = source_root / name
        refspec = GitRefSpec(branch=branch, revision=revision, tag=tag)

        if target.exists():
            if clean:
                # force clean the local copy if it exists, do not reuse
                remove_directory(target, force=True)
            else:
                # check if the current local copy matches the requested ref spec
                try:
                    current_repo = Repo(str(target))

                    with current_repo:
                        current_sha = current_repo.head().decode("utf-8")
                except (NotGitRepository, AssertionError, KeyError):
                    # something is wrong with the current checkout, clean it
                    remove_directory(target, force=True)
                else:
                    if not is_revision_sha(revision=current_sha):
                        # head is not a sha, this will cause issues later, lets reset
                        remove_directory(target, force=True)
                    elif (
                        refspec.is_sha
                        and refspec.revision is not None
                        and current_sha.startswith(refspec.revision)
                    ):
                        # if revision is used short-circuit remote fetch head matches
                        return current_repo

        try:
            if not cls.is_using_legacy_client():
                local = cls._clone(url=url, refspec=refspec, target=target)
                cls._clone_submodules(repo=local)
                return local
        except HTTPUnauthorized:
            # we do this here to handle http authenticated repositories as dulwich
            # does not currently support using credentials from git-credential helpers.
            # upstream issue: https://github.com/jelmer/dulwich/issues/873
            #
            # this is a little inefficient, however preferred as this is transparent
            # without additional configuration or changes for existing projects that
            # use http basic auth credentials.
            logger.debug(
                (
                    "Unable to fetch from private repository '%s', falling back to"
                    " system git"
                ),
                url,
            )

        # fallback to legacy git client
        return cls._clone_legacy(url=url, refspec=refspec, target=target)
