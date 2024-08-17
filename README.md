# dredd-compiler-testing

Scripts to allow the Dredd mutation testing framework to be used to generate test cases that improve mutation coverage.

##

Necessary packages on AWS EC2:

```
sudo apt update
sudo apt install -y python3-pip python3.10-venv unzip zip bear cmake clang-15 ninja-build libzstd-dev m4 gcc-multilib python2
pip3 install --upgrade pip
pip3 install build
```

## Set some environment variables

Decide where the root of the experiments should be. Everything that follows will be checked out / performed under this location. E.g.:

```
export DREDD_EXPERIMENTS_ROOT=${HOME}
```

Decide which version of the LLVM project you would like to mutate and put this version in the `LLVM_VERSION` environment variable. E.g.:

```
export LLVM_VERSION=3.5.0
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

# (Optional) For reproducibility, checkout the dredd version used below
pushd dredd
git checkout 2074c34a701211777554e4d2d6acdbb8fc1166f2
popd

DREDD_COMPILER_PATH=${DREDD_EXPERIMENTS_ROOT}/dredd/third_party/clang+llvm/bin
cmake -S dredd -B dredd/build -G Ninja -DCMAKE_C_COMPILER=${DREDD_COMPILER_PATH}/clang -DCMAKE_CXX_COMPILER=${DREDD_COMPILER_PATH}/clang++
cmake --build dredd/build --target dredd
cp dredd/build/src/dredd/dredd dredd/third_party/clang+llvm/bin/
```


## Build mutated versions of clang

Check out this version of the LLVM project, and keep it as a clean version of the source code (from which versions of the source code to be mutated will be copied):

```
curl -Lo llvm-${LLVM_VERSION}.src.tar.xz https://releases.llvm.org/${LLVM_VERSION}/llvm-${LLVM_VERSION}.src.tar.xz
tar -xf llvm-${LLVM_VERSION}.src.tar.xz
rm llvm-${LLVM_VERSION}.src.tar.xz
mv llvm-${LLVM_VERSION}.src llvm-${LLVM_VERSION}-clean

pushd llvm-${LLVM_VERSION}-clean/tools
curl -Lo cfe-${LLVM_VERSION}.src.tar.xz https://releases.llvm.org/${LLVM_VERSION}/cfe-${LLVM_VERSION}.src.tar.xz
tar -xf cfe-${LLVM_VERSION}.src.tar.xz
rm cfe-${LLVM_VERSION}.src.tar.xz
mv cfe-${LLVM_VERSION}.src clang
popd
```
Apply the patch to the source code to ensure it builds with a modern compiler and that some scripts run with the correct version of Python:
```
pushd llvm-3.5.0-clean
git apply ../dredd-compiler-testing/llvm.patch
popd
```

Check out an old version of GCC, apply a patch to ensure it builds with a modern compiler, and then build it. The installation path will serve as the GCC toolchain when building Clang. These steps ensure that Clang can link properly.
```
wget ftp://ftp.gnu.org/gnu/gcc/gcc-4.8.2/gcc-4.8.2.tar.bz2
tar -xvjf gcc-4.8.2.tar.bz2
cd gcc-4.8.2
./contrib/download_prerequisites
git apply ../dredd-compiler-testing/gcc-4.8.2.patch
cd ..
mkdir gcc-4.8.2-build
cd gcc-4.8.2-build
$PWD/../gcc-4.8.2/configure --prefix=$HOME/toolchains --enable-languages=c,c++
make -j$(nproc)
make install
cd ..
```

Now make two copies of the LLVM project--one that will be mutated, and another that will be used for the tracking of covered mutants.

```
cp -r llvm-${LLVM_VERSION}-clean llvm-${LLVM_VERSION}-mutated
cp -r llvm-${LLVM_VERSION}-clean llvm-${LLVM_VERSION}-mutant-tracking
```

Generate a compilation database for each of these copies of LLVM, and build a core component so that all auto-generated code is in place for Dredd.

```
cd ${DREDD_EXPERIMENTS_ROOT}
for kind in mutated mutant-tracking
do
  SOURCE_DIR=llvm-${LLVM_VERSION}-${kind}
  BUILD_DIR=llvm-${LLVM_VERSION}-${kind}-build
  mkdir ${BUILD_DIR}
  cmake -S "${SOURCE_DIR}" -B "${BUILD_DIR}" -G Ninja -DCMAKE_EXPORT_COMPILE_COMMANDS=ON -DCMAKE_CXX_FLAGS="-w" -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_COMPILER=${DREDD_COMPILER_PATH}/clang -DCMAKE_CXX_COMPILER=${DREDD_COMPILER_PATH}/clang++ -DGCC_INSTALL_PREFIX=${HOME}/toolchains
  # Build something minimal to ensure all auto-generated pieces of code are created.
  cmake --build "${BUILD_DIR}" --target all
done
```

Record the location of the `dredd` executable in an environment variable.

```
export DREDD_EXECUTABLE=${DREDD_EXPERIMENTS_ROOT}/dredd/third_party/clang+llvm/bin/dredd
```

Mutate all `.cpp` files under `Transforms` in the copy of LLVM designated for mutation:

