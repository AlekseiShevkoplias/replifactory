import os

def add_gitkeep_to_empty_dirs(base_path):
    """Recursively add .gitkeep to every empty directory under the base path."""
    for root, dirs, files in os.walk(base_path):
        for directory in dirs:
            dir_path = os.path.join(root, directory)
            if not os.listdir(dir_path):  # Check if the directory is empty
                gitkeep_path = os.path.join(dir_path, '.gitkeep')
                with open(gitkeep_path, 'w') as f:
                    pass  # Create an empty .gitkeep file
                print(f"Added .gitkeep to: {dir_path}")

if __name__ == "__main__":
    base_path = os.getcwd()  # Change to the desired base path if needed
    add_gitkeep_to_empty_dirs(base_path)
