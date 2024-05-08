from interpreter import interpreter, computer
import time
#     ____                      ____      __                            __
#    / __ \____  ___  ____     /  _/___  / /____  _________  ________  / /____  _____
#   / / / / __ \/ _ \/ __ \    / // __ \/ __/ _ \/ ___/ __ \/ ___/ _ \/ __/ _ \/ ___/
#  / /_/ / /_/ /  __/ / / /  _/ // / / / /_/  __/ /  / /_/ / /  /  __/ /_/  __/ /
#  \____/ .___/\___/_/ /_/  /___/_/ /_/\__/\___/_/  / .___/_/   \___/\__/\___/_/
#      /_/                                         /_/
#     ____ _____ ____  _____    _    __  __        ___  _   _ _____
#    / ___|_   _|  _ \| ____|  / \  |  \/  |      / _ \| | | |_   _|
#    \___ \ | | | |_) |  _|   / _ \ | |\/| |_____| | | | | | | | |
#     ___) || | |  _ <| |___ / ___ \| |  | |_____| |_| | |_| | | |
#    |____/ |_| |_| \_\_____/_/   \_\_|  |_|      \___/ \___/  |_|

'''
# THIS EXAMPLE SHOWS HOW TO:
# 1. Stream-Out All of OpenInterpreter's outputs to another process (like another UI)
# 2. Async-Input To Trigger (Y/N/Other) Remotely
# 3. Make Changes to the Code Before Execution
#       - If you answer Other than "y" or "n" your answer will be counted as a User Message
#       - If you manually change the code, the new revised code will be run
'''


interpreter.llm.model = 'mixtral-8x7b-32768'
interpreter.llm.model = 'llama3-70b-8192'
interpreter.llm.api_key = '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'
interpreter.llm.api_base = "https://api.groq.com/openai/v1"
interpreter.llm.context_window = 32000


#______________________________________
# Data placeholders used to do async streaming out
from collections import deque

block_queue = deque()
full_queue = deque()
blocks_unfinished = deque()
pauseSend = [False]

# Useful for whatsapp and other messaging apps (set to True)
update_by_blocks = False
ignore_formats = ['active_line']
independent_blocks = ['confirmation', 'output'] # These will be sent as whole
#______________________________________


#______________________________________
# Prep for my implemintation
# from xo_benedict.freshClient import FreshClient #
# client = FreshClient(_inc=3)
#______________________________________

## ↓ EXAMPLE FOR THE FINAL METHOD TO STREAM OI'S OUTPUT TO ANOTHER PROGRAM
def _update(item, debug = False):
    def _format(lines):
        hSize = 4
        return lines.replace("**Plan:**",f"<h{hSize}>Plan:</h{hSize}>").replace("**Code:**",f"<h{hSize}>Code:</h{hSize}>")

    if not pauseSend[0]:
        if debug: print(f"::: STREAMING OUT:", item)
        stream_out = _format(str(item))

        ## ↓↓↓ SEND OUT OI'S OUTPUT

        #client.addText(stream_out) # Just an example, my personal implemintation
        if debug: print(" --CHANGE THIS-- STREAMING OUTPUT: ",stream_out)

        ## ↑↑↑ CHANGE THIS to something that triggers YOUR APPLICATION
## ↑ You can change this function to one that suites your application



# ↓ STREAN OUT HOOK - This function is passed into chat() and is called on every output from
def stream_out_hook(partial, debug = False, *a, **kw):
    # Gets Chunks from OpenInterpreter and sends them to an async update queue
    ''' THIS FUNCTION PROCESSES ALL THE OUTPUTS FROM OPEN INTERPRETER
        Prepares all the chunks to be sent out
        update_by_blocks=True will batch similar messages, False will stream (unless in independent_blocks )
        '''
    if debug: print("STREAMING OUT! ",partial)

    ## ↓ Send all the different openinterpreter chunk types to the queue

    if "start" in partial and partial["start"]:
        if update_by_blocks:
            blocks_unfinished.append({"content":"",**partial})#,"content_parts":[],**partial})
        else:
            full_queue.append(partial)
    if partial['type'] in independent_blocks or 'format' in partial and partial['format'] in independent_blocks:
        if update_by_blocks:
            block_queue.append({"independent":True,**partial})
        else:
            full_queue.append({"independent":True,**partial})
        if debug: print("INDEPENDENT BLOCK", partial)
    elif 'content' in partial and ('format' not in partial or partial['format'] not in ignore_formats):
        if update_by_blocks:
            blocks_unfinished[0]['content'] += partial['content']
        else:
            full_queue.append(partial['content'])
        # blocks[-1]['content_parts'].append(partial['content'])
    if 'end' in partial:
        if debug: print("EEEnd",blocks_unfinished, partial)
        fin = {**partial}
        if update_by_blocks:
            blocks_unfinished[0]['end'] = partial['end']
            fin = blocks_unfinished.popleft()
            block_queue.append(fin)
        else:
            full_queue.append(fin)

        if debug: print("FINISHED BLOCK", fin)




