import asyncio
import fcntl
import os
import sys
import termios


async def get_input(
    placeholder_text: str = "Testing", placeholder_color: str = "gray"
) -> str:
    # Save terminal settings and set raw mode
    old_settings = termios.tcgetattr(sys.stdin.fileno())
    tty_settings = termios.tcgetattr(sys.stdin.fileno())
    tty_settings[3] = tty_settings[3] & ~(termios.ECHO | termios.ICANON)
    termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, tty_settings)

    # Set up non-blocking stdin
    fd = sys.stdin.fileno()
    flags = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

    COLORS = {
        "gray": "\033[90m",
        "red": "\033[91m",
        "green": "\033[92m",
        "yellow": "\033[93m",
        "blue": "\033[94m",
        "magenta": "\033[95m",
        "cyan": "\033[96m",
        "white": "\033[97m",
    }
    RESET = "\033[0m"

    current_input = []
    show_placeholder = True

    def redraw():
        sys.stdout.write("\r\033[K")  # Clear line
        sys.stdout.write("\r> ")
        if current_input:
            sys.stdout.write("".join(current_input))
        elif show_placeholder:
            color_code = COLORS.get(placeholder_color.lower(), COLORS["gray"])
            sys.stdout.write(f"{color_code}{placeholder_text}{RESET}")
            sys.stdout.write("\r> ")
        sys.stdout.flush()

    try:
        redraw()
        while True:
            try:
                char = os.read(fd, 1).decode()

                if char == "\n":
                    if current_input:
                        result = "".join(current_input)
                        return result
                    else:
                        redraw()
                elif char == "\x7f":  # Backspace
                    if current_input:
                        current_input.pop()
                        if not current_input:
                            show_placeholder = True
                elif char == "\x03":  # Ctrl+C
                    raise KeyboardInterrupt
                elif char and char.isprintable():
                    current_input.append(char)
                    show_placeholder = False
                redraw()
            except BlockingIOError:
                pass

    finally:
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old_settings)
        fcntl.fcntl(fd, fcntl.F_SETFL, flags)
        print()
