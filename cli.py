import argparse
import interpreter

def main():
    parser = argparse.ArgumentParser(description='Run the OpenAI Interpreter.')
    parser.add_argument('--safe_mode', action='store_true', help='Enable safe mode')
    args = parser.parse_args()

    # Set safe_mode on the imported interpreter instance
    if args.safe_mode:
      print("\nYou are in safe mode. Generated code will require confirmation before running.\n")
      interpreter.safe_mode = True
    
    # Now run the chat method
    interpreter.chat()

if __name__ == "__main__":
    main()