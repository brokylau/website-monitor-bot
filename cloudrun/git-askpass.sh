#!/usr/bin/env sh

case "$1" in
  *Username*)
    printf '%s\n' "${GITHUB_USERNAME}"
    ;;
  *Password*)
    printf '%s\n' "${GITHUB_TOKEN}"
    ;;
  *)
    printf '\n'
    ;;
esac
