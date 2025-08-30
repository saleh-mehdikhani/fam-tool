import uuid
import yaml
import os
from pathlib import Path
import git

# --- Repository Discovery ---

def find_repos():
    """Finds the data and graph repos by searching up from the current directory."""
    try:
        # Find the top-level of the current git repository.
        search_path = Path(git.Repo(os.getcwd(), search_parent_directories=True).working_dir)
        
        # Simply try to instantiate the repos. Let GitPython handle validation.
        data_repo = git.Repo(search_path)
        graph_repo_path = search_path / 'family_graph'
        graph_repo = git.Repo(graph_repo_path)
        return data_repo, graph_repo
    except (git.InvalidGitRepositoryError, git.NoSuchPathError):
        # This will catch if the current dir is not a git repo, or the submodule is missing.
        return None, None

import shutil

def initialize_project(root_path_str, force=False):
    """Creates a new family tree project at the specified path."""
    # Resolve path first to enable reliable comparison
    root_path = Path(root_path_str).resolve()

    # Safeguard against deleting CWD. This is the key check.
    if force and root_path.exists() and root_path == Path.cwd().resolve():
        print(f"Error: Cannot overwrite the current working directory.")
        return False

    graph_source_path = root_path.with_name(root_path.name + "_graph_source")

    if force:
        if root_path.exists():
            shutil.rmtree(root_path)
        if graph_source_path.exists():
            shutil.rmtree(graph_source_path)
    elif root_path.exists() or graph_source_path.exists():
        print(f"Error: Target directory '{root_path}' or '{graph_source_path}' already exists. Use --force to overwrite.")
        return False

    try:
        # 1. Create and initialize the source graph repo
        graph_source_repo = git.Repo.init(graph_source_path)
        graph_source_repo.git.commit('--allow-empty', '-m', "Graph Root")
        graph_source_repo.create_tag("GRAPH_ROOT", message="Graph entry point")
        print(f"Initialized graph source at: {graph_source_path}")

        # 2. Initialize the main data repo
        data_repo = git.Repo.init(root_path)
        print(f"Initialized data repo at: {root_path}")

        # 3. Add the graph repo as a submodule
        submodule = data_repo.create_submodule(
            name='family_graph',
            path='family_graph',
            url=str(graph_source_path)
        )
        print("Added family_graph submodule.")

        # 4. Create people directory and initial commit
        (root_path / 'people').mkdir()
        # Add a .gitkeep to the empty directory so git tracks it
        (root_path / 'people' / '.gitkeep').touch()

        data_repo.index.add([submodule.path, '.gitmodules', 'people/.gitkeep'])
        data_repo.index.commit("Initial commit: Add family_graph submodule and people directory")
        print("Created initial commit.")

    finally:
        # 5. Clean up the temporary source repo
        if graph_source_path.exists():
            shutil.rmtree(graph_source_path)
            print(f"Cleaned up graph source directory.")
    
    print(f"Successfully created new family tree project at {root_path}")
    return True

# --- Core Logic ---

def add_person(first_name, last_name, middle_name, birth_date, gender, nickname):
    """
    Orchestrates creating a new person across both the data and graph repositories.
    """
    data_repo, graph_repo = find_repos()
    if not data_repo or not graph_repo:
        print("Error: Must be run from within a valid data repository with a 'family_graph' submodule.")
        return False

    # 1. Generate ID and filename
    person_id = str(uuid.uuid4())
    short_id = person_id[:8]
    filename = f"{short_id}_{first_name.lower()}_{last_name.lower()}.yml"
    filepath = Path(data_repo.working_dir) / 'people' / filename
    graph_repo_path = Path(graph_repo.working_dir)

    # 2. Create graph commit containing a reference to the person's data file
    try:
        graph_root_commit = graph_repo.tags['GRAPH_ROOT'].commit
        # Operate in a detached HEAD state starting from the root commit
        graph_repo.head.reference = graph_root_commit
        graph_repo.head.reset(index=True, working_tree=True)

        # Create the reference file
        ref_filepath = graph_repo_path / 'person.ref'
        with open(ref_filepath, 'w') as f:
            f.write(short_id)

        # Add and commit the reference file
        commit_message = f"Person: {first_name} {last_name} ({short_id})"
        graph_repo.index.add([str(ref_filepath)])
        graph_repo.index.commit(commit_message)
        
        new_graph_commit = graph_repo.head.commit
        print(f"Created graph commit: {new_graph_commit.hexsha}")

        # 3. Tag the new commit with the stable short_id for easy lookup
        graph_repo.create_tag(short_id, ref=new_graph_commit, message=f"Reference to person {short_id}")
        print(f"Tagged commit with: {short_id}")

    except (IndexError, ValueError) as e:
        print(f"Error during graph operation: {e}")
        print("Is this a valid project? Graph repository might be missing the GRAPH_ROOT tag.")
        return False
    finally:
        # Clean up the reference file from the working directory
        if 'ref_filepath' in locals() and ref_filepath.exists():
            ref_filepath.unlink()


    # 4. Assemble YAML data
    full_name = f"{first_name}{f' {middle_name}' if middle_name else ''} {last_name}"
    person_data = {
        'id': person_id,
        'name': full_name,
        'gender': gender,
        'birth_date': birth_date,
        'nickname': nickname,
    }
    # Clean up optional fields that are None
    person_data = {k: v for k, v in person_data.items() if v is not None}

    # 5. Write YAML file
    if not filepath.parent.exists():
        filepath.parent.mkdir()
    with open(filepath, 'w', encoding='utf-8') as f:
        yaml.dump(person_data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    print(f"Created person file: {filepath}")

    # 6. Commit to data repo
    data_repo.index.add([str(filepath)])
    data_repo.index.commit(f"feat: Add person '{full_name}' ({short_id})")
    print("Committed person file to data repository.")

    return True