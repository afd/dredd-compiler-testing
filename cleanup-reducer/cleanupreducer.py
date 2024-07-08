import argparse
import json
import os
import tempfile
import time



def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("file_to_reduce",
                        help="The C source file to reduce.",
                        type=Path)
    parser.add_argument("interestingness_test",
                        help="The interestingness test.",
                        type=Path)
    parser.add_argument("cleanupreducer_clang_tool",
                        help="The Clang tool for performing cleanup reduction actions.",
                        type=Path)
    args = parser.parse_args()

    some_reduction_kind_had_an_effect: bool = True
    while some_reduction_kind_had_an_effect:
        some_reduction_kind_had_an_effect: bool = False
        for reduction_kind in ["removeparam"]:
            this_reduction_kind_had_an_effect: bool = True
            while this_reduction_kind_had_an_effect:
                this_reduction_kind_had_an_effect = False
                opportunities_to_try = get_num_opportunities()
                if opportunities_to_try == 0:
                    break
                for opportunity in range(0, opportunities_to_try):
                    if is_intersting(take_opportunity(opportunity)):
                        this_reduction_kind_had_an_effect = True
                        some_reduction_kind_had_an_effect = True
                        update_most_interesting()
                        break








if __name__ == '__main__':
    main()
