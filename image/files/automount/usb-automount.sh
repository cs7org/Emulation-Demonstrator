#!/bin/bash
set -e

DEVICE="/dev/$1"

PART=$(/usr/bin/udisksctl mount -b "$DEVICE" | awk '{print $NF}')

if [ "$PART" = "" ]; then
    exit 1
fi

chmod +r,o+x $PART
DIR=$(dirname "$PART")
chmod +r,o+x $DIR
