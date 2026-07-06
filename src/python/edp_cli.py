from __future__ import annotations

from edp_cli_core.app import main, parse_args
from edp_cli_core.commands.data import *
from edp_cli_core.commands.divergence import *
from edp_cli_core.commands.low_buy import *
from edp_cli_core.commands.shared import *
from edp_cli_core.commands.strategy import *
from edp_cli_core.commands.theme import *
from edp_cli_core.commands.theme_stock import *
from edp_cli_core.common import (
    ChineseArgumentParser,
    ForwardArg,
    add_python_arg,
    chinese_argparse_text,
    set_script_runner,
)
from edp_cli_core.runtime import (
    append_forwarded_args,
    find_repo_root,
    missing_script,
    run_command,
    run_script,
    subprocess,
)
from edp_cli_core.shell import run_menu, run_status
from edp_cli_core.version import VERSION


if __name__ == "__main__":
    main()
