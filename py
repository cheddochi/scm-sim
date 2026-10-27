#!/bin/sh
# venv-scm 패키지가 x86_64 빌드라 Apple Silicon에서는 Rosetta로 실행해야 한다
cd "$(dirname "$0")" && PYTHONPATH=. exec arch -x86_64 "$HOME/venv-scm/bin/python" "$@"
