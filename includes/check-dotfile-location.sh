#!/usr/bin/env bash
# coding: utf-8

ls "$DOTFILE_FOLDER" >/dev/null 2>&1

if [ "$?" -ne 0 ]; then
    echo "dotfile location is not $DOTFILE_FOLDER. Exiting";
    exit 1;
else
    echo "dotfile folder found";
    cd "$DOTFILE_FOLDER" || {
        echo "can not change diretory to $DOTFILE_FOLDER";
        exit 1;
    }
fi
