from interpreter.exec import exec_and_capture_output

code = """plan = [
  'Step 1',
  'Step 2',
  'Step 3'
]"""

exec_and_capture_output(code, 1000)