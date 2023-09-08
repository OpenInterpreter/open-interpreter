import subprocess
import sys
import json

def check_avx2_support():
    result = subprocess.run(['lscpu', '--json'], stdout=subprocess.PIPE)
    lscpu_output = result.stdout.decode('utf-8')
    
    lscpu_info = json.loads(lscpu_output)
    
    for info in lscpu_info["lscpu"]:
        if info["field"] == "Flags:":
            flags = info["data"].split()
            if "avx2" in flags:
                print("This system supports AVX2.")
                return True
            else:
                print("This system does not support AVX2.")
                return False

if check_avx2_support():
    sys.exit(0)
else:
    sys.exit(1)