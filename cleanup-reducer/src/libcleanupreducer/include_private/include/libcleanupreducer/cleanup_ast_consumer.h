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

#ifndef LIBCLEANUPREDUCER_CLEANUP_AST_CONSUMER_H
#define LIBCLEANUPREDUCER_CLEANUP_AST_CONSUMER_H

#include <memory>
#include <string>
#include <unordered_set>

#include "clang/AST/ASTConsumer.h"
#include "clang/AST/ASTContext.h"
#include "clang/Frontend/CompilerInstance.h"
#include "clang/Rewrite/Core/Rewriter.h"
#include "libcleanupreducer/cleanup_reducer_options.h"
#include "libcleanupreducer/cleanup_visitor.h"

namespace cleanupreducer {

class CleanupAstConsumer : public clang::ASTConsumer {
 public:
  CleanupAstConsumer(const clang::CompilerInstance& compiler_instance, const CleanupReducerOptions& options)
      : compiler_instance_(&compiler_instance), options_(&options),
        visitor_(std::make_unique<CleanupVisitor>(compiler_instance))
  {}

  void HandleTranslationUnit(clang::ASTContext& ast_context) override;

 private:

  template<typename T>
  void RemoveParameter(std::function<T*(uint32_t)> index_to_param, uint32_t param_index,
                       clang::ASTContext& ast_context);

  const clang::CompilerInstance* compiler_instance_;

  // True if and only if the AST being consumed should be dumped; useful for
  // debugging.
  const CleanupReducerOptions* options_;

  std::unique_ptr<CleanupVisitor> visitor_;

  clang::Rewriter rewriter_;

};

}  // namespace cleanupreducer

#endif  // LIBCLEANUPREDUCER_CLEANUP_AST_CONSUMER_H
