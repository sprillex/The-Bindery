
import os
import shutil

class ModuleManager:
    def __init__(self, modules_dir="modules"):
        self.modules_dir = modules_dir
        if not os.path.exists(modules_dir):
            os.makedirs(modules_dir)

    def create_module(self, module_name, zim_file_path, title, description=""):
        # Create module directory
        module_path = os.path.join(self.modules_dir, module_name)
        if os.path.exists(module_path):
            shutil.rmtree(module_path)
        os.makedirs(module_path)

        # Move/Copy ZIM file
        zim_filename = os.path.basename(zim_file_path)
        dest_zim_path = os.path.join(module_path, zim_filename)
        shutil.copy2(zim_file_path, dest_zim_path)

        # Create rachel-index.php
        # This is a best-guess template based on RACHEL documentation
        # The link usually points to the Kiwix server.
        # We assume the ZIM filename (without extension) is the ID used by Kiwix,
        # or Kiwix uses the internal ZIM UUID.
        # Usually it's better to rely on Kiwix to detect it, but we need a link on the homepage.
        # RACHEL's kiwix-start.pl likely maps the file to a URL.

        # We'll use the filename as the potential URL path for now.
        zim_id = os.path.splitext(zim_filename)[0]

        php_content = f"""
        <div class="indexmodule">
            <a href="http://<?php echo $_SERVER['SERVER_ADDR']; ?>:81/{zim_filename}/">
                <div class="indexmodulelink">
                    <h3>{title}</h3>
                    <p>{description}</p>
                </div>
            </a>
        </div>
        """

        with open(os.path.join(module_path, "rachel-index.php"), "w") as f:
            f.write(php_content)

        print(f"Module {module_name} created at {module_path}")
        return module_path

if __name__ == "__main__":
    # Test module creation
    # Create a dummy ZIM first if not exists
    if not os.path.exists("test_output.zim"):
        with open("test_output.zim", "w") as f:
            f.write("dummy zim content")

    manager = ModuleManager("test_modules")
    manager.create_module("test_module", "test_output.zim", "Test Module", "A test module")
