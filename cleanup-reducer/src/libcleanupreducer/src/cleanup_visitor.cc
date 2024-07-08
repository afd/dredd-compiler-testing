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

#include "libcleanupreducer/cleanup_visitor.h"

#include <cassert>
#include <cstddef>
#include <memory>

#include "clang/AST/ASTContext.h"
#include "clang/AST/ASTTypeTraits.h"
#include "clang/AST/Decl.h"
#include "clang/AST/DeclBase.h"
#include "clang/AST/DeclCXX.h"
#include "clang/AST/Expr.h"
#include "clang/AST/ExprCXX.h"
#include "clang/AST/LambdaCapture.h"
#include "clang/AST/OperationKinds.h"
#include "clang/AST/ParentMapContext.h"
#include "clang/AST/RecursiveASTVisitor.h"
#include "clang/AST/Stmt.h"
#include "clang/AST/TemplateBase.h"
#include "clang/AST/Type.h"
#include "clang/AST/TypeLoc.h"
#include "clang/Basic/LangOptions.h"
#include "clang/Basic/SourceLocation.h"
#include "clang/Frontend/CompilerInstance.h"
#include "libcleanupreducer/util.h"
#include "llvm/Support/Casting.h"

namespace cleanupreducer {

CleanupVisitor::CleanupVisitor(const clang::CompilerInstance& compiler_instance)
    : compiler_instance_(&compiler_instance) {
}

bool CleanupVisitor::VisitFunctionDecl(clang::FunctionDecl* function_decl) {
  if (GetSourceRangeInMainFile(compiler_instance_->getPreprocessor(), *function_decl).isInvalid()) {
    return true;
  }

  if (function_calls_info_.find(function_decl->getNameAsString()) == function_calls_info_.end()) {
    function_calls_info_[function_decl->getNameAsString()] = FunctionCallInfo();
  }
  auto& function_call_info = *function_calls_info_.find(function_decl->getNameAsString());
  function_call_info.second.decls.push_back(function_decl);
  return true;
}

bool CleanupVisitor::VisitCallExpr(clang::CallExpr* call_expr) {
  if (GetSourceRangeInMainFile(compiler_instance_->getPreprocessor(), *call_expr).isInvalid()) {
    return true;
  }

  if (auto* direct_callee = call_expr->getDirectCallee()) {
    if (function_calls_info_.find(direct_callee->getNameAsString()) == function_calls_info_.end()) {
      function_calls_info_[direct_callee->getNameAsString()] = FunctionCallInfo();
    }
    auto& function_call_info = *function_calls_info_.find(direct_callee->getNameAsString());
    function_call_info.second.calls.push_back(call_expr);
  }
  return true;
}

}  // namespace cleanupreducer