```
# (Optional) `sort` depend on locale, for reproducibility:
export LC_ALL=C

cd ${DREDD_EXPERIMENTS_ROOT}
FILES_TO_MUTATE=($(ls llvm-${LLVM_VERSION}-mutated/lib/Transforms/**/*.cpp | sort))
echo ${FILES[*]}
${DREDD_EXECUTABLE} -p llvm-${LLVM_VERSION}-mutated-build/compile_commands.json --mutation-info-file llvm-mutated.json ${FILES_TO_MUTATE[*]}
```

Apply mutation tracking to all `.cpp` files under `Transforms` in the copy of LLVM designated for mutation tracking:

```
# (Optional) `sort` depend on locale, for reproducibility:
export LC_ALL=C

cd ${DREDD_EXPERIMENTS_ROOT}
FILES_TO_MUTATE=($(ls llvm-${LLVM_VERSION}-mutant-tracking/lib/Transforms/**/*.cpp | sort))
echo ${FILES[*]}
${DREDD_EXECUTABLE} --only-track-mutant-coverage -p llvm-${LLVM_VERSION}-mutant-tracking-build/compile_commands.json --mutation-info-file llvm-mutant-tracking.json ${FILES_TO_MUTATE[*]}
```

Build entire LLVM project for both copies (this will take a long time):

```
cd ${DREDD_EXPERIMENTS_ROOT}
for kind in mutated mutant-tracking
do
  BUILD_DIR=llvm-${LLVM_VERSION}-${kind}-build
  cmake --build ${BUILD_DIR}
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

## Scripts to figure out which Dredd-induced mutants are killed by the LLVM test suite

```
curl -Lo test-suite-${LLVM_VERSION}.src.tar.xz https://releases.llvm.org/${LLVM_VERSION}/test-suite-${LLVM_VERSION}.src.tar.xz
tar -xf test-suite-${LLVM_VERSION}.src.tar.xz
rm test-suite-${LLVM_VERSION}.src.tar.xz
mv test-suite-${LLVM_VERSION}.src llvm-test-suite
```

Executing `test-suite` with Makefiles is non-trivial. Instead, we made use of `LNT` testing infrastructure to execute the test, and `bear` to record the compilation database.
```
sudo apt install python3-virtualenv bison byacc
virtualenv ~/mysandbox
git clone https://github.com/llvm/llvm-lnt.git ~/lnt
~/mysandbox/bin/python ~/lnt/setup.py develop
source mysandbox/bin/activate
bear -- lnt runtest nt --sandbox /tmp/SANDBOX --cc /home/ubuntu/llvm-${LLVM_VERSION}-mutated-build/bin/clang  --test-suite llvm-test-suite -j$(nproc)
deactivate
```

You point it at:

- A checkout of the LLVM test suite
- A compilation database for the test suite
- The mutated compiler and mutant tracking compiler
- Associated JSON files with mutation info

It considers the tests in the suite in turn and determines which
mutants they kill.

Command to invoke `llvm-test-suite-runner`:

```
llvm-test-suite-runner llvm-mutated.json llvm-mutant-tracking.json llvm-${LLVM_VERSION}-mutated-build/bin llvm-${LLVM_VERSION}-mutant-tracking-build/bin $(pwd)/llvm-test-suite $(pwd)/compile_commands.json
```

To run many instances in parallel (16):

```
for i in `seq 1 16`; do llvm-test-suite-runner llvm-mutated.json llvm-mutant-tracking.json llvm-${LLVM_VERSION}-mutated-build/bin llvm-${LLVM_VERSION}-mutant-tracking-build/bin $(pwd)/llvm-test-suite $(pwd)/compile_commands.json & done
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
llvm-regression-tests-runner llvm-mutated.json llvm-mutant-tracking.json llvm-${LLVM_VERSION}-mutated-build/bin llvm-${LLVM_VERSION}-mutant-tracking-build/bin llvm-${LLVM_VERSION}-mutated/test/Transforms llvm-${LLVM_VERSION}-mutant-tracking/test/Transforms
```

To run many instances in parallel (16):

```
for i in `seq 1 16`; do llvm-regression-tests-runner llvm-mutated.json llvm-mutant-tracking.json llvm-${LLVM_VERSION}-mutated-build/bin llvm-${LLVM_VERSION}-mutant-tracking-build/bin llvm-${LLVM_VERSION}-mutated/test/Transforms llvm-${LLVM_VERSION}-mutant-tracking/test/Transforms & done
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

# (or alternatively) YARPGen runner

Get and build YARPGen:
```
git clone https://github.com/intel/yarpgen.git
pushd yarpgen
# (Optional) for reproducibility
git checkout 700f5a2f564aab697ef8ff1b26afd50c3e729ecb

mkdir build
cd build
cmake ..
make -j$(proc)
popd
```

```
yarpgen-runner llvm-mutated.json llvm-mutant-tracking.json llvm-${LLVM_VERSION}-mutated-build/bin/clang llvm-${LLVM_VERSION}-mutant-tracking-build/bin/clang ${DREDD_EXPERIMENTS_ROOT}/yarpgen
```

To run many instances in parallel (16):

```
for i in `seq 1 16`; do yarpgen-runner llvm-mutated.json llvm-mutant-tracking.json llvm-${LLVM_VERSION}-mutated-build/bin/clang llvm-${LLVM_VERSION}-mutant-tracking-build/bin/clang ${DREDD_EXPERIMENTS_ROOT}/yarpgen & done
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