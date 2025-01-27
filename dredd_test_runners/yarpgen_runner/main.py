import argparse
import shutil

import json
import os
import random
import tempfile
import time

from dredd_test_runners.common.constants import DEFAULT_COMPILATION_TIMEOUT, DEFAULT_RUNTIME_TIMEOUT
from dredd_test_runners.common.hash_file import hash_file
from dredd_test_runners.common.mutation_tree import MutationTree
from dredd_test_runners.common.run_process_with_timeout import ProcessResult, run_process_with_timeout
from dredd_test_runners.common.run_test_with_mutants import run_test_with_mutants, KillStatus

from pathlib import Path
from typing import List, Set


def still_testing(start_time_for_overall_testing: float,
                  time_of_last_kill: float,
                  total_test_time: int,
                  maximum_time_since_last_kill: int) -> bool:
    if 0 < total_test_time < int(time.time() - start_time_for_overall_testing):
        return False
    if 0 < maximum_time_since_last_kill < int(time.time() - time_of_last_kill):
        return False
    return True


def main():
    start_time_for_overall_testing: float = time.time()
    time_of_last_kill: float = start_time_for_overall_testing

    parser = argparse.ArgumentParser()
    parser.add_argument("mutation_info_file",
                        help="File containing information about mutations, generated when Dredd was used to actually "
                             "mutate the source code.",
                        type=Path)
    parser.add_argument("mutation_info_file_for_mutant_coverage_tracking",
                        help="File containing information about mutations, generated when Dredd was used to "
                             "instrument the source code to track mutant coverage; this will be compared against the "
                             "regular mutation info file to ensure that tracked mutants match applied mutants.",
                        type=Path)
    parser.add_argument("mutated_compiler_executable",
                        help="Path to the executable for the Dredd-mutated compiler.",
                        type=Path)
    parser.add_argument("mutant_tracking_compiler_executable",
                        help="Path to the executable for the compiler instrumented to track mutants.",
                        type=Path)
    parser.add_argument("yarpgen_root", help="Path to a checkout of YARPgen, assuming that it has been built under "
                                             "'build' beneath this directory.",
                        type=Path)
    parser.add_argument("--generator_timeout",
                        default=20,
                        help="Time in seconds to allow for generation of a program.",
                        type=int)
    parser.add_argument("--compile_timeout",
                        default=DEFAULT_COMPILATION_TIMEOUT,
                        help="Time in seconds to allow for compilation of a generated program (without mutation).",
                        type=int)
    parser.add_argument("--run_timeout",
                        default=DEFAULT_RUNTIME_TIMEOUT,
                        help="Time in seconds to allow for running a generated program (without mutation).",
                        type=int)
    parser.add_argument("--seed",
                        help="Seed for random number generator.",
                        type=int)
    parser.add_argument("--total_test_time",
                        default=86400,
                        help="Total time to allow for testing, in seconds. Default is 24 hours. To test indefinitely, "
                             "pass 0.",
                        type=int)
    parser.add_argument("--maximum_time_since_last_kill",
                        default=86400,
                        help="Cease testing if a kill has not occurred for this length of time. Default is 24 hours. "
                             "To test indefinitely, pass 0.",
                        type=int)
    args = parser.parse_args()

    assert args.mutation_info_file != args.mutation_info_file_for_mutant_coverage_tracking

    print("Building the real mutation tree...")
    with open(args.mutation_info_file, 'r') as json_input:
        mutation_tree = MutationTree(json.load(json_input))
    print("Built!")
    print("Building the mutation tree associated with mutant coverage tracking...")
    with open(args.mutation_info_file_for_mutant_coverage_tracking, 'r') as json_input:
        mutation_tree_for_coverage_tracking = MutationTree(json.load(json_input))
    print("Built!")
    print("Checking that the two mutation trees match...")
    assert mutation_tree.mutation_id_to_node_id == mutation_tree_for_coverage_tracking.mutation_id_to_node_id
    assert mutation_tree.parent_map == mutation_tree_for_coverage_tracking.parent_map
    assert mutation_tree.num_nodes == mutation_tree_for_coverage_tracking.num_nodes
    assert mutation_tree.num_mutations == mutation_tree_for_coverage_tracking.num_mutations
    print("Check complete!")

    if args.seed is not None:
        random.seed(args.seed)

    with tempfile.TemporaryDirectory() as temp_dir_for_generated_code:
        yarpgen_out_dir = Path(temp_dir_for_generated_code, '__gen')
        dredd_covered_mutants_path: Path = Path(temp_dir_for_generated_code, '__dredd_covered_mutants')
        generated_program_exe_compiled_with_no_mutants = Path(temp_dir_for_generated_code, '__regular.exe')
        generated_program_exe_compiled_with_mutant_tracking = Path(temp_dir_for_generated_code, '__tracking.exe')
        mutant_exe = Path(temp_dir_for_generated_code, '__mutant.exe')
        asan_ubsan_compiled_exe = Path(temp_dir_for_generated_code, '__asan_ubsan.exe')
        msan_compiled_exe = Path(temp_dir_for_generated_code, '__msan.exe')

        killed_mutants: Set[int] = set()
        unkilled_mutants: Set[int] = set(range(0, mutation_tree.num_mutations))

        # Make a work directory in which information about the mutant killing process will be stored. If this already
        # exists that's OK - there may be other processes working on mutant killing, or we may be continuing a job that
        # crashed previously.
        Path("work").mkdir(exist_ok=True)
        Path("work/tests").mkdir(exist_ok=True)
        Path("work/killed_mutants").mkdir(exist_ok=True)

        while still_testing(total_test_time=args.total_test_time,
                            maximum_time_since_last_kill=args.maximum_time_since_last_kill,
                            start_time_for_overall_testing=start_time_for_overall_testing,
                            time_of_last_kill=time_of_last_kill):
            if dredd_covered_mutants_path.exists():
                os.remove(dredd_covered_mutants_path)
            if yarpgen_out_dir.exists():
                shutil.rmtree(yarpgen_out_dir)
            if generated_program_exe_compiled_with_no_mutants.exists():
                os.remove(generated_program_exe_compiled_with_no_mutants)
            if generated_program_exe_compiled_with_mutant_tracking.exists():
                os.remove(generated_program_exe_compiled_with_mutant_tracking)
            if asan_ubsan_compiled_exe.exists():
                os.remove(asan_ubsan_compiled_exe)
            if msan_compiled_exe.exists():
                os.remove(msan_compiled_exe)


            # Generate a Yarpgen program
            os.mkdir(yarpgen_out_dir)
            yarpgen_seed = random.randint(0, 2 ** 32 - 1)
            yarpgen_cmd = [str(args.yarpgen_root / "build" / "yarpgen"),
                           "--std=c",
                           "--seed=" + str(yarpgen_seed),
                           "-o",
                           str(yarpgen_out_dir)]

            yarpgen_result: ProcessResult = run_process_with_timeout(cmd=yarpgen_cmd,
                                                                     timeout_seconds=args.generator_timeout)
            if yarpgen_result is None:
                print(f"YARPgen timed out (seed {yarpgen_seed})")
                continue

            if yarpgen_result.returncode != 0:
                print("YARPgen terminated abnormally.")
                print(' '.join(yarpgen_cmd))
                print(f"stdout: {yarpgen_result.stdout}")
                print(f"stderr: {yarpgen_result.stderr}")
                continue

            compiler_args = ["-O3",
                             yarpgen_out_dir / "driver.c", yarpgen_out_dir / "func.c"]

            # Compile the program without mutation.
            regular_compile_cmd = [args.mutated_compiler_executable]\
                + compiler_args\
                + ["-o", generated_program_exe_compiled_with_no_mutants]

            compile_time_start: float = time.time()
            regular_compile_result: ProcessResult = run_process_with_timeout(cmd=regular_compile_cmd,
                                                                             timeout_seconds=args.compile_timeout)
            compile_time_end: float = time.time()
            compile_time = compile_time_end - compile_time_start

            if regular_compile_result is None:
                print("Compiler timeout.")
                continue
            if regular_compile_result.returncode != 0:
                print("Compilation failed without mutants.")
                print(f"stdout: {regular_compile_result.stdout.decode('utf-8')}")
                print(f"stderr: {regular_compile_result.stderr.decode('utf-8')}")
                continue

            regular_hash = hash_file(str(generated_program_exe_compiled_with_no_mutants))

            run_time_start: float = time.time()
            regular_execution_result: ProcessResult = run_process_with_timeout(
                cmd=[str(generated_program_exe_compiled_with_no_mutants)], timeout_seconds=args.run_timeout)
            run_time_end: float = time.time()
            run_time = run_time_end - run_time_start

            if regular_execution_result is None:
                print("Runtime timeout.")
                continue
            if regular_execution_result.returncode != 0:
                print("Execution of generated program failed without mutants.")
                continue

            # Compile and run the program with sanitizers - it should run without error. This is to guard against YARPGen
            # emitting programs that feature undefined behaviour.
            asan_ubsan_compile_command = ["clang-15"] + compiler_args + ["-fsanitize=address,undefined",
                                                                         "-fno-sanitize-recover=undefined",
                                                                         "-o",
                                                                         asan_ubsan_compiled_exe]
            asan_ubsan_compilation_result: ProcessResult = run_process_with_timeout(
                asan_ubsan_compile_command,
                timeout_seconds=args.compile_timeout * 10)
            if asan_ubsan_compilation_result is None:
                print("Compilation of generated program with asan/ubsan timed out.")
                continue
            if asan_ubsan_compilation_result.returncode != 0:
                print("Compilation of generated program with asan/ubsan failed.")
                continue
            asan_ubsan_execution_result: ProcessResult = run_process_with_timeout(
                cmd=[str(asan_ubsan_compiled_exe)], timeout_seconds=args.run_timeout * 10)
            if asan_ubsan_execution_result is None:
                print("Execution of generated program with asan/ubsan timed out.")
                continue
            if asan_ubsan_execution_result.returncode != 0:
                print("Asan/ubsan error detected in generated program.")
                continue

            msan_compile_command = ["clang-15"] + compiler_args + ["-fsanitize=memory",
                                                                   "-o",
                                                                   msan_compiled_exe]
            msan_compilation_result: ProcessResult = run_process_with_timeout(
                msan_compile_command,
                timeout_seconds=args.compile_timeout * 10)
            if msan_compilation_result is None:
                print("Compilation of generated program with msan timed out.")
                continue
            if msan_compilation_result.returncode != 0:
                print("Compilation of generated program with msan failed.")
                continue
            msan_execution_result: ProcessResult = run_process_with_timeout(
                cmd=[str(msan_compiled_exe)], timeout_seconds=args.run_timeout * 10)
            if msan_execution_result is None:
                print("Execution of generated program with msan timed out.")
                continue
            if msan_execution_result.returncode != 0:
                print("Msan error detected in generated program.")
                continue
            # End of use of sanitizers on the generated program - it's looking good!

            # Compile the program with the mutant tracking compiler.
            tracking_environment = os.environ.copy()
            tracking_environment["DREDD_MUTANT_TRACKING_FILE"] = str(dredd_covered_mutants_path)
            tracking_compile_cmd = [args.mutant_tracking_compiler_executable]\
                + compiler_args\
                + ["-o", generated_program_exe_compiled_with_mutant_tracking]
            if run_process_with_timeout(cmd=tracking_compile_cmd, timeout_seconds=args.compile_timeout,
                                        env=tracking_environment) is None:
                print("Mutant tracking compilation timed out.")
                continue

            # Try to create a directory for this YARPgen test. It is very unlikely that it already exists, but this
            # could happen if two test workers pick the same seed. If that happens, this worker will skip the test.
            yarpgen_test_name: str = "yarpgen_" + str(yarpgen_seed)
            test_output_directory: Path = Path("work/tests/" + yarpgen_test_name)
            try:
                test_output_directory.mkdir()
            except FileExistsError:
                print(f"Skipping seed {yarpgen_seed} as a directory for it already exists")
                continue
            shutil.copy(src=yarpgen_out_dir / "driver.c", dst=test_output_directory / "driver.c")
            shutil.copy(src=yarpgen_out_dir / "func.c", dst=test_output_directory / "func.c")
            shutil.copy(src=yarpgen_out_dir / "init.h", dst=test_output_directory / "init.h")

            # Load file contents into a list. We go from list to set to list to eliminate duplicates.
            covered_by_this_test: List[int] = list(set([int(line.strip()) for line in
                                                        open(dredd_covered_mutants_path, 'r').readlines()]))
            covered_by_this_test.sort()
            candidate_mutants_for_this_test: List[int] = ([m for m in covered_by_this_test if m not in killed_mutants])
            print("Number of mutants to try: " + str(len(candidate_mutants_for_this_test)))

            already_killed_by_other_tests: List[int] = ([m for m in covered_by_this_test if m in killed_mutants])
            killed_by_this_test: List[int] = []
            covered_but_not_killed_by_this_test: List[int] = []

            for mutant in candidate_mutants_for_this_test:

                if not still_testing(total_test_time=args.total_test_time,
                                     maximum_time_since_last_kill=args.maximum_time_since_last_kill,
                                     start_time_for_overall_testing=start_time_for_overall_testing,
                                     time_of_last_kill=time_of_last_kill):
                    break

                mutant_path = Path("work/killed_mutants/" + str(mutant))
                if mutant_path.exists():
                    print("Skipping mutant " + str(mutant) + " as it is noted as already killed.")
                    unkilled_mutants.remove(mutant)
                    killed_mutants.add(mutant)
                    already_killed_by_other_tests.append(mutant)
                    continue
                print("Trying mutant " + str(mutant))
                mutant_result = run_test_with_mutants(mutants=[mutant],
                                                      compiler_path=str(args.mutated_compiler_executable),
                                                      compiler_args=compiler_args,
                                                      compile_time=compile_time,
                                                      run_time=run_time,
                                                      binary_hash_non_mutated=regular_hash,
                                                      execution_result_non_mutated=regular_execution_result,
                                                      mutant_exe_path=mutant_exe)
                print("Mutant result: " + str(mutant_result))
                if mutant_result == KillStatus.SURVIVED_IDENTICAL \
                        or mutant_result == KillStatus.SURVIVED_BINARY_DIFFERENCE:
                    covered_but_not_killed_by_this_test.append(mutant)
                    continue

                unkilled_mutants.remove(mutant)
                killed_mutants.add(mutant)
                killed_by_this_test.append(mutant)
                time_of_last_kill = time.time()
                print(f"Kill! Mutants killed so far: {len(killed_mutants)}")
                try:
                    mutant_path.mkdir()
                    print("Writing kill info to file.")
                    with open(mutant_path / "kill_info.json", "w") as outfile:
                        json.dump({"killing_test": yarpgen_test_name,
                                   "kill_type": str(mutant_result)}, outfile)
                except FileExistsError:
                    print(f"Mutant {mutant} was independently discovered to be killed.")
                    continue

            terminating_test_process: bool = not still_testing(
                total_test_time=args.total_test_time,
                maximum_time_since_last_kill=args.maximum_time_since_last_kill,
                start_time_for_overall_testing=start_time_for_overall_testing,
                time_of_last_kill=time_of_last_kill)

            all_considered_mutants = killed_by_this_test \
                + covered_but_not_killed_by_this_test \
                + already_killed_by_other_tests
            all_considered_mutants.sort()

            if covered_by_this_test != all_considered_mutants:
                assert terminating_test_process
                terminated_early: bool = True
            else:
                terminated_early: bool = False

            killed_by_this_test.sort()
            covered_but_not_killed_by_this_test.sort()
            already_killed_by_other_tests.sort()
            with open(test_output_directory / "kill_summary.json", "w") as outfile:
                json.dump({"terminated_early": terminated_early,
                           "covered_mutants": covered_by_this_test,
                           "killed_mutants": killed_by_this_test,
                           "skipped_mutants": already_killed_by_other_tests,
                           "survived_mutants": covered_but_not_killed_by_this_test}, outfile)


if __name__ == '__main__':
    main()
