from .code_interpreter import language_map

import os
import tempfile
import subprocess

def get_extension(language):
    if language_map[language]["extension"]:
      return language_map[language]["extension"]
    else:
      return language

def code_scan(code, language, self):
  """
  Scan code with semgrep
  """

  # Create a temporary file
  with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=f".{get_extension(language)}") as f:  
    f.write(code)
    temp_file_name = f.name
    f.close()

  temp_path = os.path.dirname(temp_file_name)
  file_name = os.path.basename(temp_file_name)

  if (self.debug_mode):
    print(f"Created temporary file {temp_file_name}")
    print(f"Scanning {language} code in {file_name}")
    print("---")

  # Run semgrep
  try:
    # HACK: we need to give the subprocess shell access so that the semgrep from our pyproject.toml is available
    # the global namespace might have semgrep from guarddog installed, but guarddog is currenlty
    # pinned to an old semgrep version that has issues with reading the semgrep registry
    # while scanning a single file like the temporary one we generate
    # if guarddog solves [#249](https://github.com/DataDog/guarddog/issues/249) we can change this approach a bit
    subprocess.run(f"cd {temp_path} && semgrep scan --config auto --dryrun {file_name}", shell=True)

  except Exception as e:
    print(f"Could not scan {language} code.")
    print(e)
    print("")  # <- Aesthetic choice

  # clean up temporary file
  os.remove(temp_file_name)