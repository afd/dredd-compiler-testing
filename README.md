# dredd-compiler-testing

Scripts to allow the Dredd mutation testing framework to be used to generate test cases that improve mutation coverage.

##

Necessary packages on AWS EC2:

```
sudo apt update
sudo apt install -y python3-pip python3.10-venv unzip zip cmake clang-15 ninja-build libzstd-dev m4 bear texinfo automake
pip3 install --upgrade pip
pip3 install build
```

## Set some environment variables

Decide where the root of the experiments should be. Everything that follows will be checked out / performed under this location. E.g.:

```
export DREDD_EXPERIMENTS_ROOT=${HOME}
```

Decide which version of the gcc you would like to mutate and put this version in the `GCC_VERSION` environment variable. E.g.:

```
export GCC_VERSION=14.1.0
```


## Get Dredd and build it

```
cd ${DREDD_EXPERIMENTS_ROOT}
git clone --recursive https://github.com/mc-imperial/dredd.git
pushd dredd/third_party/clang+llvm
    OS=ubuntu-22.04
    DREDD_LLVM_TAG=17.0.6
    curl -Lo clang+llvm.tar.xz "https://github.com/llvm/llvm-project/releases/download/llvmorg-${DREDD_LLVM_TAG}/clang+llvm-${DREDD_LLVM_TAG}-x86_64-linux-gnu-${OS}.tar.xz"
    tar xf clang+llvm.tar.xz
    mv clang+llvm-${DREDD_LLVM_TAG}-x86_64-linux-gnu-${OS}/* .
    rm clang+llvm.tar.xz
popd
DREDD_COMPILER_PATH=${DREDD_EXPERIMENTS_ROOT}/dredd/third_party/clang+llvm/bin
cmake -S dredd -B dredd/build -G Ninja -DCMAKE_C_COMPILER=${DREDD_COMPILER_PATH}/clang -DCMAKE_CXX_COMPILER=${DREDD_COMPILER_PATH}/clang++
cmake --build dredd/build --target dredd
cp dredd/build/src/dredd/dredd dredd/third_party/clang+llvm/bin/
```


## Build mutated versions of gcc

Check out this version of the gcc, download prerequisites, and keep it as a clean version of the source code (from which versions of the source code to be mutated will be copied):

```
cd ${DREDD_EXPERIMENTS_ROOT}
git clone git://gcc.gnu.org/git/gcc.git gcc-${GCC_VERSION}-clean
pushd gcc-${LLVM_VERSION}-clean
git checkout releases/gcc-${LLVM_VERSION}
./contrib/download_prerequisites
popd

sudo apt-get install flex
sudo apt-get install g++-multilib
```

Now make two copies of the gcc --one that will be mutated, and another that will be used for the tracking of covered mutants.

```
cp -r gcc-${GCC_VERSION}-clean gcc-${GCC_VERSION}-mutated
cp -r gcc-${GCC_VERSION}-clean gcc-${GCC_VERSION}-mutant-tracking
```

Generate a compilation database for each of these copies of gcc, and build it on bear so we have a compilation database available in each build root for Dredd. 

