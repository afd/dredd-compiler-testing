import argparse
import json
import sys
import tempfile
import subprocess
import os
import shutil

from pathlib import Path
from typing import Dict


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "work_dir",
        help="Directory containing test results. It should have subdirectories, 'killed_mutants' and 'reductions' .",
        type=Path,
    )
    parser.add_argument(
        "csmith_root",
        help="Path to a checkout of Csmith, assuming that it has been built under "
        "'build' beneath this directory.",
        type=Path,
    )
    parser.add_argument(
        "--include_timeout",
        default=False,
        action="store_true",
        help="Include timed out testcase in its final form.",
    )
    parser.add_argument(
        "--use_unreduced_testcase",
        default=False,
        action="store_true",
        help="Use original unreduced program instead of reduced program.",
    )
    args = parser.parse_args()
    work_dir: Path = args.work_dir
    if not work_dir.exists() or not work_dir.is_dir():
        print(f"Error: {str(work_dir)} is not a working directory.")
        sys.exit(1)
    killed_mutants_dir = work_dir / "killed_mutants"
    if not killed_mutants_dir.exists() or not killed_mutants_dir.is_dir():
        print(f"Error: {str(killed_mutants_dir)} does not exist.")
        sys.exit(1)
    reductions_dir = work_dir / "reductions"
    if not reductions_dir.exists() or not reductions_dir.is_dir():
        print(f"Error: {str(reductions_dir)} does not exist.")
        sys.exit(1)

    testsuite_dir: Path = work_dir / "testsuite"
    Path(testsuite_dir).mkdir(exist_ok=True)

    for testcase in reductions_dir.glob("*"):
        if not testcase.is_dir():
            continue

        # Ensure the reduction_summary and kill_info noth exist
        reductions_summary: Path = testcase / "reduction_summary.json"
        if not reductions_summary.exists():
            continue
        mutant = str(testcase).replace(str(reductions_dir) + "/", "")
        kill_info: Path = killed_mutants_dir / mutant / "kill_info.json"
        if not kill_info.exists():
            continue
        reductions_summary_json: Dict = json.load(open(reductions_summary, "r"))
        kill_info_json: Dict = json.load(open(kill_info, "r"))

        # Check that the testcase is successfully reduced.
        if (
            reductions_summary_json["reduction_status"] != "SUCCESS"
            and not (
                args.include_timeout
                and reductions_summary_json["reduction_status"] == "TIMEOUT"
            )
            and not args.use_unreduced_testcase
        ):
            print(
                f"Skipping testsuite generation for mutant {mutant} creduce has status {reductions_summary_json['reduction_status']}."
            )
            continue

        # Create a directory for this test case
        current_testsuite_dir: Path = testsuite_dir / str(mutant)
        try:
            current_testsuite_dir.mkdir()
        except FileExistsError:
            continue

        # ensure test case source file exists
        prog = testcase / (
            "prog.c" if not args.use_unreduced_testcase else "prog.c.orig"
        )
        if not prog.is_file():
            continue
        prog = os.path.abspath(prog)

        # Check whether the test is miscompilation test or crash test
        testcase_is_miscompilation_check = (
            not kill_info_json["kill_type"] == "KillStatus.KILL_COMPILER_CRASH"
        )

        print(f"Starting testsuite generaton for {testcase.name}.")

        with tempfile.TemporaryDirectory() as tmpdir:
            shutil.copy(prog, Path(tmpdir) / "prog.c")

            # Common compiler args
            compiler_args = [
                "-I",
                f"{args.csmith_root}/runtime",
                "-I",
                f"{args.csmith_root}/build/runtime",
                "-pedantic",
                "-Wall",
            ]
            if not testcase_is_miscompilation_check:
                compiler_args.append("-c")

            # compile with clang-15
            proc = subprocess.run(
                ["clang-15", *compiler_args, "-O0", "prog.c", "-o", "__clang_O0"],
                cwd=tmpdir,
                capture_output=True,
            )
            if proc.returncode != 0:
                print(
                    f"clang -O0 compilation for {testcase.name} failed with return code {proc.returncode}:"
                )
                print(proc.stderr.decode())
                continue

            # Execute the clang-15 compiled binary
            if testcase_is_miscompilation_check:
                proc = subprocess.run(["./__clang_O0"], cwd=tmpdir, capture_output=True)
                clang_output_O0 = proc.stdout

            # compile with clang-15 with -O3
            proc = subprocess.run(
                ["clang-15", *compiler_args, "-O3", "prog.c", "-o", "__clang_O3"]
                + compiler_args,
                cwd=tmpdir,
                capture_output=True,
            )
            if proc.returncode != 0:
                print(
                    f"clang -O3 compilation for {testcase.name} failed with return code {proc.returncode}:"
                )
                print(proc.stderr.decode())
                continue

            # Execute the clang-15 compiled binary
            if testcase_is_miscompilation_check:
                proc = subprocess.run(["./__clang_O3"], cwd=tmpdir, capture_output=True)
                clang_output_O3 = proc.stdout

                if clang_output_O3 != clang_output_O0:
                    print(
                        f"clang -O0 and -O3 give different output for {testcase.name}"
                    )
                    continue

            # compile with gcc with -O0
            proc = subprocess.run(
                ["gcc-12", *compiler_args, "-O0", "prog.c", "-o", "__gcc_O0"]
                + compiler_args,
                cwd=tmpdir,
                capture_output=True,
            )
            if proc.returncode != 0:
                print(
                    f"gcc -O0 compilation for {testcase.name} failed with return code {proc.returncode}:"
                )
                print(proc.stderr.decode())
                continue

            # Execute the gcc compiled binary
            if testcase_is_miscompilation_check:
                proc = subprocess.run(["./__gcc_O0"], cwd=tmpdir, capture_output=True)
                gcc_output_O0 = proc.stdout

                if gcc_output_O0 != clang_output_O0:
                    print(f"gcc and clang give different output for {testcase.name}")
                    continue

            # compile with gcc with -O3
            proc = subprocess.run(
                ["gcc-12", *compiler_args, "-O3", "prog.c", "-o", "__gcc_O3"]
                + compiler_args,
                cwd=tmpdir,
                capture_output=True,
            )
            if proc.returncode != 0:
                print(
                    f"gcc -O3 compilation for {testcase.name} failed with return code {proc.returncode}:"
                )
                print(proc.stderr.decode())
                continue

            # Execute the gcc compiled binary
            if testcase_is_miscompilation_check:
                proc = subprocess.run(["./__gcc_O3"], cwd=tmpdir, capture_output=True)
                gcc_output_O3 = proc.stdout

                if gcc_output_O3 != clang_output_O0:
                    print(f"gcc -O0 and -O3 give different output for {testcase.name}")
                    continue

            shutil.copy(prog, current_testsuite_dir / "prog.c")
            if testcase_is_miscompilation_check:
                with open(current_testsuite_dir / "prog.reference_output", "bw+") as f:
                    f.write(gcc_output_O3)

        print(f"Testsuite generaton for {testcase.name} succeed.")


if __name__ == "__main__":
    main()
