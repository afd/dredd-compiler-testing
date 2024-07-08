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

#include "libcleanupreducer/cleanup_ast_consumer.h"

#include <cassert>
#include <set>
#include <sstream>
#include <string>
#include <unordered_set>
#include <vector>

#include "clang/AST/ASTContext.h"
#include "clang/AST/Decl.h"
#include "clang/Basic/Diagnostic.h"
#include "clang/Basic/FileEntry.h"
#include "clang/Basic/LangOptions.h"
#include "clang/Basic/SourceLocation.h"
#include "clang/Basic/SourceManager.h"
#include "clang/Frontend/CompilerInstance.h"
#include "clang/Rewrite/Core/Rewriter.h"
#include "clang/Tooling/Transformer/SourceCode.h"
#include "llvm/ADT/StringRef.h"
#include "llvm/Support/raw_ostream.h"

namespace cleanupreducer {

template<typename T>
void CleanupAstConsumer::RemoveParameter(std::function<T*(uint32_t)> index_to_param, uint32_t param_index,
                                        clang::ASTContext& ast_context) {
  clang::SourceLocation begin_loc;
  clang::SourceLocation end_loc;
  if (param_index == 0) {
    begin_loc = index_to_param(param_index)->getSourceRange().getBegin();
    const clang::CharSourceRange source_range_of_param =
        clang::CharSourceRange::getTokenRange(
            index_to_param(param_index)->getSourceRange());
    const clang::CharSourceRange source_range_of_param_extended =
        clang::tooling::maybeExtendRange(
            source_range_of_param, clang::tok::TokenKind::comma, ast_context);
    end_loc = source_range_of_param_extended.getEnd();
  } else {
    const clang::CharSourceRange source_range_of_previous_param =
        clang::CharSourceRange::getTokenRange(
            index_to_param(param_index - 1)->getSourceRange());
    const clang::CharSourceRange source_range_of_previous_param_extended =
        clang::tooling::maybeExtendRange(
            source_range_of_previous_param, clang::tok::TokenKind::comma, ast_context);
    begin_loc = source_range_of_previous_param_extended.getEnd();
    end_loc = index_to_param(param_index)->getSourceRange().getEnd();
  }
  rewriter_.RemoveText(clang::SourceRange(begin_loc, end_loc));
}


void CleanupAstConsumer::HandleTranslationUnit(clang::ASTContext& ast_context) {
  const std::string filename =
      ast_context.getSourceManager()
          .getFileEntryForID(ast_context.getSourceManager().getMainFileID())
          ->getName()
          .str();

  llvm::errs() << "Processing " << filename << "\n";

  if (ast_context.getDiagnostics().hasErrorOccurred()) {
    llvm::errs() << "Skipping due to errors\n";
    return;
  }

  if (options_->dump_asts) {
    llvm::errs() << "AST:\n";
    ast_context.getTranslationUnitDecl()->dump();
    llvm::errs() << "\n";
  }
  visitor_->TraverseDecl(ast_context.getTranslationUnitDecl());

  rewriter_.setSourceMgr(compiler_instance_->getSourceManager(),
                         compiler_instance_->getLangOpts());

  if (!options_->opportunity_to_take.has_value()) {
    uint32_t num_opportunities = 0;
    for (auto& entry : visitor_->GetFunctionCallsInfo()) {
      if (!entry.second.decls.empty()) {
        num_opportunities += entry.second.decls[0]->getNumParams();
      }
    }
    llvm::errs() << num_opportunities << "\n";
    return;
  }

  uint32_t counter = 0;
  for (const auto& entry : visitor_->GetFunctionCallsInfo()) {
    if (!entry.second.decls.empty()) {
      for (uint32_t param_index = 0;
           param_index < entry.second.decls[0]->getNumParams(); param_index++) {
        if (counter == options_->opportunity_to_take) {
          for (auto* decl : entry.second.decls) {
            RemoveParameter<clang::ParmVarDecl>([&decl](uint32_t index) -> clang::ParmVarDecl* {
              return decl->getParamDecl(index);
            }, param_index, ast_context);
          }
          for (auto* call : entry.second.calls) {
            RemoveParameter<clang::Expr>([&call](uint32_t index) -> clang::Expr* {
              return call->getArg(index);
            }, param_index, ast_context);
          }
        }
        counter++;
      }
    }
  }
  rewriter_.overwriteChangedFiles();
}

}  // namespace cleanupreducer
