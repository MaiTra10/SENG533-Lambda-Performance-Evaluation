#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAMBDA_DIR="$SCRIPT_DIR"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()  { echo -e "${GREEN}[build]${NC} $*"; }
error() { echo -e "${RED}[error]${NC} $*"; exit 1; }

make_zip() {
  local out="$1"; shift
  zip -j "$out" "$@" > /dev/null
}

make_zip_dir() {
  local out="$1" dir="$2"
  (cd "$dir" && zip -r "$out" . -x "*.pyc" -x "*__pycache__*" > /dev/null)
}

# ─── GO ───────────────────────────────────────
build_go() {
  local go_root="$LAMBDA_DIR/go"

  [ -f "$go_root/go.mod" ] || error "go.mod not found"

  # CPU
  local src="$go_root/experiment1"
  info "Building Go CPU"

  for arch in arm x86; do
    if [ "$arch" = "arm" ]; then goarch="arm64"; else goarch="amd64"; fi

    out_dir="$src/deploy/$arch"
    mkdir -p "$out_dir"

    (
      cd "$go_root"
      GOOS=linux GOARCH="$goarch" CGO_ENABLED=0 \
      go build -tags lambda.norpc -ldflags="-s -w" \
      -o "$out_dir/bootstrap" ./experiment1/...
    )

    make_zip "$out_dir/bootstrap.zip" "$out_dir/bootstrap"
    rm "$out_dir/bootstrap"
  done

  # I/O
  for variant in placeholder-x86 placeholder-arm; do

    if [[ "$variant" == *"arm"* ]]; then
      goarch="arm64"
    else
      goarch="amd64"
    fi

    src="$go_root/$variant"
    out_dir="$src/deploy"
    mkdir -p "$out_dir"

    info "Building Go I/O -> $variant"

    (
      cd "$go_root"
      GOOS=linux GOARCH="$goarch" CGO_ENABLED=0 \
      go build -tags lambda.norpc -ldflags="-s -w" \
      -o "$out_dir/bootstrap" ./$variant
    )

    make_zip "$out_dir/bootstrap.zip" "$out_dir/bootstrap"
    rm "$out_dir/bootstrap"
  done
}

# ─── JAVA ─────────────────────────────────────
build_java() {

  # CPU
  local src="$LAMBDA_DIR/java/experiment1"
  local build_dir="$src/build"
  local out_dir="$src/deploy"

  info "Building Java CPU"

  mkdir -p "$out_dir"
  rm -rf "$build_dir" && mkdir -p "$build_dir"

  (
    cd "$src"
    javac -cp "lib/*" -d "$build_dir" Handler.java

    if [ -d "lib" ]; then
      for jar in lib/*.jar; do
        (cd "$build_dir" && jar xf "$OLDPWD/$jar")
      done
    fi
  )

  jar cf "$out_dir/bootstrap.jar" -C "$build_dir" .
  rm -rf "$build_dir"

  # I/O
  local src="$LAMBDA_DIR/java/placeholder"
  local build_dir="$src/build"
  local out_dir="$src/deploy"

  info "Building Java I/O"

  mkdir -p "$out_dir"
  rm -rf "$build_dir" && mkdir -p "$build_dir"

  (
    cd "$src"

    javac -cp "lib/*" -d "$build_dir" Handler.java

    for jar in lib/*.jar; do
      (cd "$build_dir" && jar xf "$OLDPWD/$jar")
    done
  )

  jar cf "$out_dir/bootstrap.jar" -C "$build_dir" .
  rm -rf "$build_dir"
}

# ─── PYTHON ───────────────────────────────────
build_python() {

  # CPU
  local src="$LAMBDA_DIR/python/experiment1"
  local out_dir="$src/deploy"

  info "Building Python CPU"

  mkdir -p "$out_dir"
  rm -f "$out_dir/bootstrap.zip"

  (
    cd "$src"
    make_zip "$out_dir/bootstrap.zip" *.py
  )

  # I/O
  local src="$LAMBDA_DIR/python/placeholder"
  local out_dir="$src/deploy"

  info "Building Python I/O"

  mkdir -p "$out_dir"
  rm -f "$out_dir/bootstrap.zip"

  (
    cd "$src"
    make_zip "$out_dir/bootstrap.zip" *.py
  )
}

# ─── MAIN ─────────────────────────────────────
case "${1:-all}" in
  go) build_go ;;
  java) build_java ;;
  python) build_python ;;
  all)
    build_go
    build_java
    build_python

    echo ""
    info "All builds complete"
    ;;
  *)
    echo "Usage: $0 [go|java|python|all]"
    exit 1
    ;;
esac