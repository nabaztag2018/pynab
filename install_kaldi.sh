#!/bin/sh

case `uname` in
  "Darwin")
    echo "kaldi is not available precompiled on MacOS X"
    echo "Please install it and make it available to pkg-config"
    exit 1
    ;;
  "Linux")
    case `uname -m` in
      "x86_64")
        wget -q -O - "https://github.com/pguyot/kaldi/releases/download/v5.4.1/kaldi-c3260f2-linux_x86_64-vfp.tar.xz" | sudo tar xJ -C /
        sudo ldconfig
        ;;
      "armv6l")
        # This probably is a Pi Zero
        wget -q -O - "https://github.com/pguyot/kaldi/releases/download/v5.4.1/kaldi-c3260f2-linux_armv6l-vfp.tar.xz" | sudo tar xJ -C /
        sudo ldconfig
        ;;
      *)
        echo "Unknown architecture. Please install kaldi and make it available to pkg-config"
        exit 1
        ;;
    esac
    ;;
  *)
    echo "Unknown OS. Please install kaldi and make it available to pkg-config"
    exit 1
    ;;  
esac
