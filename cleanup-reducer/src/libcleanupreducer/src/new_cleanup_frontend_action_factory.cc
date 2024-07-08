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

#include "libcleanupreducer/new_cleanup_frontend_action_factory.h"

#include <cassert>
#include <set>
#include <string>

#include "clang/AST/ASTConsumer.h"
#include "clang/Frontend/CompilerInstance.h"
#include "clang/Frontend/FrontendAction.h"
#include "clang/Frontend/FrontendOptions.h"
#include "clang/Tooling/Tooling.h"
#include "libcleanupreducer/cleanup_ast_consumer.h"
#include "libcleanupreducer/cleanup_reducer_options.h"
#include "llvm/ADT/StringRef.h"
#include "llvm/Support/raw_ostream.h"

namespace cleanupreducer {

class CleanupFrontendAction : public clang::ASTFrontendAction {
 public:
  CleanupFrontendAction(const CleanupReducerOptions& options)
      : options_(&options) {}

  std::unique_ptr<clang::ASTConsumer> CreateASTConsumer(
      clang::CompilerInstance& compiler_instance,
      llvm::StringRef file) override;

  bool BeginInvocation(clang::CompilerInstance& compiler_instance) override {
    (void)compiler_instance;  // Unused.
    const bool input_exists = !getCurrentInput().isEmpty();
    (void)input_exists;  // Keep release-mode compilers happy.
    assert(input_exists && "No current file.");
    return true;
  }

 private:
  const CleanupReducerOptions* options_;
};

std::unique_ptr<clang::tooling::FrontendActionFactory>
NewCleanupFrontendActionFactory(const CleanupReducerOptions& options) {
  class CleanupFrontendActionFactory
      : public clang::tooling::FrontendActionFactory {
   public:
    CleanupFrontendActionFactory(const CleanupReducerOptions& options)
        : options_(&options) {}

    std::unique_ptr<clang::FrontendAction> create() override {
      return std::make_unique<CleanupFrontendAction>(
          *options_);
    }

   private:
    const CleanupReducerOptions* options_;
  };

  return std::make_unique<CleanupFrontendActionFactory>(
      options);
}

std::unique_ptr<clang::ASTConsumer> CleanupFrontendAction::CreateASTConsumer(
    clang::CompilerInstance& compiler_instance, llvm::StringRef file) {
  (void)file;  // Unused.
  return std::make_unique<CleanupAstConsumer>(
      compiler_instance, *options_);
}

}  // namespace cleanupreducer
