CC ?= cc
AR ?= ar
SANITIZERS ?= address,undefined
CPPFLAGS += -Iinclude
CFLAGS ?= -O2 -g
CFLAGS += -std=c11 -Wall -Wextra -Wpedantic -Werror
LDLIBS += -lm

CORE_NAMES = preprocess poly ransac render lane
CORE_OBJECTS = $(addprefix build/,$(addsuffix .o,$(CORE_NAMES)))
HOST_OBJECTS = build/main.o build/image_io.o

.PHONY: all core host firmware-check test integration sanitize clean
all: core firmware-check
core: build/liblane.a
host: build/lane_detect
firmware-check: build/nios_entry.o build/nios_main.o

build:
	mkdir -p $@

build/%.o: src/%.c | build
	$(CC) $(CPPFLAGS) $(CFLAGS) -MMD -MP -c $< -o $@

build/main.o: host/main.c | build
	$(CC) $(CPPFLAGS) $(CFLAGS) -MMD -MP -c $< -o $@

build/image_io.o: host/image_io.c | build
	$(CC) $(CPPFLAGS) $(CFLAGS) -MMD -MP -c $< -o $@

build/nios_entry.o: nios/entry.c | build
	$(CC) $(CPPFLAGS) $(CFLAGS) -MMD -MP -c $< -o $@

build/nios_main.o: nios/main.c | build
	$(CC) $(CPPFLAGS) $(CFLAGS) -MMD -MP -c $< -o $@

build/liblane.a: $(CORE_OBJECTS)
	$(AR) rcs $@ $^

build/lane_detect: $(HOST_OBJECTS) build/liblane.a
	$(CC) $(CFLAGS) $(LDFLAGS) $^ $(LDLIBS) -o $@

build/test_core: tests/test_core.c build/nios_entry.o build/liblane.a | build
	$(CC) $(CPPFLAGS) -Inios $(CFLAGS) $(LDFLAGS) $^ $(LDLIBS) -o $@

test: build/test_core
	./build/test_core

integration: host
	python3 tests/test_pipeline.py

sanitize:
	$(MAKE) clean
	UBSAN_OPTIONS=halt_on_error=1 $(MAKE) CFLAGS='-O1 -g -std=c11 -Wall -Wextra -Wpedantic -Werror -fsanitize=$(SANITIZERS) -fno-omit-frame-pointer' LDFLAGS='-fsanitize=$(SANITIZERS)' all test integration

clean:
	rm -rf build

-include $(CORE_OBJECTS:.o=.d) $(HOST_OBJECTS:.o=.d) build/nios_entry.d build/nios_main.d
