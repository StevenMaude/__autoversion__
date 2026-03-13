"""
Automatically determine the version of the importer through package metadata
or version control if installed with ``pip install --editable``.
"""

import os
import re
import subprocess
import sys
from importlib import metadata
from inspect import getmodule
from itertools import groupby

orig = sys.modules[__name__]


class Git:
    @classmethod
    def get_branch(cls, path):
        return (
            subprocess.check_output(
                "git rev-parse --abbrev-ref HEAD", shell=True, cwd=path
            )
            .strip()
            .decode("utf-8")
        )

    @classmethod
    def get_version(cls, path, memo={}):
        """
        Return a string describing the version of the repository at ``path`` if
        possible, otherwise throws ``subprocess.CalledProcessError``.

        (Note: memoizes the result in the ``memo`` parameter)
        """
        if path not in memo:
            memo[path] = (
                subprocess.check_output(
                    "git describe --tags --dirty 2> /dev/null", shell=True, cwd=path
                )
                .strip()
                .decode("utf-8")
            )

            v = re.search("-[0-9]+-", memo[path])
            if v is not None:
                # Replace -n- with -branchname-n-
                branch = rf"-{cls.get_branch(path)}-\1-"
                (memo[path], _) = re.subn("-([0-9]+)-", branch, memo[path], 1)

        return memo[path]

    @classmethod
    def is_repo_instance(cls, path):
        """
        Return ``True`` if ``path`` is a source controlled repository.
        """
        try:
            cls.get_version(path)
            return True
        except subprocess.CalledProcessError:
            # Git returns non-zero status
            return False
        except OSError:
            # Git unavailable?
            return False


repo_types = [Git]


def get_repo_type(path):
    """
    Return the class representing the repository type at ``path`` if there is
    one, otherwise return None.
    """
    for repo_type in repo_types:
        if repo_type.is_repo_instance(path):
            return repo_type


def getversion(package):
    """
    Obtain the ``__version__`` for ``package``, looking at the egg information
    or the source repository's version control if necessary.
    """
    try:
        distribution = metadata.distribution(package)
    except metadata.PackageNotFoundError as exc:
        raise RuntimeError(f"Can't find distribution {package}") from exc
    location = str(distribution.locate_file(""))
    repo_type = get_repo_type(location)
    if repo_type is None:
        return distribution.version

    return repo_type.get_version(location)


def version_from_frame(frame):
    """
    Given a ``frame``, obtain the version number of the module running there.
    """

    module = getmodule(frame)
    if module is None:
        s = "<unknown from {0}:{1}>"
        return s.format(frame.f_code.co_filename, frame.f_lineno)

    module_name = module.__name__

    variable = f"AUTOVERSION_{module_name.upper()}"
    override = os.environ.get(variable, None)
    if override is not None:
        return override

    while True:
        try:
            metadata.version(module_name)
        except metadata.PackageNotFoundError:
            # Look at what's to the left of "."
            module_name, dot, _ = module_name.partition(".")
            if dot == "":
                # There is no dot, nothing more we can do.
                break
        else:
            return getversion(module_name)

    return None


def try_fix_num(n):
    """
    Return ``n`` as an integer if it is numeric, otherwise return the input
    """
    if not n.isdigit():
        return n
    if n.startswith("0"):
        n = n.lstrip("0")
    if not n:
        n = "0"
    return int(n)


def tupleize_version(version):
    """
    Split ``version`` into a lexicographically comparable tuple.

    "1.0.3" -> ((1, 0, 3),)
    "1.0.3-dev" -> ((1, 0, 3), ("dev",))
    "1.0.3-rc-5" -> ((1, 0, 3), ("rc",), (5,))
    """

    if version is None:
        return (("unknown",),)

    if version.startswith("<unknown"):
        return (("unknown",),)

    split = re.split(r"(?:\.|(-))", version)
    parsed = tuple(try_fix_num(x) for x in split if x)

    # Put the tuples in groups by "-"
    def is_dash(s):
        return s == "-"

    grouped = groupby(parsed, is_dash)

    return tuple(tuple(group) for dash, group in grouped if not dash)


class Module(type(orig)):
    @property
    def __version__(self):
        """
        Obtain the __version__ of the module of the requestor
        """
        prev_frame = sys._getframe(1)
        return version_from_frame(prev_frame)

    @property
    def __version_tuple__(self):
        """
        Returns a lexicographically comparable tuple representing the version
        of the requestor
        """
        prev_frame = sys._getframe(1)
        return tupleize_version(version_from_frame(prev_frame))

    def __getattr__(self, key):
        return getattr(orig, key)


module = Module(__name__)
module.__file__ = orig.__file__
module.__doc__ = orig.__doc__

sys.modules[__name__] = module
