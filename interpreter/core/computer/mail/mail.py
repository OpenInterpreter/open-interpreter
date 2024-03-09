import re
import subprocess
import platform
from ..utils.run_applescript import run_applescript, run_applescript_capture


class Mail:
    def __init__(self, computer):
        self.computer = computer
        # In the future, we should allow someone to specify their own mail app
        self.mail_app = "Mail"

    def get(self, number=5, unread: bool = True):
        """
        Retrieves the last {number} emails from the inbox, optionally filtering for only unread emails.
        """
        if platform.system() != 'Darwin':
            return "This method is only supported on MacOS"
        
        # This is set up to retry if the number of emails is less than the number requested, but only a max of three times
        retries = 0  # Initialize the retry counter
        while retries < 3:
            read_status_filter = "whose read status is false" if unread else ""
            script = f'''
            tell application "{self.mail_app}"
                set latest_messages to messages of inbox {read_status_filter}
                set email_data to {{}}
                repeat with i from 1 to {number}
                    set this_message to item i of latest_messages
                    set end of email_data to {{subject:subject of this_message, sender:sender of this_message, content:content of this_message}}
                end repeat
                return email_data
            end tell
            '''
            stdout, stderr = run_applescript_capture(script)
            
            # if the error is due to not having enough emails, retry with the available emails. 
            if "Can’t get item" in stderr:
                match = re.search(r"Can’t get item (\d+) of", stderr)
                if match:
                    available_emails = int(match.group(1)) - 1
                    if available_emails > 0:
                        number = available_emails
                        retries += 1
                        continue
                break
            elif stdout:
                print(stdout)
                return stdout
            break
        return None  # Return None if the operation fails after max_retries

    def send(self, to, subject, body, attachments=None):
        """
        Sends an email with the given parameters using the default mail app.
        """
        if platform.system() != 'Darwin':
            return "This method is only supported on MacOS"
        
        attachment_clause = ''
        if attachments:
            # Generate AppleScript to attach each file
            attachment_clause = '\n'.join(f'make new attachment with properties {{file name:"{path}"}} at after the last paragraph of the content of new_message' for path in attachments)
            
        # In the future, we might consider allowing the llm to specify an email to send from
        script = f'''
        tell application "{self.mail_app}"
            set new_message to make new outgoing message with properties {{subject:"{subject}", content:"{body}"}} at end of outgoing messages
            tell new_message
                set visible to true
                make new to recipient at end of to recipients with properties {{address:"{to}"}}
                {attachment_clause}
            end tell
            send new_message
        end tell
        '''
        try:
            run_applescript(script)
            return f'''Email sent to {to}'''
        except subprocess.CalledProcessError:
            return "Failed to send email"

    def unread_count(self):
            """
            Retrieves the count of unread emails in the inbox.
            """
            if platform.system() != 'Darwin':
                return "This method is only supported on MacOS"
            
            script = f'''
            tell application "{self.mail_app}"
                return count of (messages of inbox whose read status is false)
            end tell
            '''
            try:
                return int(run_applescript(script))
            except subprocess.CalledProcessError as e:
                print(e)
                return 0

