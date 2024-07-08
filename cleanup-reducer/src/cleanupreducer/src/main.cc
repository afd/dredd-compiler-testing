// Copyright 2024 The Dredd Project Authors
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

#include <fstream>
#include <memory>
#include <string>

#include "clang/Tooling/CommonOptionsParser.h"
#include "clang/Tooling/Tooling.h"
#include "libcleanupreducer/cleanup_reducer_options.h"
#include "libcleanupreducer/new_cleanup_frontend_action_factory.h"
#include "llvm/ADT/ArrayRef.h"
#include "llvm/ADT/StringRef.h"
#include "llvm/Support/CommandLine.h"
#include "llvm/Support/Error.h"
#include "llvm/Support/Signals.h"
#include "llvm/Support/raw_ostream.h"

#if defined(__clang__)
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wexit-time-destructors"
#pragma clang diagnostic ignored "-Wglobal-constructors"
#elif defined(__GNUC__)
#pragma GCC diagnostic push
#elif defined(_MSC_VER)
#pragma warning(push)
#endif

// Set up the command line options
// NOLINTNEXTLINE
static llvm::cl::extrahelp common_help(
    clang::tooling::CommonOptionsParser::HelpMessage);
// NOLINTNEXTLINE
static llvm::cl::OptionCategory cleanup_category("cleanup options");
// NOLINTNEXTLINE
static llvm::cl::opt<bool> dump_asts(
    "dump-asts",
    llvm::cl::desc("Dump each AST that is processed; useful for debugging"),
    llvm::cl::cat(cleanup_category));
static llvm::cl::opt<std::string> reduction_type(
    "reduction-type", llvm::cl::Required,
    llvm::cl::desc(
        "The kind of reduction that should be reported on or attempted. Options are: removeparam"),
    llvm::cl::cat(cleanup_category));
static llvm::cl::opt<int32_t> opportunity_to_take(
    "opportunity-to-take",
    llvm::cl::desc("The id of the reduction opportunity of the given kind that should be taken. If not specified, the number of available opportunities of this kind will be displayed."),
    llvm::cl::cat(cleanup_category),
    llvm::cl::init(-1));

#if defined(__clang__)
#pragma clang diagnostic pop
#elif defined(__GNUC__)
#pragma GCC diagnostic pop
#elif defined(_MSC_VER)
#pragma warning(pop)
#endif

int main(int argc, const char** argv) {
  llvm::sys::PrintStackTraceOnErrorSignal(argv[0]);

  llvm::Expected<clang::tooling::CommonOptionsParser> options =
      clang::tooling::CommonOptionsParser::create(argc, argv, cleanup_category,
                                                  llvm::cl::OneOrMore);
  if (!options) {
    const std::string error_message = toString(options.takeError());
    llvm::errs() << error_message;
    return 1;
  }

  cleanupreducer::CleanupReducerOptions cleanup_reducer_options;
  cleanup_reducer_options.dump_asts = dump_asts;
  if (reduction_type == "removeparam") {
    cleanup_reducer_options.reduction_type = cleanupreducer::ReductionType::REMOVEPARAM;
  } else {
    llvm::errs() << "Unknown reduction type: " << reduction_type << "\n";
    return 1;
  }
  if (opportunity_to_take >= 0) {
    cleanup_reducer_options.opportunity_to_take = static_cast<uint32_t>(opportunity_to_take);
  } else {
    cleanup_reducer_options.opportunity_to_take = {};
  }

  clang::tooling::ClangTool Tool(options.get().getCompilations(),
                                 options.get().getSourcePathList());



  const std::unique_ptr<clang::tooling::FrontendActionFactory> factory =
      cleanupreducer::NewCleanupFrontendActionFactory(cleanup_reducer_options);

  const int return_code = Tool.run(factory.get());

  return return_code;
}
