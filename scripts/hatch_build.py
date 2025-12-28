import os
import sys
import shutil
from pathlib import Path
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

sys.path.append(os.path.dirname(__file__))
from inline_resources import generate_inlined_css


class CustomBuildHook(BuildHookInterface):
    def initialize(self, version: str, build_data: dict[str, Any]):
        generate_inlined_css()
        src = Path(self.root) / 'resources' / 'styles' / 'main.css'
        dst = Path(self.root) / 'cloudflare_error_page' / 'templates'
        shutil.copy(src, dst)
