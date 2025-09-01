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
        graph_repo.head.reference = graph_root_commit
        graph_repo.head.reset(index=True, working_tree=True)

        # Create an empty commit with the person's info in the message
        commit_message = f"Person: {first_name} {last_name} ({short_id})"
        graph_repo.git.commit('--allow-empty', '-m', commit_message)
        new_graph_commit = graph_repo.head.commit

        print(f"Created graph commit: {new_graph_commit.hexsha}")

        # 3. Tag the new commit with the stable short_id for easy lookup
        graph_repo.create_tag(short_id, ref=new_graph_commit, message=f"Reference to person {short_id}")
        print(f"Tagged commit with: {short_id}")

    except (IndexError, ValueError) as e:
        print(f"Error during graph operation: {e}")
        print("Is this a valid project? Graph repository might be missing the GRAPH_ROOT tag.")
        return False


    # 4. Assemble YAML data
    full_name = f"{first_name}{f' {middle_name}' if middle_name else ''} {last_name}"
    person_data = {
        'id': person_id,
        'name': full_name,
        'first_name': first_name,
        'last_name': last_name,
        'middle_name': middle_name or '',
        'gender': gender or '',
        'nickname': nickname or '',
        'photo_path': '',
        'birth_date': birth_date or '',
        'birth_place': '',
        'death_date': '',
        'death_place': '',
        'occupation': '',
        'notes': ''
    }

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

def marry(male_id, female_id):
    """Creates a marriage event between two people in the graph repository."""
    data_repo, graph_repo = find_repos()
    if not data_repo or not graph_repo:
        print("Error: Must be run from within a valid data repository with a 'family_graph' submodule.")
        return False

    try:
        male_commit = _find_person_commit_by_id(graph_repo, male_id)
        female_commit = _find_person_commit_by_id(graph_repo, female_id)

        if not male_commit or not female_commit:
            print("Error: Could not find one or both persons.")
            return False

        # Check if marriage already exists
        marriage_tag1 = f"marriage_{male_id[:8]}_{female_id[:8]}"
        marriage_tag2 = f"marriage_{female_id[:8]}_{male_id[:8]}"
        if marriage_tag1 in graph_repo.tags or marriage_tag2 in graph_repo.tags:
            print("Error: Marriage already registered.")
            return False

        # Create a merge commit
        merge_base = graph_repo.merge_base(male_commit, female_commit)
        graph_repo.index.merge_tree(female_commit, base=merge_base)
        commit_message = f"Marriage: {male_id} and {female_id}"
        marriage_commit = graph_repo.index.commit(commit_message, parent_commits=(male_commit, female_commit), head=False)

        # Tag the marriage commit
        marriage_tag = f"marriage_{male_id[:8]}_{female_id[:8]}"
        graph_repo.create_tag(marriage_tag, ref=marriage_commit)

        print(f"Successfully created marriage event between {male_id} and {female_id}.")
        return True

    except git.GitCommandError as e:
        print(f"Error during git operation: {e}")
        return False

def _find_person_commit_by_id(repo, person_id):
    """Finds a person's commit in the graph repo by its short or long ID."""
    try:
        obj = repo.rev_parse(person_id)
        if isinstance(obj, git.TagObject):
            return obj.object
        return obj
    except git.BadName:
        print(f"Error: Could not find person with ID '{person_id}'.")
        return None

def add_child(father_id, mother_id, child_id):
    """Adds a child to a couple, creating the marriage if it doesn't exist."""
    data_repo, graph_repo = find_repos()
    if not data_repo or not graph_repo:
        print("Error: Must be run from within a valid data repository with a 'family_graph' submodule.")
        return False

    graph_repo.head.reset(index=True, working_tree=True)

    # 1. Find all parties.
    father_commit = _find_person_commit_by_id(graph_repo, father_id)
    mother_commit = _find_person_commit_by_id(graph_repo, mother_id)
    child_commit = _find_person_commit_by_id(graph_repo, child_id)

    if not all([father_commit, mother_commit, child_commit]):
        print("Error: Could not find father, mother, or child.")
        return False

    # 2. Find or create the marriage.
    marriage_tag_name = f"marriage_{father_id[:8]}_{mother_id[:8]}"
    reverse_marriage_tag_name = f"marriage_{mother_id[:8]}_{father_id[:8]}"
    marriage_tag = None

    if marriage_tag_name in graph_repo.tags:
        marriage_tag = graph_repo.tags[marriage_tag_name]
    elif reverse_marriage_tag_name in graph_repo.tags:
        marriage_tag = graph_repo.tags[reverse_marriage_tag_name]

    if marriage_tag:
        marriage_commit = marriage_tag.commit
        print("Found existing marriage.")
    else:
        print("Marriage not found, creating it now.")
        if not marry(father_id, mother_id):
            print("Error: Failed to create marriage.")
            return False
        # After creating the marriage, we need to get the commit.
        # The marry function creates a tag, so we can find the commit through the tag.
        marriage_tag = graph_repo.tags[marriage_tag_name]
        marriage_commit = marriage_tag.commit
        graph_repo.head.reset(index=True, working_tree=True)

    # 3. Rebase the child's history onto the marriage commit.
    try:
        # We need to find the commit that is the parent of the child commit.
        # This is the commit that the child was based on.
        # In our case, this will be the GRAPH_ROOT commit.
        child_parent_commit = child_commit.parents[0]

        # We are going to rebase the child commit onto the marriage commit.
        # The rebase command will be: git rebase --onto <new_base> <old_base> <branch_to_rebase>
        # In our case: git rebase --onto marriage_commit child_parent_commit child_commit
        graph_repo.git.rebase('--onto', marriage_commit.hexsha, child_parent_commit.hexsha, child_commit.hexsha)

        # After the rebase, the child's tag will be pointing to the old commit.
        # We need to update the tag to point to the new commit.
        # The new commit will be the head of the graph repo.
        new_child_commit = graph_repo.head.commit
        graph_repo.create_tag(child_id, ref=new_child_commit, force=True, message=f"Reference to person {child_id}")

        print(f"Successfully added {child_id} as a child of {father_id} and {mother_id}.")
        return True
    except git.GitCommandError as e:
        print(f"Error during git rebase operation: {e}")
        # If the rebase fails, we should abort it.
        try:
            graph_repo.git.rebase('--abort')
        except git.GitCommandError:
            pass
        return False
