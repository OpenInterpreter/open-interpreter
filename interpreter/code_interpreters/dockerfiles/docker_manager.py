class DockerManager:
    def __init__(self, requirements_file='requirements.txt', docker_file='Dockerfile'):
        self.requirements_file = requirements_file
        self.docker_file = docker_file

    def add_dependency(self, language, dependency):
        lines = []
        language_section_found = False
        dependency_name = dependency.split('==')[0]

        with open(self.requirements_file, 'r') as f:
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

        with open(self.requirements_file, 'w') as f:
            f.writelines(lines)

    def remove_dependency(self, language, dependency_name):
        lines = []
        language_section_found = False

        with open(self.requirements_file, 'r') as f:
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
            raise ValueError(f"Error: Language section [{language}] or dependency {dependency_name} not found. please add the language using the '.add_language' method")

        with open(self.requirements_file, 'w') as f:
            f.writelines(lines)


    def add_language(self, language, install_command):
        with open(self.docker_file, 'a') as f:
            f.write(f'\n# Install {language}\nRUN {install_command}\n')

        with open(self.requirements_file, 'a') as f:
            f.write(f"\n[{language}]\n")
