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

#ifndef LIBCLEANUPREDUCER_NEW_CLEANUP_FRONTEND_ACTION_FACTORY_H
#define LIBCLEANUPREDUCER_NEW_CLEANUP_FRONTEND_ACTION_FACTORY_H

#include <memory>

#include "clang/Tooling/Tooling.h"
#include "libcleanupreducer/cleanup_reducer_options.h"

namespace cleanupreducer {

std::unique_ptr<clang::tooling::FrontendActionFactory>
NewCleanupFrontendActionFactory(const CleanupReducerOptions& options);

}  // namespace cleanupreducer

#endif  // LIBCLEANUPREDUCER_NEW_CLEANUP_FRONTEND_ACTION_FACTORY_H
