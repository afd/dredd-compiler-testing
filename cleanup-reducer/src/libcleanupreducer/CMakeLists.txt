# Copyright 2024   The Dredd Project Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

cmake_minimum_required(VERSION 3.13)

add_library(
  libcleanupreducer STATIC
  include/libcleanupreducer/cleanup_reducer_options.h
  include/libcleanupreducer/new_cleanup_frontend_action_factory.h
  include/libcleanupreducer/util.h
  include_private/include/libcleanupreducer/cleanup_ast_consumer.h
  include_private/include/libcleanupreducer/cleanup_visitor.h
  src/cleanup_ast_consumer.cc
  src/cleanup_visitor.cc
  src/new_cleanup_frontend_action_factory.cc
  src/util.cc
)

target_include_directories(
  libcleanupreducer
  PUBLIC include
  PRIVATE include_private/include)

target_include_directories(libcleanupreducer SYSTEM PRIVATE ${CMAKE_BINARY_DIR}/src)

set(CLANG_LIBS clangTooling clangTransformer)

foreach(clang_target ${CLANG_LIBS})
  if(NOT TARGET ${clang_target})
    message(FATAL_ERROR "${clang_target} is not a target")
  endif()
endforeach()

target_link_libraries(libcleanupreducer PRIVATE ${CLANG_LIBS})

target_compile_features(libcleanupreducer PUBLIC cxx_std_20)
