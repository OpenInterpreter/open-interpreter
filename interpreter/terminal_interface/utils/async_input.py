import threading
import time

active_input = {"active":None}
data_wrapper = {"async_input_data":{}, "canSendInput":False} # out, canSave

# This uses the classic input methon (called from a thread)
def classic_input(input_msg):
    try:
        ## ↓ GET CLASSIC INPUT()
        user_input = input()

        # Send classic input back to input_confirmation
        async_input_data, canSendInput = data_wrapper["async_input_data"],data_wrapper["canSendInput"]
        if canSendInput:
            # set origin of input to classic
            async_input_data["origin"] = "classic_input"
            if user_input == "":
                async_input_data["input"] = "N"
            else:
                # (Trigger) Send user input (Y/N/Other Requests)
                async_input_data["input"] = user_input
    except:
        async_input_data, canSendInput = data_wrapper["async_input_data"], data_wrapper["canSendInput"]
        if canSendInput:
            async_input_data["input"] = "N"


## ↓ JOINT INPUT METHOD - FROM BOTH CLASSIC INTPUT() AND EXTERNAL INPUT
def input_confirmation(input_msg, async_input=None): # async_input:dict {"input":None,""}
    ''' Changing `async_input` dict from an external process
        can trigger confirmation, just like using input()
        and also allows for manual code changes before execution
        async_input:dict {"input":None,"code_revison"}'''
    if async_input == None:
        # in case no async_input dict was provided, run normally
        response = input(input_msg)
        return response, None # input, code_revision

    # Print the question here (Y/N)
    print(input_msg)

    # Wrap the input data, Enable classic input from
    data_wrapper["async_input_data"], data_wrapper["canSendInput"] = async_input, True
    # Start the classic input thread (if one isnt already active)
    if active_input["active"] is None:
        # If no other classic input thread is open, create one
        threading.Thread(target=classic_input, args=[input_msg,]).start()
    if async_input["input"] is not None: pass # Skipping, confirmation already exists


    ## ↓ WAIT FOR EITHER EXTERNAL INPUT OR CLASSIC INPUT() TO FINISH
    ##          async_input["input"] can change from external process or from classic input()

    while async_input["input"] is None:
        time.sleep(0.1)

    ## ↑ WAIT UNTIL CLASSIC INPUT() FINISHES OR EXTERNAL INPUT FINISHES


    if "origin" in async_input and async_input["origin"] == "classic_input":
        pass # Got answer from classic input
    else:
        # Got answer from External async input
        print(f"Got external input: {async_input}")

    # Disable input until next confirmation
    data_wrapper["canSendInput"] = False

    # return input from either classic or external + code revisions
    return async_input["input"], async_input["code_revision"]
