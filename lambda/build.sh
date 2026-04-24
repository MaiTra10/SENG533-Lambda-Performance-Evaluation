# Source: Claude Sonnet 4.6

#!/bin/bash
set -euo pipefail

# ─────────────────────────────────────────────
# Lambda build script — experiment1
#
# Output structure:
#   lambda/go/experiment1/deploy/arm/bootstrap.zip   <- arm64 (Graviton)
#   lambda/go/experiment1/deploy/x86/bootstrap.zip   <- x86_64
#   lambda/java/experiment1/deploy/bootstrap.zip
#   lambda/python/experiment1/deploy/bootstrap.zip
# ─────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAMBDA_DIR="$SCRIPT_DIR"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()  { echo -e "${GREEN}[build]${NC} $*"; }
warn()  { echo -e "${YELLOW}[warn]${NC}  $*"; }
error() { echo -e "${RED}[error]${NC} $*"; exit 1; }

# ─── ZIP HELPERS ──────────────────────────────
# zip is not available by default on Windows (Git Bash).
# Falls back to PowerShell Compress-Archive, matching the same pattern
# used in the project's other build scripts.

# Converts a Git Bash Unix path to a Windows path for PowerShell.
# e.g. /c/Users/foo/bar -> C:\Users\foo\bar
to_win_path() {
  echo "$1" | sed 's|^/\([a-zA-Z]\)/|\1:/|' | sed 's|/|\\|g'
}

# make_zip <output.zip> <file> [file2 ...]
# Zips listed files flat (no directory structure) into output.zip.
make_zip() {
  local out="$1"; shift
  if command -v zip &>/dev/null; then
    zip -j "$out" "$@"
  else
    local win_out
    win_out="$(to_win_path "$out")"
    local first=true
    for f in "$@"; do
      local win_f
      win_f="$(to_win_path "$f")"
      if $first; then
        powershell.exe -Command "Compress-Archive -Path '${win_f}' -DestinationPath '${win_out}' -Force"
        first=false
      else
        powershell.exe -Command "Compress-Archive -Path '${win_f}' -DestinationPath '${win_out}' -Update"
      fi
    done
  fi
}

# make_zip_dir <output.zip> <dir>
# Zips all contents of a directory into output.zip.
make_zip_dir() {
  local out="$1" dir="$2"
  if command -v zip &>/dev/null; then
    (cd "$dir" && zip -r "$out" . -x "*.pyc" -x "*__pycache__*" -x "*.dist-info/*")
  else
    local win_out win_dir
    win_out="$(to_win_path "$out")"
    win_dir="$(to_win_path "$dir")"
    powershell.exe -Command "Compress-Archive -Path '${win_dir}\\*' -DestinationPath '${win_out}' -Force"
  fi
}

# ─── GO ───────────────────────────────────────
# go.mod lives at lambda/go/ and is shared across all experiments.
# Builds both arm64 and x86_64 into separate deploy subdirs.
build_go() {
  local go_root="$LAMBDA_DIR/go"
  local src="$go_root/experiment1"
  info "Building Go (arm64 + x86_64) -> $src"

  [ -f "$go_root/go.mod" ] || error "go.mod not found in $go_root"
  [ -d "$src" ] || error "experiment1 directory not found in $go_root"

  local arch goarch out_dir
  for arch in arm x86; do
    if [ "$arch" = "arm" ]; then goarch="arm64"; else goarch="amd64"; fi

    out_dir="$src/deploy/$arch"
    mkdir -p "$out_dir"

    info "  Compiling GOARCH=$goarch"
    (
      cd "$go_root"
      GOOS=linux GOARCH="$goarch" CGO_ENABLED=0 \
        go build -tags lambda.norpc -ldflags="-s -w" -o "$out_dir/bootstrap" ./experiment1/...
    )

    make_zip "$out_dir/bootstrap.zip" "$out_dir/bootstrap"
    rm "$out_dir/bootstrap"
    info "  Done -> $out_dir/bootstrap.zip"
  done
}

# ─── JAVA ─────────────────────────────────────
# Structure: java/experiment1/Handler.java + lib/*.jar
# Compiles with javac, bundles lib jars into a fat JAR
build_java() {
  local src="$LAMBDA_DIR/java/experiment1"
  local build_dir="$src/build"
  local out_dir="$src/deploy"
  info "Building Java -> $src"
 
  [ -f "$src/Handler.java" ] || error "Handler.java not found in $src"
 
  # Build classpath from all jars in lib/
  local classpath=""
  if [ -d "$src/lib" ] && compgen -G "$src/lib/*.jar" > /dev/null 2>&1; then
    classpath=$(find "$src/lib" -name "*.jar" | tr '\n' ':' | sed 's/:$//')
    info "  Classpath: $classpath"
  fi
 
  mkdir -p "$out_dir"
  rm -rf "$build_dir" && mkdir -p "$build_dir"
 
  (
    cd "$src"
 
    # Compile Handler.java
    if [ -n "$classpath" ]; then
      javac -cp "$classpath" -d "$build_dir" Handler.java
    else
      javac -d "$build_dir" Handler.java
    fi
 
    # Unpack lib jars into build dir for a fat JAR
    if [ -d "lib" ]; then
      for jar in lib/*.jar; do
        (cd "$build_dir" && jar xf "$OLDPWD/$jar")
      done
    fi
 
  )
 
  # Package fat JAR directly as bootstrap.jar into deploy/
  jar cf "$out_dir/bootstrap.jar" -C "$build_dir" .
  rm -rf "$build_dir"
 
  info "Java build complete -> $out_dir/bootstrap.jar"
}

# ─── PYTHON ───────────────────────────────────
# Structure: python/experiment1/main.py + matrixMultiplication.py
build_python() {
  local src="$LAMBDA_DIR/python/experiment1"
  local out_dir="$src/deploy"
  info "Building Python -> $src"

  [ -f "$src/main.py" ] || error "main.py not found in $src"

  mkdir -p "$out_dir"
  rm -f "$out_dir/bootstrap.zip"

  (
    cd "$src"

    if [ -f "requirements.txt" ]; then
      info "  Installing Python dependencies"
      pip install -r requirements.txt -t package/ -q
      make_zip_dir "$out_dir/bootstrap.zip" "package"
      make_zip "$out_dir/bootstrap.zip" *.py
      rm -rf package/
    else
      make_zip "$out_dir/bootstrap.zip" *.py
    fi
  )

  info "Python build complete -> $out_dir/bootstrap.zip"
}

# ─── MAIN ─────────────────────────────────────
case "${1:-all}" in
  go)     build_go ;;
  java)   build_java ;;
  python) build_python ;;
  all)
    build_go
    build_java
    build_python
    echo ""
    info "All builds complete:"
    echo "  $LAMBDA_DIR/go/experiment1/deploy/arm/bootstrap.zip"
    echo "  $LAMBDA_DIR/go/experiment1/deploy/x86/bootstrap.zip"
    echo "  $LAMBDA_DIR/java/experiment1/deploy/bootstrap.zip"
    echo "  $LAMBDA_DIR/python/experiment1/deploy/bootstrap.zip"
    ;;
  *)
    echo "Usage: $0 [go|java|python|all]"
    exit 1
    ;;
esac
