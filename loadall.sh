#!/bin/bash
if [ -z "$PORT" ]; then
  PORT=/dev/ttyUSB0
fi
if [ ! -e "$PORT" ]; then
  echo $PORT not found
  exit 1
fi
if [ "$1" = "-c" ]; then
  echo Removing all files from device
  ampy -p $PORT rmdir / >/dev/null 2>&1
  shift
fi

if [ -z "$1" ]; then
  MANIFEST="manifest.txt"
else
  MANIFEST="$1"
fi

while read -r line; do
  files=`echo $line`
  if [[ "${files:0:1}" != "#" ]]; then
    src=`echo $files | cut -d ' ' -f 1`
    dest=`echo $files | cut -d ' ' -f 2`
    if ! ampy -p $PORT put $src $dest >/dev/null 2>&1; then
      # An error, so create sub directories as needed
      DIRS=`dirname $dest | tr '/' ' '`
      dir=''
      if [ "$DIRS" != "." ]; then
        for d in $DIRS; do
          if [ -z "$dir" ]; then
            dir=$d
          else
            dir=$dir/$d
          fi
          if ! ampy -p $PORT ls $dir >/dev/null 2>&1; then
            echo Creating $dir
            ampy -p $PORT mkdir $dir >/dev/null 2>&1
          fi
        done
      fi
      # Do it again (report any errors)
      ampy -p $PORT put $src $dest
    fi
    echo Downloaded $src as $dest
  fi
done <$MANIFEST
