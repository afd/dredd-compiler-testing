import argparse
import jinja2
import json
import os
import shutil
import stat
import sys
import subprocess

from dredd_test_runners.common.constants import (DEFAULT_RUNTIME_TIMEOUT,
                                                 MIN_TIMEOUT_FOR_MUTANT_COMPILATION,
                                                 TIMEOUT_MULTIPLIER_FOR_MUTANT_COMPILATION,
                                                 MIN_TIMEOUT_FOR_MUTANT_EXECUTION,
                                                 TIMEOUT_MULTIPLIER_FOR_MUTANT_EXECUTION)
from dredd_test_runners.common.run_process_with_timeout import ProcessResult, run_process_with_timeout

from pathlib import Path
from typing import Dict, List, Optional


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("work_dir",
                        help="Directory containing test results. It should have subdirectories, 'tests' and "
                             "'killed_mutants'.",
                        type=Path)
    parser.add_argument("mutated_compiler_executable",
                        help="Path to the executable for the Dredd-mutated compiler.",
                        type=Path)
    parser.add_argument("csmith_root",
                        help="Path to Csmith checkout, built in 'build' directory under this path.",
                        type=Path)
    args = parser.parse_args()
    work_dir: Path = args.work_dir
    if not work_dir.exists() or not work_dir.is_dir():
        print(f"Error: {str(work_dir)} is not a working directory.")
        sys.exit(1)
    tests_dir = work_dir / "tests"
    if not tests_dir.exists() or not tests_dir.is_dir():
        print(f"Error: {str(tests_dir)} does not exist.")
        sys.exit(1)
    killed_mutants_dir = work_dir / "killed_mutants"
    if not killed_mutants_dir.exists() or not killed_mutants_dir.is_dir():
        print(f"Error: {str(killed_mutants_dir)} does not exist.")
        sys.exit(1)

    killed_mutant_to_test_info: Dict[int, Dict] = {}

    # Figure out all the tests that have killed mutants in ways for which reduction is
    # actionable. The reason for determining all such tests upfront is that when we reduce one
    # such test, we can quickly see whether it kills any of the mutants killed by the other
    # tests, avoiding the need to reduce those tests too if so.
    for test in tests_dir.glob('*'):
        if not test.is_dir():
            continue
        if not test.name.startswith("csmith"):
            continue
        kill_summary: Path = test / "kill_summary.json"
        if not kill_summary.exists():
            continue
        kill_summary_json: Dict = json.load(open(kill_summary, 'r'))
        for mutant in kill_summary_json["killed_mutants"]:
            mutant_summary = json.load(open(killed_mutants_dir / str(mutant) / "kill_info.json", 'r'))
            kill_type: str = mutant_summary['kill_type']
            if (kill_type == 'KillStatus.KILL_DIFFERENT_STDOUT'
                    or kill_type == 'KillStatus.KILL_RUNTIME_TIMEOUT'
                    or kill_type == 'KillStatus.KILL_DIFFERENT_EXIT_CODES'):
                # This is an actionable kill: the mutated compiler produces a compilable program
                # that runs, but that deviates from the expected result at runtime.
                killed_mutant_to_test_info[mutant] = mutant_summary
    
    reduction_queue: List[int] = list(killed_mutant_to_test_info.keys())
    reduction_queue.sort()

    reductions_dir: Path = work_dir / "reductions"
    Path(reductions_dir).mkdir(exist_ok=True)
        
    while reduction_queue:
        mutant_to_reduce = reduction_queue.pop(0)
        current_reduction_dir: Path = reductions_dir / str(mutant_to_reduce)
        try:
            current_reduction_dir.mkdir()
        except FileExistsError:
            print(f"Skipping reduction for mutant {mutant_to_reduce} as {current_reduction_dir} already exists.")
            continue

        print(f"Preparing to reduce mutant {mutant_to_reduce}. Details: {killed_mutant_to_test_info[mutant_to_reduce]}")

        interestingness_test_template = jinja2.Environment(
            loader=jinja2.FileSystemLoader(
                searchpath=os.path.dirname(os.path.realpath(__file__)))).get_template("interesting.py.template")
        open(current_reduction_dir / 'interesting.py', 'w').write(interestingness_test_template.render(
            program_to_check="prog.c",
            mutated_compiler_executable=args.mutated_compiler_executable,
            csmith_root=args.csmith_root,
            mutation_ids=str(mutant_to_reduce),
            min_timeout_for_mutant_compilation=MIN_TIMEOUT_FOR_MUTANT_COMPILATION,
            timeout_multiplier_for_mutant_compilation=TIMEOUT_MULTIPLIER_FOR_MUTANT_COMPILATION,
            min_timeout_for_mutant_execution=MIN_TIMEOUT_FOR_MUTANT_EXECUTION,
            timeout_multiplier_for_mutant_execution=TIMEOUT_MULTIPLIER_FOR_MUTANT_EXECUTION,
            default_runtime_timeout=DEFAULT_RUNTIME_TIMEOUT
        ))

        # Make the interestingness test executable.
        st = os.stat(current_reduction_dir / 'interesting.py')
        os.chmod(current_reduction_dir / 'interesting.py', st.st_mode | stat.S_IEXEC)
        shutil.copy(src=tests_dir / killed_mutant_to_test_info[mutant_to_reduce]['killing_test'] / 'prog.c',
                    dst=current_reduction_dir / 'prog.c')

        # 12 hour timeout
        # maybe_result: Optional[ProcessResult] = run_process_with_timeout(
        #     cmd=['creduce', 'interesting.py', 'prog.c'],
        #     timeout_seconds=43200,
        #     cwd=current_reduction_dir)
        try:
            creduce_proc = subprocess.run(['creduce', 'interesting.py', 'prog.c'], timeout=43200, cwd=current_reduction_dir)
        except subprocess.TimeoutExpired:
            print(f"Reduction of {mutant_to_reduce} timed out.")
        else:
            if creduce_proc.returncode != 0:
                 print(f"Reduction of {mutant_to_reduce} failed:")


        # TODO: Check for additional kills for the reduced program
        # TODO: Emit a summary of the mutants that the reduced program kills
        # TODO: Look into potential for automated cleanup of reduced program, e.g. to use standard data types or to
        #       be better formatted.


if __name__ == '__main__':
    main()
