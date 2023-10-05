import os

class DockerManager:
    
    here = os.path.abspath(__file__)
    requirements_file = os.path.normpath(os.path.join(here, "..", "requirements.txt"))
    docker_file = os.path.normpath(os.path.join(here,"..", "Dockerfile"))

    def add_dependency(language, dependency):
        lines = []
        language_section_found = False
        dependency_name = dependency.split('==')[0]

        with open(DockerManager.requirements_file, 'r') as f:
            lines = f.readlines()

        for i, line in enumerate(lines):
            if line.strip() == f'[{language}]':
                language_section_found = True
            elif language_section_found:
                if line.strip() == '' or line.strip().startswith('['):
                    break
                existing_dependency_name = line.strip().split('==')[0]
                if existing_dependency_name == dependency_name:
                    print(f"Dependency {dependency} already exists under [{language}].")
                    return

        if not language_section_found:
            print(f"Error: Language section [{language}] not found. Please add it first.")
            return

        lines.insert(i, f"{dependency}\n")

        with open(DockerManager.requirements_file, 'w') as f:
            f.writelines(lines)

    def remove_dependency(language, dependency_name):
        lines = []
        language_section_found = False

        with open(DockerManager.requirements_file, 'r') as f:
            lines = f.readlines()

        for i, line in enumerate(lines):
            if line.strip() == f'[{language}]':
                language_section_found = True
            elif language_section_found:
                if line.strip() == '' or line.strip().startswith('['):
                    break
                existing_dependency_name = line.strip().split('==')[0]
                if existing_dependency_name == dependency_name:
                    del lines[i]
                    break
        else:
            raise ValueError(f"Error: Language section [{language}] or dependency {dependency_name} not found.")

        with open(DockerManager.requirements_file, 'w') as f:
            f.writelines(lines)

