UUID := request-more-time@example.com
SOURCES := customDurationStore.js malcontentClient.js parentalControlsIntegration.js remainingTimeIndicator.js requestDialog.js timerQuery.js
EXTENSION_BASE ?= $(if $(XDG_DATA_HOME),$(XDG_DATA_HOME),$(HOME)/.local/share)
EXTENSION_DIR := $(EXTENSION_BASE)/gnome-shell/extensions/$(UUID)
RUNTIME_FILES := metadata.json stylesheet.css extension.js $(SOURCES)

.PHONY: pack check install

pack:
	gnome-extensions pack . --force --out-dir=. $(SOURCES:%=--extra-source=%)

check:
	@for file in extension.js $(SOURCES); do node --check "$$file"; done

install:
	install -d "$(EXTENSION_DIR)"
	install -m 0644 $(RUNTIME_FILES) "$(EXTENSION_DIR)/"
	@echo "Installed $(UUID) to $(EXTENSION_DIR)"
	@echo "Enable it with: gnome-extensions enable $(UUID)"
