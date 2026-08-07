PREFIX     ?= /usr
DESTDIR    ?=

APP        := gdl-zapret-gui
LIBDIR     := $(DESTDIR)$(PREFIX)/lib/$(APP)
BINDIR     := $(DESTDIR)$(PREFIX)/bin
DESKTOPDIR := $(DESTDIR)$(PREFIX)/share/applications

SRC_PY     := main.py gdl_zapret

.PHONY: all install uninstall

all:
	@echo "Usage: make install [PREFIX=/usr] [DESTDIR=]"

install:
	# --- python sources ---
	install -d $(LIBDIR)
	cp -r $(SRC_PY) $(LIBDIR)/

	# --- launcher wrapper ---
	install -d $(BINDIR)
	printf '#!/bin/sh\nexec python3 $(PREFIX)/lib/$(APP)/main.py "$$@"\n' \
		> $(BINDIR)/$(APP)
	chmod 755 $(BINDIR)/$(APP)

	# --- .desktop ---
	install -d $(DESKTOPDIR)
	install -m 644 $(APP).desktop $(DESKTOPDIR)/$(APP).desktop

uninstall:
	rm -rf  $(LIBDIR)
	rm -f   $(BINDIR)/$(APP)
	rm -f   $(DESKTOPDIR)/$(APP).desktop
