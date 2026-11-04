"""Setuptools hooks: no implicit discovery or cached private payload in releases."""

from pathlib import Path
import sys

from setuptools.command.build_py import build_py
from setuptools.command.sdist import sdist

sys.path.insert(0, str(Path(__file__).resolve().parent))
from public_distribution import ROOT, check_content, is_allowed, load_policy, selected_files  # noqa: E402


class PublicBuildPy(build_py):
    def run(self):
        selected_files(ROOT, "wheel")
        super().run()
        policy = load_policy(ROOT)
        for path in Path(self.build_lib).rglob("*"):
            if not path.is_file():
                continue
            name = path.relative_to(self.build_lib).as_posix()
            if not is_allowed(name, policy["wheel_files"], policy.get("wheel_patterns", [])):
                raise ValueError("Unexpected cached build payload: " + name)
            check_content(name, path.read_bytes())


class PublicSdist(sdist):
    def make_release_tree(self, base_dir, files):
        # Egg-info SOURCES can remember old files; never use it as a release allowlist.
        names = selected_files(ROOT, "source")
        super().make_release_tree(base_dir, names)
