=======================================================================
                              NOTE TO DEVELOPERS
=======================================================================

Please avoid manually editing the following files:
- Dockerfile
- requirements.txt
- hash.json

These files are key components for Open-Interpreter's containerized execution features. Manually editing them can disrupt the program's ability to:

1. Know when to rebuild the Docker image.
2. Perform other related functionalities efficiently.

If you need to make adjustments, kindly use the 'DockerManager' class. It offers convenient methods like:
- add_dependency
- remove_dependency
- add_language

Your cooperation helps maintain a smooth and reliable development workflow.

=======================================================================