Bear is known to get ["stuck"](https://github.com/rizsotto/Bear/issues/443) when the number of concurrent build `-j$(nproc)` is too high. If this happens, try lowering the number of concurrent builds.

```
cd ${DREDD_EXPERIMENTS_ROOT}
for kind in mutated mutant-tracking
do
  SOURCE_DIR=gcc-${GCC_VERSION}-${kind}
  BUILD_DIR=gcc-${GCC_VERSION}-${kind}-build
  mkdir ${BUILD_DIR}
  pushd ${BUILD_DIR}
  ../${SOURCE_DIR}/configure --disable-bootstrap --enable-multilib --enable-languages=c,c++  --prefix=${DREDD_EXPERIMENTS_ROOT}/gcc-toolchains-${GCC_VERSION}-${kind}
  bear -- make -j$(nproc)
  popd
done
```

Record the location of the `dredd` executable in an environment variable.

```
export DREDD_EXECUTABLE=${DREDD_EXPERIMENTS_ROOT}/dredd/third_party/clang+llvm/bin/dredd
```

Mutate all `tree-ssa-*.cc` files under `gcc` in the copy of GCC designated for mutation:

```
cd ${DREDD_EXPERIMENTS_ROOT}
FILES_TO_MUTATE=($(ls gcc-${GCC_VERSION}-mutated/gcc/tree-ssa-*.cc | sort))
echo ${FILES[*]}
${DREDD_EXECUTABLE} -p gcc-${GCC_VERSION}-mutated-build/compile_commands.json --mutation-info-file gcc-mutated.json ${FILES_TO_MUTATE[*]}
```

Apply mutation tracking to all `tree-ssa-*.cc` files under `gcc` in the copy of GCC designated for mutation tracking:

```
cd ${DREDD_EXPERIMENTS_ROOT}
FILES_TO_MUTATE=($(ls gcc-${GCC_VERSION}-mutant-tracking/gcc/tree-ssa-*.cc | sort))
echo ${FILES[*]}
${DREDD_EXECUTABLE} --only-track-mutant-coverage -p gcc-${GCC_VERSION}-mutant-tracking-build/compile_commands.json --mutation-info-file gcc-mutant-tracking.json ${FILES_TO_MUTATE[*]}
```

Build entire GCC project for both copies (this will take a long time):

```
cd ${DREDD_EXPERIMENTS_ROOT}
for kind in mutated mutant-tracking
do
  BUILD_DIR=gcc-${GCC_VERSION}-${kind}-build
  pushd ${BUILD_DIR}
  make -j$(nprc)
  popd
done
```

## Build and interactive install steps

```
cd ${DREDD_EXPERIMENTS_ROOT}
git clone https://github.com/mc-imperial/dredd-compiler-testing.git
pushd dredd-compiler-testing
python3 -m build
python3 -m pip install -e .
popd
```

## Scripts to figure out which Dredd-induced mutants are killed by the GCC `test-ssa` testsuite


You point it at:

- A checkout of the LLVM test suite
- A compilation database for the test suite
- The mutated compiler and mutant tracking compiler
- Associated JSON files with mutation info

It considers the tests in the suite in turn and determines which
mutants they kill.

Command to invoke `llvm-test-suite-runner`:

```
llvm-test-suite-runner llvm-mutated.json llvm-mutant-tracking.json llvm-${LLVM_VERSION}-mutated-build/bin llvm-${LLVM_VERSION}-mutant-tracking-build/bin $(pwd)/llvm-test-suite llvm-test-suite-build/compile_commands.json
```

To run many instances in parallel (16):

```
for i in `seq 1 16`; do llvm-test-suite-runner llvm-mutated.json llvm-mutant-tracking.json llvm-${LLVM_VERSION}-mutated-build/bin llvm-${LLVM_VERSION}-mutant-tracking-build/bin $(pwd)/llvm-test-suite llvm-test-suite-build/compile_commands.json & done
```

To kill them:

```
pkill -9 -f llvm-test-suite
```

Watch out for left over `clang` processes!




# LLVM regression test runner

```
for kind in mutated mutant-tracking
do
  pushd llvm-${LLVM_VERSION}-${kind}
    git apply ../dredd-compiler-testing/lit-patches/${kind}.patch
  popd
done
```

Command to invoke regression test suite runner:

```
llvm-regression-tests-runner llvm-mutated.json llvm-mutant-tracking.json llvm-${LLVM_VERSION}-mutated-build/bin llvm-${LLVM_VERSION}-mutant-tracking-build/bin llvm-${LLVM_VERSION}-mutated/llvm/test/Transforms/InstCombine llvm-${LLVM_VERSION}-mutant-tracking/llvm/test/Transforms/InstCombine
```

To run many instances in parallel (16):

```
for i in `seq 1 16`; do llvm-regression-tests-runner llvm-mutated.json llvm-mutant-tracking.json llvm-${LLVM_VERSION}-mutated-build/bin llvm-${LLVM_VERSION}-mutant-tracking-build/bin llvm-${LLVM_VERSION}-mutated/llvm/test/Transforms/InstCombine llvm-${LLVM_VERSION}-mutant-tracking/llvm/test/Transforms/InstCombine & done
```

To kill them: TODO


# Csmith runner

Get and build Csmith:

```
cd ${DREDD_EXPERIMENTS_ROOT}
git clone https://github.com/csmith-project/csmith.git
cmake -S csmith -B csmith/build -G Ninja
cmake --build csmith/build
```

`csmith-runner` and `reduce-new-kills` both use `clang-15`'s sanitiser, which might not work on newer Linux distros. A workaround for this issue is to reduce ASLR entropy:
```
sudo sysctl vm.mmap_rnd_bits=28
```

```
csmith-runner llvm-mutated.json llvm-mutant-tracking.json llvm-${LLVM_VERSION}-mutated-build/bin/clang llvm-${LLVM_VERSION}-mutant-tracking-build/bin/clang ${DREDD_EXPERIMENTS_ROOT}/csmith
```

To run many instances in parallel (16):

```
for i in `seq 1 16`; do csmith-runner llvm-mutated.json llvm-mutant-tracking.json llvm-${LLVM_VERSION}-mutated-build/bin/clang llvm-${LLVM_VERSION}-mutant-tracking-build/bin/clang ${DREDD_EXPERIMENTS_ROOT}/csmith & done
```

To kill them:

```
pkill -9 -f csmith-runner
```


# Results analysis

To see a list of the Csmith tests that have led to "actionable" kills (kills for which test case reduction will lead to a runnable killing test case with oracle), do:

```
cd ${DREDD_EXPERIMENTS_ROOT}
analyse-results work
```

# Reductions
Install `creduce` and `gcc-12`:
```
sudo apt install creduce gcc-12
```

```
cd ${DREDD_EXPERIMENTS_ROOT}
reduce-new-kills work ${DREDD_EXPERIMENTS_ROOT}/llvm-${LLVM_VERSION}-mutated-build/bin/clang ${DREDD_EXPERIMENTS_ROOT}/csmith
```

To run many instances in parallel (16):

```
for i in `seq 1 16`; do reduce-new-kills work ${DREDD_EXPERIMENTS_ROOT}/llvm-${LLVM_VERSION}-mutated-build/bin/clang ${DREDD_EXPERIMENTS_ROOT}/csmith & done
```