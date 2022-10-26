#!/usr/bin/env bash
# coding: utf-8

if [[ "$OSTYPE" == "linux-gnu" ]]; then
  export SYSTEM_KIND='linux';
elif [[ "$OSTYPE" == "darwin"* ]]; then
  # Mac OSX
  export SYSTEM_KIND='mac';
else
  # Unknown.
  export SYSTEM_KIND='unknown';
  echo 'unknown system type. Continuing despite that.'
fi

