BLENDER_EXE ?= $(shell which blender)
ifeq ($(BLENDER_EXE),)
$(error "Blender executable not found. Please set BLENDER_EXE to the path of your Blender installation.")
endif

BLENDER_DIR := $(dir $(BLENDER_EXE))
BLENDER_VERSION := $(shell $(BLENDER_EXE) --version | head -n 1 | awk '{print substr($$2, 1, 3)}')
PYTHON_EXE := $(shell find $(BLENDER_DIR) -type f -name "python3*" | head -n 1)

PIPMODULES := gdstk numpy pyyaml

.PHONY: install install_pip

.DEFAULT: install

install_pip:
	@$(PYTHON_EXE) -m pip install --upgrade --target=$(HOME)/.config/blender/$(BLENDER_VERSION)/scripts/addons/modules/ $(PIPMODULES)
	@echo "Python modules installed to Blender's add-on modules directory."

install: install_pip
	@echo "Installing BlenderGDS add-on..."
	@mkdir -p $(HOME)/.config/blender/$(BLENDER_VERSION)/scripts/addons/
	@cp -r ./import_gdsii $(HOME)/.config/blender/$(BLENDER_VERSION)/scripts/addons/
	@echo "Add-on installed successfully."

remove:
	@echo "Removing BlenderGDS add-on..."
	@rm -rf $(HOME)/.config/blender/$(BLENDER_VERSION)/scripts/addons/import_gdsii
	@echo "Add-on removed successfully."
