#!/usr/bin/env bash
# coding: utf-8

if [[ "$OSTYPE" == "linux-gnu" ]]; then
  SYSTEM_KIND='linux';
elif [[ "$OSTYPE" == "darwin"* ]]; then
  # Mac OSX
  SYSTEM_KIND='mac';
else
  # Unknown.
  SYSTEM_KIND='unknown';
  echo 'unknown system type'
  exit 1;
fi

