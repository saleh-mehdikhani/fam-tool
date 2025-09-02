# Fam-Tool

A command-line tool for managing family tree data using a dual-repository Git model.

This tool separates person data (YAML files) from relationship data (a Git commit graph), allowing for flexible data management and a robust, version-controlled family structure.

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

## Getting Started

To create a new family tree project, use the `fam init` command. This will create a new directory where your family tree data will be stored.

```bash
# This path is where your family tree data will be stored.
fam init /path/to/my-family-tree
```

This will create a new directory named `my-family-tree` at the specified path, with the following structure:

```
/path/to/
└── my-family-tree/
    ├── .git/
    ├── .gitmodules
    ├── family_graph/
    └── people/
```

You are now ready to use the `fam` tool inside the `my-family-tree` directory.

## Usage

### Add a new person

```bash
fam add -fn "John" -l "Doe" -b "1950-10-25" -g "Male"
```

### Marry two people

```bash
fam marry --male <male_person_id> --female <female_person_id>
```

### Add a child to a couple

```bash
fam child <child_id> -f <father_id> -m <mother_id>
```
