#!/bin/bash
set -e
cd /data/openpilot
clang++ -o selfdrive/pandad/panda_comms.o -c -std=c++1z -D__TICI__ -mcpu=cortex-a57 -DQCOM2 -g -fPIC -O2 -Wunused -Werror -Wshadow -Wno-unknown-warning-option -Wno-inconsistent-missing-override -Wno-c99-designator -Wno-reorder-init-list -Wno-vla-cxx-extension -I. -Imsgq -I/usr/local/venv/lib/python3.12/site-packages/capnproto/install/include -I/usr/local/venv/lib/python3.12/site-packages/libusb/install/include selfdrive/pandad/panda_comms.cc
cd selfdrive/pandad
ar rcs libpanda.a panda.o panda_comms.o spi.o
clang++ -o pandad main.o pandad.o panda_safety.o -L. -lpanda /data/openpilot/common/libcommon.a /data/openpilot/cereal/libsocketmaster.a /data/openpilot/cereal/libcereal.a /data/openpilot/msgq_repo/libmsgq.a /usr/local/venv/lib/python3.12/site-packages/json11/install/lib/libjson11.a -L/usr/local/venv/lib/python3.12/site-packages/libusb/install/lib -lusb-1.0 -L/usr/local/venv/lib/python3.12/site-packages/zeromq/install/lib -lzmq -L/usr/local/venv/lib/python3.12/site-packages/capnproto/install/lib -lcapnp -lkj -lpthread -lm -lrt
chmod +x pandad
echo rebuild_done