#______________________________________
# Continuesly Recieve OpenInterpreter Chunks and Prepare them to be Sent Out
def update_queue(debug = False, *a, **kw):
    target = full_queue
    if update_by_blocks:
        target = block_queue
    c = 0
    while(True):
        while(len(target) > 0):
            leftmost_item = target.popleft()
            if debug: print(f"{c} ::: UPDATING QUEUE:", leftmost_item)

            #
            if "start" in leftmost_item:
                if "type" in leftmost_item and leftmost_item["type"] == "code":
                    _update("__________________________________________\n")
                    pauseSend[0] = True
            elif "end" in leftmost_item:
                if "type" in leftmost_item and leftmost_item["type"] == "code":
                    pauseSend[0] = False
            elif isinstance(leftmost_item, str): _update(leftmost_item)
            else:
                content = "" if "content" not in leftmost_item else leftmost_item["content"]
                if "content" in leftmost_item and not isinstance(leftmost_item["content"],str):
                    content = leftmost_item['content']['content'] if not isinstance(leftmost_item['content'],str) else leftmost_item['content']
                    if len(content) >0 and content[0] == "\n": content = content[1:]
                if "type" in leftmost_item and leftmost_item["type"] in ["confirmation"]:
                    if len(content)>0 and content[0] != "<" and content[-1] != ">": content = "<code>"+content+ "</code>"
                    _update(content+"<h4> Would you like to run this code? (Y/N)</h4>"
                        +"<span style=\"color: grey;\"> You can also edit it before accepting</span><br>__________________________________________<br></x>")
                elif "type" in leftmost_item and leftmost_item["type"] == 'console':
                    if len(content)>0 and content != "\n":
                        if debug: print(f"::: content :::{content}:::")
                        if content[0] != "<" and content[-1] != ">": content = "<code>"+content+ "</code>"
                        _update(f"<h3>OUTPUT:</h3>{content}<br>")
                else:
                    _update(leftmost_item)
        time.sleep(0.1)

from threading import Thread
update_queue_thread = Thread(target=update_queue)
update_queue_thread.start()
# ↑ Start Async Thread to Process Chunks Before streaming out
#______________________________________

# Run tests, one after the other
def test_async_input(tests):
    for i, answer, code_revision in tests:
        # Wait {i} seconds
        while(i>0):
            if i%5==0: print(f"::: Testing Input:\"{answer}\"  with code:{code_revision} in: {i} seconds")
            time.sleep(1)
            i-=1

        ## ↓ TRIGGER EXTERNAL INPUT
        async_input_data["input"] = answer
        async_input_data["code_revision"] = code_revision
        ## ↑ OPTIONAL CODE CHANGES

        pass #print(" TEST DONE ", async_input_data)


## ↓ THIS IS OBJECT BEING WATCHED FOR TRIGGERING INPUT
async_input_data = {"input":None, "code_revision":None}
## ↑ CHANGING async_input_data["input"] WILL TRIGGER OI'S INPUT
if __name__ == "__main__":

    ## Test automatic external trigger for (Y/N/Other) + code revisions
    tests = [
        # seconds_to_wait, input_response, new_code_to_run
        [20, "Y", "print('SUCCESS!!!!!!!!')"],
        # [20,"N",None],
        # [20,"print hello {username from host} instead", None],
        ]
    Thread(target=test_async_input, args=[tests,]).start()

    # Start OpenInterpreter
    '''# Pass in stream_out_hook function, and async_input_data '''
    interpreter.chat(stream_out = stream_out_hook, async_input = async_input_data)
