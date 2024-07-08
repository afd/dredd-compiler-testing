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

#ifndef LIBCLEANUPREDUCER_CLEANUP_VISITOR_H
#define LIBCLEANUPREDUCER_CLEANUP_VISITOR_H

#include <memory>
#include <set>
#include <unordered_set>
#include <utility>
#include <vector>

#include "clang/AST/Decl.h"
#include "clang/AST/DeclBase.h"
#include "clang/AST/Expr.h"
#include "clang/AST/ExprCXX.h"
#include "clang/AST/LambdaCapture.h"
#include "clang/AST/RecursiveASTVisitor.h"
#include "clang/AST/Stmt.h"
#include "clang/AST/TemplateBase.h"
#include "clang/AST/Type.h"
#include "clang/AST/TypeLoc.h"
#include "clang/Basic/SourceLocation.h"
#include "clang/Frontend/CompilerInstance.h"

namespace cleanupreducer {

class CleanupVisitor : public clang::RecursiveASTVisitor<CleanupVisitor> {
 public:
  CleanupVisitor(const clang::CompilerInstance& compiler_instance);

  bool VisitFunctionDecl(clang::FunctionDecl* function_decl);

  bool VisitCallExpr(clang::CallExpr* call_expr);

  // NOLINTNEXTLINE
  bool shouldTraversePostOrder() { return true; }

  struct FunctionCallInfo {
    std::vector<clang::FunctionDecl*> decls;
    std::vector<clang::CallExpr*> calls;
  };

  const std::map<std::string, FunctionCallInfo>& GetFunctionCallsInfo() const {
    return function_calls_info_;
  }

 private:

  const clang::CompilerInstance* compiler_instance_;

  std::map<std::string, FunctionCallInfo> function_calls_info_;

};

}  // namespace cleanupreducer

#endif  // LIBCLEANUPREDUCER_CLEANUP_VISITOR_H
