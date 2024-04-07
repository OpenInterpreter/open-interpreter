from jupyter_client import KernelManager

km1 = KernelManager()
km1.start_kernel()

kc1 = km1.client()
kc1.start_channels()
kc1.wait_for_ready()

kc1.stop_channels()
# If the following line is commented out, the message
# "[IPKernelApp] WARNING | Parent appears to have exited, shutting down."
# will appear after this script finishes running.
km1.shutdown_kernel()

del kc1
del km1