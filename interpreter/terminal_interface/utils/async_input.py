import threading
# import multiprocessing
# import ctypes
# import inspect
import time
# import io, sys

# def _async_raise(tid, exctype):
#     '''Raises an exception in the threads with id tid'''
#     if not inspect.isclass(exctype):
#         raise TypeError("Only types can be raised (not instances)")
#     res = ctypes.pythonapi.PyThreadState_SetAsyncExc(ctypes.c_long(tid),
#                                                      ctypes.py_object(exctype))
#     if res == 0:
#         raise ValueError("invalid thread id")
#     elif res != 1:
#         # "if it returns a number greater than one, you're in trouble,
#         # and you should call it again with exc=NULL to revert the effect"
#         ctypes.pythonapi.PyThreadState_SetAsyncExc(ctypes.c_long(tid), None)
#         raise SystemError("PyThreadState_SetAsyncExc failed")

# class ThreadWithExc(threading.Thread):
#     '''A thread class that supports raising an exception in the thread from
#        another thread.
#     '''
#     def _get_my_tid(self):
#         """determines this (self's) thread id

#         CAREFUL: this function is executed in the context of the caller
#         thread, to get the identity of the thread represented by this
#         instance.
#         """
#         if not self.is_alive(): # Note: self.isAlive() on older version of Python
#             raise threading.ThreadError("the thread is not active")

#         # do we have it cached?
#         if hasattr(self, "_thread_id"):
#             return self._thread_id

#         # no, look for it in the _active dict
#         for tid, tobj in threading._active.items():
#             if tobj is self:
#                 self._thread_id = tid
#                 return tid

#         # TODO: in python 2.6, there's a simpler way to do: self.ident

#         raise AssertionError("could not determine the thread's id")

#     def raise_exc(self, exctype):
#         """Raises the given exception type in the context of this thread.

#         If the thread is busy in a system call (time.sleep(),
#         socket.accept(), ...), the exception is simply ignored.

#         If you are sure that your exception should terminate the thread,
#         one way to ensure that it works is:

#             t = ThreadWithExc( ... )
#             ...
#             t.raise_exc( SomeException )
#             while t.isAlive():
#                 time.sleep( 0.1 )
#                 t.raise_exc( SomeException )

#         If the exception is to be caught by the thread, you need a way to
#         check that your thread has caught it.

#         CAREFUL: this function is executed in the context of the
#         caller thread, to raise an exception in the context of the
#         thread represented by this instance.
#         """
#         _async_raise( self._get_my_tid(), exctype )

active_input = {"active":None}
# def classic_input(queue):
# data_wrapper = [[], False] # out, canSave
data_wrapper = {"async_input_data":{}, "canSendInput":False} # out, canSave
# def classic_input(ret, prompt):
def classic_input(prompt):

    # async_input = ret()[0]
    # print("Simulating input:", simulated_input)
    # s = sys
    # print("::::")

    # ret = queue.get()
    # final = [None,None]
    try:
        # stdin = open(0)
        if False:
            final = [None]
            def inputLayer(final):
                active_input["active"] = "blocked"
                # last = input(prompt)
                last = input()

                # print("LAST:",last)
                final[0] = last
                active_input["active"] = None
            threading.Thread(target=inputLayer, args=[final,]).start()
            # print("AWAITING INPUT LAYER")
            while(final[0] is None):
                time.sleep(0.111)
            res = final[0]
        res = input()
        # print("INPUT LAYER RES:",res)
        # print("********************* (Y/N)", end="", flush=True)
        # res = stdin.readline()
        # queue.put(x)
        # print("$$$ canSendInput {canSendInput} GOT CLASSIC INPUT:",res, flush=True)
        async_input_data, canSendInput = data_wrapper["async_input_data"],data_wrapper["canSendInput"]
        # print(f"$$$ canSendInput {canSendInput} ret {async_input_data} GOT CLASSIC INPUT:",res, flush=True)

        if canSendInput:
            async_input_data["origin"] = "classic_input"
            if res != "":
                async_input_data["input"] = res
                # final[0] = res

                # queue.put(res)
            elif "$none$" in res:
                # print("$$$$$$$$ SKIPPING CLASSIC")
                async_input_data["input"] = None
            else:
                async_input_data["input"] = "N"
                # final[0] = "N"
                # queue.put("N")

    except Exception as e:
        # stdin = open(0)

        # print("::: !!! stopped classic input", e)
        async_input_data, canSendInput = data_wrapper["async_input_data"], data_wrapper["canSendInput"]
        if canSendInput:
            async_input_data["input"] = "N"
        # final[0] = "N"
        # queue.put("N")

def input_confirmation(prompt, async_input=None):
    if async_input == None:
        # incase no async_input method was provided
        response = input(prompt)
        return response, None # classic input, code_revision
    # response_revise = [None, None] #response, code_revision

        # finally:
        #     queue.put(final)
    # threading.Thread(target=classic_input, args=[async_input,prompt]).start()
    print(prompt)
    # data_wrapper[0] = async_input#, True
    # data_wrapper[1] = True
    data_wrapper["async_input_data"], data_wrapper["canSendInput"] = async_input, True
    if active_input["active"] is None:
        # classic = ThreadWithExc(target=classic_input, args=[async_input,prompt])
        # classic = ThreadWithExc(target=classic_input, args=[prompt,])
        # classic.start()
        threading.Thread(target=classic_input, args=[prompt,]).start()

    # getInput = lambda : [async_input]
    # queue = multiprocessing.Queue()

    # queue.put(async_input)
    # classic = multiprocessing.Process(target=classic_input, args=(queue,))
    # print(prompt)
    # classic.start()
    if async_input["input"] != None: print("::: skipping, confirmation already exists:",async_input)
    while async_input["input"] is None:# and queue.empty():
        # awaiting for either classic_input or async_input to return a response
        # print(".",end="")
        time.sleep(0.22) #1111
    # Simulate user input
    # if len(async_input) >= 3:
    if "origin" in async_input and async_input["origin"] == "classic_input":
        # Got answer from classic input
        pass
        # print("--- ORIGIN ",async_input.pop("origin"))
        # print("GOT ANSWER FROM INPUT", async_input)
    else:
        print(f"(Got external input) {async_input}")
        # Got answer from External async input
        pass
        # simulated_input = "$none$"
        # print("GOT ANSWER FROM EXTERNAL INPUT",async_input)

        # sys.stdin = open("/dev/stdin")  # Redirect stdin to an open file (Linux)
        # Now the waiting thread should receive the input
        # classic_input.sim(simulated_input)
        # classic.raise_exc(KeyboardInterrupt)
    data_wrapper["canSendInput"] = False
    # sys.stdin.write(simulated_input + "\n")
    # sys.stdin.flush()
    # process.terminate()
    # process.join()
    # classic.raise_exc(KeyboardInterrupt)
    # if not queue.empty():
    #     answer = queue.get()
    #     print("$$$$$$$$$ GOT CLASSIC INPUT", answer)
    #     async_input[0] = answer
    # else:
    #     print("XXXXXX TERMINATING CLASSIC INPUT")
        # classic.terminate()
    # print("::: Done Async_Input", async_input)
    return async_input["input"], async_input["code_revision"]
