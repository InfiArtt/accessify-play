# How to Contribute to Accessify Play

💖 We're thrilled that you're interested in contributing to Accessify Play! Your help is valuable.

To make the process smooth for everyone, please follow these guidelines.

## 📜 Table of Contents

- [Code of Conduct](#-code-of-conduct)
- [Contribution Workflow](#-contribution-workflow)
  - [1. Set Up Your Repository](#1-set-up-your-repository)
  - [2. Create a New Branch](#2-create-a-new-branch)
- [Submitting a Pull Request (PR)](#-submitting-a-pull-request-pr)
  - [✅ PR Requirements](#-pr-requirements)
  - [🏷️ Adding Labels to Your PR](#️-adding-labels-to-your-pr)
- [Need Help?](#-need-help)

## 🤝 Code of Conduct

First, please review our [Code of Conduct](CODE_OF_CONDUCT.md). We enforce this code to ensure our community is welcoming and inclusive for everyone.

## 🚀 Contribution Workflow

We use the "GitHub Flow" model, which means all changes happen through Pull Requests.

### 1. Set Up Your Repository

Before you start, you'll need a copy of the repository on your own account.

1.  **Fork** this repository to your own GitHub account.
2.  **Clone** your fork to your local machine.
    ```bash
    git clone https://github.com/YOUR_USERNAME/accessify-play.git
    cd accessify-play
    ```

### 2. Create a New Branch

All changes must be made on a new branch created from `main`.

**Branch Naming Convention:**
Please use our standard naming convention to keep things organized:
-   **Features:** `feature/add-new-thing`
-   **Bug Fixes:** `bugfix/fix-that-crash`
-   **Documentation:** `docs/update-readme`
-   **Maintenance:** `chore/fix-linting` or `maintenance/fix-linting`

**Example Commands:**
```bash
# 1. Always start from an up-to-date 'main' branch
git checkout main
git pull origin main

# 2. Create your new branch
git checkout -b feature/your-new-feature
```

## 📦 Submitting a Pull Request (PR)

Once your changes are ready, it's time to create a PR.

1.  Make your changes and write clear, concise commit messages.
2.  **Push** your branch to your fork on GitHub:
    ```bash
    git push -u origin feature/your-new-feature
    ```
3.  Go to the main `InfiArtt/accessify-play` repository and you will see a prompt to **"Open a Pull Request"**.
4.  Fill out the PR template, explaining *what* you changed and *why*. If your PR addresses an existing issue, please link it (e.g., `Closes #123`).

### ✅ PR Requirements

Our repository is protected by automated checks (GitHub Actions). Before your PR can be merged, it **must** meet two conditions:

1.  **🤖 Linting Check Must Pass**
    Our linter will automatically check your code for style errors (using `flake8`). You can see the result at the bottom of your PR page. If it fails, please fix the reported issues.

2.  **🌿 Branch Must Be Up-to-Date**
    Your branch must be in sync with the `main` branch. If `main` has been updated while you were working, you'll need to update your branch before we can merge it.

    **How to update your branch:**
    ```bash
    # Switch to your feature branch
    git checkout feature/your-new-feature

    # Pull the latest changes from the main repository's main branch
    git pull origin main

    # If there are any merge conflicts, resolve them, then push your changes
    git push
    ```

### 🏷️ Adding Labels to Your PR

Please add an appropriate label to your Pull Request (e.g., `feature`, `bug`, `documentation`).

> **This is very important!** Our automated `release-drafter` bot uses these labels to build the changelog for the next release.

## 🤔 Need Help?

If you have any questions or get stuck, feel free to [create a new issue](https://github.com/InfiArtt/accessify-play/issues/new/choose).

---

Thank you for contributing! 🎉