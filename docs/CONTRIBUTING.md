# ●

**Open Interpreter is large, open-source initiative to build a standard interface between language models and computers.**

There are many ways to contribute, from helping others on [Github](https://github.com/KillianLucas/open-interpreter/issues) or [Discord](https://discord.gg/6p3fD6rBVm), writing documentation, or improving code.

We depend on contributors like you. Let's build this.

## What should I work on?

First, please familiarize yourself with our [project scope](https://github.com/KillianLucas/open-interpreter/blob/main/docs/ROADMAP.md#whats-in-our-scope). Then, pick up a task from our [roadmap](https://github.com/KillianLucas/open-interpreter/blob/main/docs/ROADMAP.md) or work on solving an [issue](https://github.com/KillianLucas/open-interpreter/issues).

If you encounter a bug or have a feature in mind, don't hesitate to [open a new issue](https://github.com/KillianLucas/open-interpreter/issues/new/choose).

## Philosophy

This is a minimalist, **tighly scoped** project that places a premium on simplicity. We're skeptical of new extensions, integrations, and extra features. We would rather not extend the system if it adds nonessential complexity.

# Contribution Guidelines

1. Before taking on significant code changes, please discuss your ideas on [Discord](https://discord.gg/6p3fD6rBVm) to ensure they align with our vision. We want to keep the codebase simple and unintimidating for new users.
2. Fork the repository and create a new branch for your work.
3. Follow the [Running Your Local Fork](https://github.com/KillianLucas/open-interpreter/blob/main/docs/CONTRIBUTING.md#running-your-local-fork) guide below.
4. Make changes with clear code comments explaining your approach. Try to follow existing conventions in the code.
5. Follow the [Code Formatting and Linting](https://github.com/KillianLucas/open-interpreter/blob/main/docs/CONTRIBUTING.md#code-formatting-and-linting) guide below.
6. Open a PR into `main` linking any related issues. Provide detailed context on your changes.

We will review PRs when possible and work with you to integrate your contribution. Please be patient as reviews take time. Once approved, your code will be merged.

## Running Your Local Fork

Once you've forked the code and created a new branch for your work, you can run the fork in CLI mode by following these steps:

1. CD into the project folder `/open-interpreter`
2. Install dependencies `poetry install`
3. Run the program `poetry run interpreter`

After modifying the source code, you will need to do `poetry run interpreter` again.

**Note**: This project uses [`black`](https://black.readthedocs.io/en/stable/index.html) and [`isort`](https://pypi.org/project/isort/) via a [`pre-commit`](https://pre-commit.com/) hook to ensure consistent code style. If you need to bypass it for some reason, you can `git commit` with the `--no-verify` flag.

### Installing New Dependencies

If you wish to install new dependencies into the project, please use `poetry add package-name`.

### Installing Developer Dependencies

If you need to install dependencies specific to development, like testing tools, formatting tools, etc. please use `poetry add package-name --group dev`.

### Known Issues

For some, `poetry install` might hang on some dependencies. As a first step, try to run the following command in your terminal:

`export PYTHON_KEYRING_BACKEND=keyring.backends.fail.Keyring`

Then run `poetry install` again. If this doesn't work, please join our [Discord community](https://discord.gg/6p3fD6rBVm) for help.

## Code Formatting and Linting

Our project uses `black` for code formatting and `isort` for import sorting. To ensure consistency across contributions, please adhere to the following guidelines:

1. **Install Pre-commit Hooks**:

   If you want to automatically format your code every time you make a commit, install the pre-commit hooks.

   ```bash
   pip install pre-commit
   pre-commit install
   ```

   After installing, the hooks will automatically check and format your code every time you commit.

2. **Manual Formatting**:

   If you choose not to use the pre-commit hooks, you can manually format your code using:

   ```bash
   black .
   isort .
   ```

# Licensing

Contributions to Open Interpreter would be under the MIT license before version 0.2.0, or under AGPL for subsequent contributions.

# Questions?

Join our [Discord community](https://discord.gg/6p3fD6rBVm) and post in the #General channel to connect with contributors. We're happy to guide you through your first open source contribution to this project!

**Thank you for your dedication and understanding as we continue refining our processes. As we explore this extraordinary new technology, we sincerely appreciate your involvement.**
