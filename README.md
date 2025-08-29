# Fam-Tool

A command-line tool to manage family tree data using a dual-repository Git model.

This tool separates the person data (in YAML files) from the relationship data (a Git commit graph), allowing for flexible data management and a robust, version-controlled family structure.

## Installation

To install the tool, clone this repository and use `pip` to install it in editable mode within a virtual environment.

```bash
# Clone the repository
git clone <this_repository_url>
cd fam-tool

# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install the tool in editable mode
pip install -e .
```

## Getting Started: Initializing Your Data Repository

The `fam` tool operates on a specific repository structure. To create a new family tree project, you must first initialize your data and graph repositories.

1.  **Create a directory for your graph source.** This will be a bare repository that only stores the relationship graph.
    ```bash
    mkdir my_family_graph
    cd my_family_graph
    git init --bare
    cd ..
    ```

2.  **Create a directory for your main data repository.**
    ```bash
    mkdir my_family_data
    cd my_family_data
    git init
    ```

3.  **Add the graph repository as a submodule named `family_graph`.**
    ```bash
    # Use a relative path to the graph source repo you created
    git submodule add ../my_family_graph family_graph
    ```

4.  **Create the `people` directory and commit the structure.**
    ```bash
    mkdir people
    git add .gitmodules family_graph people
    git commit -m "Initial commit: Add family_graph submodule and people directory"
    ```

You are now ready to use the `fam` tool inside the `my_family_data` directory.

## Usage

### Add a new person

To add a new person, `cd` into your data repository and use the `fam add` command.

```bash
# Navigate to your data repository
cd /path/to/my_family_data

# Add a person using required and optional flags
fam add -f "John" -l "Doe" -b "1950-10-25" -g "Male"
```
