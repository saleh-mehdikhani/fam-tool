import uuid
import yaml
import os
from pathlib import Path
import git
import subprocess
import json
import shutil
import click

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

def initialize_project(root_path_str):
    """Creates a new family tree project at the specified path."""
    # Resolve path first to enable reliable comparison
    root_path = Path(root_path_str).resolve()

    graph_source_path = root_path.with_name(root_path.name + "_graph_source")

    try:
        # 1. Create and initialize the source graph repo
        graph_source_repo = git.Repo.init(graph_source_path, initial_branch='main')
        # Add README to graph_source_repo from resource file
        readme_graph_path = Path(__file__).parent / "resources" / "README_graph.md"
        (graph_source_path / 'README.md').write_text(readme_graph_path.read_text())
        graph_source_repo.index.add(['README.md'])
        # Add .gitignore to graph_source_repo from resource file
        gitignore_template_path = Path(__file__).parent / "resources" / "gitignore_template"
        (graph_source_path / '.gitignore').write_text(gitignore_template_path.read_text())
        graph_source_repo.index.add(['.gitignore'])
        graph_source_repo.git.commit('--allow-empty', '-m', "Graph Root")
        graph_source_repo.create_tag("GRAPH_ROOT", message="Graph entry point")
        print(f"Initialized graph source at: {graph_source_path}")

        # 2. Initialize the main data repo
        data_repo = git.Repo.init(root_path, initial_branch='main')
        # Add README to data_repo from resource file
        readme_data_path = Path(__file__).parent / "resources" / "README_data.md"
        (root_path / 'README.md').write_text(readme_data_path.read_text())
        data_repo.index.add(['README.md'])
        # Add .gitignore to data_repo from resource file
        gitignore_template_path = Path(__file__).parent / "resources" / "gitignore_template"
        (root_path / '.gitignore').write_text(gitignore_template_path.read_text())
        data_repo.index.add(['.gitignore'])
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

        data_repo.index.add(['.gitmodules', 'people/.gitkeep'])
        data_repo.index.commit("Initial commit: Add family_graph submodule and people directory")
        print("Created initial commit.")

    finally:
        # 5. Clean up the temporary source repo
        if graph_source_path.exists():
            shutil.rmtree(graph_source_path)
            print("Cleaned up graph source directory.")
    
    print(f"Successfully created new family tree project at {root_path}")
    return True

def initialize_remotes(data_remote, graph_remote):
    """Sets the remote URLs for the data and graph repositories."""
    data_repo, graph_repo = find_repos()
    if not data_repo or not graph_repo:
        print("Error: Must be run from within a valid data repository with a 'family_graph' submodule.")
        return False

    try:
        if 'origin' in data_repo.remotes:
            data_repo.delete_remote('origin')
        data_repo.create_remote('origin', data_remote)

        submodule = data_repo.submodule('family_graph')
        subprocess.run(['git', 'config', '--file=.gitmodules', f'submodule.{submodule.name}.url', graph_remote], check=True, cwd=data_repo.working_dir)
        
        data_repo.index.add(['.gitmodules'])
        if data_repo.is_dirty():
            data_repo.index.commit("Update submodule URL")

        if 'origin' in graph_repo.remotes:
            graph_repo.delete_remote('origin')
        graph_repo.create_remote('origin', graph_remote)

        return True
    except (git.GitCommandError, subprocess.CalledProcessError) as e:
        print(f"Error setting remote URLs: {e}")
        return False

def push_to_remote(force=False):
    """Pushes changes to the remote repositories after checking for conflicts."""
    data_repo, graph_repo = find_repos()
    if not data_repo or not graph_repo:
        print("Error: Must be run from within a valid data repository with a 'family_graph' submodule.")
        return False

    try:
        for repo, name in [(data_repo, "data"), (graph_repo, "graph")]:
            if not force and repo.is_dirty(untracked_files=True):
                print(f"Error: Uncommitted changes found in {name} repository. Please commit or stash them before pushing.")
                return False

            if not repo.remotes:
                print(f"Error: No remote repository configured for {name} repository.")
                return False

            origin = repo.remotes.origin
            
            if not force:
                try:
                    remote_branches = repo.git.ls_remote('--heads', 'origin')
                except git.GitCommandError as e:
                    if "Could not read from remote repository" in str(e):
                        print(f"Error: Could not read from remote repository for {name} repo. Please check the URL and your permissions.")
                        return False
                    else:
                        raise e

                if remote_branches:
                    origin.fetch()
                    for branch in repo.branches:
                        remote_branch_name = f"origin/{branch.name}"
                        if remote_branch_name in origin.refs:
                            remote_branch = origin.refs[branch.name]
                            if branch.commit != remote_branch.commit:
                                if repo.is_ancestor(branch.commit, remote_branch.commit):
                                    print(f"Error: Local {name} repository branch '{branch.name}' is behind the remote. Please pull the changes before pushing.")
                                    return False
                                elif not repo.is_ancestor(remote_branch.commit, branch.commit):
                                    print(f"Error: {name} repository branch '{branch.name}' has diverged from the remote. Please resolve the conflicts before pushing.")
                                    return False

        # If all checks pass, push all branches and tags for both repositories
        print(f"Pushing all branches and tags for data repository...")
        try:
            data_repo.git.push("--all", "origin", "--force" if force else None)
            data_repo.git.push("--tags", "origin", "--force" if force else None)
        except git.GitCommandError as e:
            if "duplicateEntries" in str(e.stderr):
                print("Error: The data repository is corrupt. Please run 'git fsck --full' to diagnose the problem.")
                return False
            else:
                raise e

        print("Pushing all branches and tags for graph repository...")
        try:
            graph_repo.git.push("--all", "origin", "--force" if force else None)
            graph_repo.git.push("--tags", "origin", "--force" if force else None)
        except git.GitCommandError as e:
            if "duplicateEntries" in str(e.stderr):
                print("Error: The graph repository is corrupt. Please run 'git fsck --full' to diagnose the problem.")
                return False
            else:
                raise e

        return True
    except (git.GitCommandError, IndexError) as e:
        print(f"Error during push: {e}")
        return False

def display_graph_log():
    """Displays the Git graph log of the graph repository."""
    data_repo, graph_repo = find_repos()
    if not data_repo or not graph_repo:
        print("Error: Must be run from within a valid data repository with a 'family_graph' submodule.")
        return False

    try:
        # Change directory to the graph repo's working directory
        original_cwd = os.getcwd()
        os.chdir(graph_repo.working_dir)

        # Run the git log command
        result = subprocess.run(
            ['git', 'log', '--graph', '--oneline', '--decorate', '--all', '--color'],
            capture_output=True,
            text=True,
            check=True
        )
        print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error running git log: {e}")
        print(f"Stderr: {e.stderr}")
        return False
    finally:
        # Change back to the original directory
        os.chdir(original_cwd)

def find_person_by_name(name):
    """Finds people by name and lists their full name and short ID."""
    data_repo, graph_repo = find_repos()
    if not data_repo or not graph_repo:
        print("Error: Must be run from within a valid data repository with a 'family_graph' submodule.")
        return False

    matches = _get_person_id_by_name(data_repo, name)

    if not matches:
        print(f"No people found matching '{name}'.")
        return False
    else:
        print("Found the following people:")
        for person in matches:
            short_id = person['id'][:8] if person['id'] else 'N/A'
            print(f"- {person['name']} (ID: {short_id})")
        return True

# --- Core Logic ---

def add_person(first_name, last_name, middle_name, birth_date, gender, nickname, father_id=None, mother_id=None):
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

    # 2. Create graph commit containing a reference to the person's data file
    try:
        parent_commit = None
        if father_id and mother_id:
            resolved_father_id = _resolve_person_id_input(data_repo, father_id, "father")
            resolved_mother_id = _resolve_person_id_input(data_repo, mother_id, "mother")

            if not resolved_father_id or not resolved_mother_id:
                return False # Abort if IDs cannot be resolved

            marriage_commit = _find_marriage_commit(graph_repo, resolved_father_id, resolved_mother_id)
            if not marriage_commit:
                father_details = _get_person_name_by_id(data_repo, resolved_father_id)
                mother_details = _get_person_name_by_id(data_repo, resolved_mother_id)
                print(f"Marriage between {father_details['first_name']} {father_details['last_name']} ({resolved_father_id}) and {mother_details['first_name']} {mother_details['last_name']} ({resolved_mother_id}) not found.")
                if click.confirm(f"Do you want to create a marriage between {father_details['first_name']} {father_details['last_name']} and {mother_details['first_name']} {mother_details['last_name']} now?"):
                    if not marry(resolved_father_id, resolved_mother_id, commit_submodule=False):
                        print("Error: Failed to create marriage.")
                        return False
                    # After marry, the tag should exist, so we can find the commit
                    marriage_commit = _find_marriage_commit(graph_repo, resolved_father_id, resolved_mother_id)
                    if not marriage_commit: # Should not happen if marry was successful
                        print("Error: Marriage was created but commit could not be found.")
                        return False
                    parent_commit = marriage_commit
                    print(f"Found marriage commit: {marriage_commit.hexsha}")
                else:
                    print("Operation aborted by user.")
                    return False
            else:
                parent_commit = marriage_commit
                print(f"Found marriage commit: {marriage_commit.hexsha}")
        else:
            graph_root_commit = graph_repo.tags['GRAPH_ROOT'].commit
            parent_commit = graph_root_commit

        graph_repo.head.reference = parent_commit
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
    data_repo.git.add('family_graph')
    data_repo.index.commit(f"feat: Add person '{full_name}' ({short_id})")
    print("Committed person file to data repository.")

    return True

def marry(male, female, commit_submodule=True):
    """Creates a marriage event between two people in the graph repository."""
    data_repo, graph_repo = find_repos()
    if not data_repo or not graph_repo:
        print("Error: Must be run from within a valid data repository with a 'family_graph' submodule.")
        return False

    resolved_male_id = _resolve_person_id_input(data_repo, male, "male")
    resolved_female_id = _resolve_person_id_input(data_repo, female, "female")

    if not resolved_male_id or not resolved_female_id:
        return False # Abort if IDs cannot be resolved

    try:
        male_commit = _find_person_commit_by_id(graph_repo, resolved_male_id)
        female_commit = _find_person_commit_by_id(graph_repo, resolved_female_id)

        if not male_commit or not female_commit:
            print("Error: Could not find one or both persons.")
            return False

        # Check if marriage already exists
        marriage_tag1 = f"marriage_{resolved_male_id[:8]}_{resolved_female_id[:8]}"
        marriage_tag2 = f"marriage_{resolved_female_id[:8]}_{resolved_male_id[:8]}"
        if marriage_tag1 in graph_repo.tags or marriage_tag2 in graph_repo.tags:
            print("Error: Marriage already registered.")
            return False

        # Create a merge commit
        merge_base = graph_repo.merge_base(male_commit, female_commit)
        graph_repo.index.merge_tree(female_commit, base=merge_base)
        commit_message = f"Marriage: {resolved_male_id} and {resolved_female_id}"
        marriage_commit = graph_repo.index.commit(commit_message, parent_commits=(male_commit, female_commit), head=False)

        # Tag the marriage commit
        marriage_tag = f"marriage_{resolved_male_id[:8]}_{resolved_female_id[:8]}"
        graph_repo.create_tag(marriage_tag, ref=marriage_commit)

        print(f"Successfully created marriage event between {resolved_male_id} and {resolved_female_id}.")

        if commit_submodule:
            # Commit submodule update to data repo
            data_repo.git.add('family_graph')
            data_repo.index.commit(f"feat: Register marriage between {resolved_male_id} and {resolved_female_id}")
            print("Committed marriage event to data repository.")

        return True

    except git.GitCommandError as e:
        print(f"Error during git operation: {e}")
        return False

def _find_person_commit_by_id(repo, person_id):
    """Finds a person's commit in the graph repo by its short or long ID."""
    try:
        # Try to find by full ID (commit SHA or tag name if it's a full ID)
        obj = repo.rev_parse(person_id)
        if isinstance(obj, git.TagObject):
            return obj.object
        return obj
    except git.BadName:
        # If not found by full ID, try by short ID (which is how person tags are created)
        short_id = person_id[:8]
        try:
            obj = repo.rev_parse(short_id)
            if isinstance(obj, git.TagObject):
                return obj.object
            return obj
        except git.BadName:
            print(f"Error: Could not find person with ID '{person_id}'.")
            return None

def _find_marriage_commit(repo, id1, id2):
    """Finds a marriage commit by two person IDs."""
    marriage_tag_name1 = f"marriage_{id1[:8]}_{id2[:8]}"
    marriage_tag_name2 = f"marriage_{id2[:8]}_{id1[:8]}"
    
    if marriage_tag_name1 in repo.tags:
        return repo.tags[marriage_tag_name1].commit
    elif marriage_tag_name2 in repo.tags:
        return repo.tags[marriage_tag_name2].commit
    return None

def _get_person_name_by_id(data_repo, person_id):
    """Retrieves a person's name details (first, last, full) from their YAML file."""
    people_dir = Path(data_repo.working_dir) / 'people'
    for person_file in people_dir.glob(f"{person_id[:8]}*.yml"):
        with open(person_file, 'r', encoding='utf-8') as f:
            person_data = yaml.safe_load(f)
            if person_data.get('id', '').startswith(person_id):
                return {
                    'id': person_data.get('id'),
                    'first_name': person_data.get('first_name', ''),
                    'last_name': person_data.get('last_name', ''),
                    'name': person_data.get('name', person_id)
                }
    return {'id': None, 'first_name': person_id, 'last_name': '', 'name': person_id} # Return ID if person file not found

def _get_person_id_by_name(data_repo, name):
    """
    Retrieves person IDs and details by name.
    Returns a list of dictionaries: [{'id': ..., 'first_name': ..., 'last_name': ..., 'name': ...}]
    """
    matches = []
    people_dir = Path(data_repo.working_dir) / 'people'
    for person_file in people_dir.glob('*.yml'):
        with open(person_file, 'r', encoding='utf-8') as f:
            person_data = yaml.safe_load(f)
            full_name = person_data.get('name', '').lower()
            first_name = person_data.get('first_name', '').lower()
            last_name = person_data.get('last_name', '').lower()

            if name.lower() in full_name or \
               name.lower() == first_name or \
               name.lower() == last_name:
                matches.append({
                    'id': person_data.get('id'),
                    'first_name': person_data.get('first_name'),
                    'last_name': person_data.get('last_name'),
                    'name': person_data.get('name')
                })
    return matches

def _resolve_person_id_input(data_repo, input_str, role):
    """
    Resolves a person ID from an input string, which can be an ID or a name.
    Handles interactive selection if multiple matches are found for a name.
    """
    if not input_str:
        return None

    # First, try to find by ID (short or full UUID)
    # _get_person_id_by_name can handle partial IDs as search terms
    # but it's primarily for names. Let's use _get_person_name_by_id to check if it's a valid ID
    # and then _get_person_id_by_name to get the full ID if it's a name.

    # Check if input_str is a valid ID (short or full)
    # We can use _get_person_name_by_id to check if a person with this ID exists
    person_details_by_id = _get_person_name_by_id(data_repo, input_str)
    if person_details_by_id and person_details_by_id['id'] is not None: # Check if a person was actually found by ID
        if person_details_by_id['id'] == input_str: # Exact ID match
            return input_str
        elif person_details_by_id['id'].startswith(input_str): # Short ID match
            return person_details_by_id['id']

    # If not found as an ID, assume it's a name
    matches = _get_person_id_by_name(data_repo, input_str)

    if not matches:
        print(f"Error: No person found matching '{input_str}' for {role}.")
        return None
    elif len(matches) == 1:
        return matches[0]['id']
    else:
        print(f"Multiple people found matching '{input_str}' for {role}:")
        for i, person in enumerate(matches):
            print(f"{i+1}. {person['first_name']} {person['last_name']} (ID: {person['id'][:8]})") # Display short ID
        
        while True:
            choice = click.prompt("Please enter the number corresponding to the correct person")
            try:
                choice_idx = int(choice) - 1
                if 0 <= choice_idx < len(matches):
                    return matches[choice_idx]['id']
                else:
                    print("Invalid choice. Please enter a number from the list.")
            except ValueError:
                print("Invalid input. Please enter a number.")

def _make_child_rewrite_permanent(graph_repo, child_commit, marriage_commit):

    original_cwd = os.getcwd()
    os.chdir(graph_repo.working_dir)

    try:
        # Create graft (temporary parent change)
        graph_repo.git.replace('--graft', child_commit.hexsha, marriage_commit.hexsha)

        # Run git-filter-repo to make it permanent
        subprocess.run([
            "git", "filter-repo",
            "--replace-refs", "delete-no-add",
            "--force"
        ], check=True)

        print("History rewrite completed successfully.")
        return True

    except subprocess.CalledProcessError as e:
        print(f"Error during history rewrite: {e}")
        return False

    finally:
        os.chdir(original_cwd)
        try:
            graph_repo.git.replace('-d', child_commit.hexsha)
        except Exception:
            pass

def add_child(father_id, mother_id, child_id):
    """Adds a child to a couple, creating the marriage if it doesn't exist."""
    data_repo, graph_repo = find_repos()
    if not data_repo or not graph_repo:
        print("Error: Must be run from within a valid data repository with a 'family_graph' submodule.")
        return False

    graph_repo.head.reset(index=True, working_tree=True)

    # 1. Find all parties.
    resolved_father_id = _resolve_person_id_input(data_repo, father_id, "father")
    resolved_mother_id = _resolve_person_id_input(data_repo, mother_id, "mother")
    resolved_child_id = _resolve_person_id_input(data_repo, child_id, "child") # Child can also be by name

    if not resolved_father_id or not resolved_mother_id or not resolved_child_id:
        return False # Abort if IDs cannot be resolved

    father_commit = _find_person_commit_by_id(graph_repo, resolved_father_id)
    mother_commit = _find_person_commit_by_id(graph_repo, resolved_mother_id)
    child_commit = _find_person_commit_by_id(graph_repo, resolved_child_id)

    if not all([father_commit, mother_commit, child_commit]):
        print("Error: Could not find father, mother, or child.")
        return False

    # 2. Find or create the marriage.
    marriage_commit = _find_marriage_commit(graph_repo, resolved_father_id, resolved_mother_id)

    if marriage_commit:
        print("Found existing marriage.")
    else:
        father_details = _get_person_name_by_id(data_repo, resolved_father_id)
        mother_details = _get_person_name_by_id(data_repo, resolved_mother_id)
        print(f"Marriage between {father_details['first_name']} {father_details['last_name']} ({resolved_father_id}) and {mother_details['first_name']} {mother_details['last_name']} ({resolved_mother_id}) not found.")
        if click.confirm(f"Do you want to create a marriage between {father_details['first_name']} {father_details['last_name']} and {mother_details['first_name']} {mother_details['last_name']} now?"):
            if not marry(resolved_father_id, resolved_mother_id):
                print("Error: Failed to create marriage.")
                return False
            # After marry, the tag should exist, so we can find the commit
            marriage_commit = _find_marriage_commit(graph_repo, resolved_father_id, resolved_mother_id)
            if not marriage_commit: # Should not happen if marry was successful
                print("Error: Marriage was created but commit could not be found.")
                return False
            graph_repo.head.reset(index=True, working_tree=True)
        else:
            print("Operation aborted by user.")
            return False

    # 3. Rewrite history to make the child a child of the marriage.
    if not _make_child_rewrite_permanent(graph_repo, child_commit, marriage_commit):
        return False

    # 4. Update tags
    commit_map_path = os.path.join(graph_repo.git_dir, "filter-repo", "commit-map")
    if os.path.exists(commit_map_path):
        commit_map = {}
        with open(commit_map_path, "r") as f:
            for line in f:
                old_sha, new_sha = line.strip().split()
                commit_map[old_sha] = new_sha

        for tag in graph_repo.tags:
            if tag.commit.hexsha in commit_map:
                new_commit = graph_repo.commit(commit_map[tag.commit.hexsha])
                if tag.tag is not None:  # annotated tag
                    graph_repo.create_tag(tag.name, ref=new_commit, force=True, message=tag.tag.message)
                else:  # lightweight tag
                    graph_repo.create_tag(tag.name, ref=new_commit, force=True)

    print(f"Successfully added {resolved_child_id} as a child of {resolved_father_id} and {resolved_mother_id}.")

    # Commit submodule update to data repo
    data_repo.git.add('family_graph')
    data_repo.index.commit(f"feat: Add child {resolved_child_id} to {resolved_father_id} and {resolved_mother_id}")
    print("Committed child relationship to data repository.")

    return True

def _calculate_generations(nodes, edges):
    node_map = {node['id']: node for node in nodes}

    # Initial setup: find roots (those who are not children) and set their generation to 0.
    child_ids = set(edge['to'] for edge in edges if edge['type'] == 'child')
    for node in nodes:
        node['generation'] = 0 if node['id'] not in child_ids else -1

    # Iteratively propagate generations until no more changes are made
    changed_in_pass = True
    pass_count = 0
    max_passes = len(nodes) * 2 # A generous limit
    
    print("Calculating generations...")
    while changed_in_pass:
        pass_count += 1
        if pass_count > max_passes:
            print("Warning: Generation calculation took too many passes. Aborting.")
            break
        
        changed_in_pass = False

        # Pass 1: Propagate generations to children
        for edge in edges:
            if edge['type'] == 'child':
                parent = node_map.get(edge['from'])
                child = node_map.get(edge['to'])
                if parent and child and parent['generation'] != -1:
                    new_gen = parent['generation'] + 1
                    if child['generation'] == -1 or new_gen > child['generation']:
                        child['generation'] = new_gen
                        changed_in_pass = True

        # Pass 2: Propagate generations to partners
        for edge in edges:
            if edge['type'] == 'partner':
                p1 = node_map.get(edge['from'])
                p2 = node_map.get(edge['to'])
                if p1 and p2:
                    max_gen = max(p1['generation'], p2['generation'])
                    if p1['generation'] != max_gen:
                        p1['generation'] = max_gen
                        changed_in_pass = True
                    if p2['generation'] != max_gen:
                        p2['generation'] = max_gen
                        changed_in_pass = True
    print("Generation calculation complete.")

def export_to_json(output_filename):
    data_repo, graph_repo = find_repos()
    if not data_repo or not graph_repo:
        print("Error: Must be run from within a valid data repository with a 'family_graph' submodule.")
        return False

    nodes = []
    edges = []

    # Read person data (nodes)
    people_files = list(Path(data_repo.working_dir).glob('people/*.yml'))
    with click.progressbar(people_files, label='Reading person data') as bar:
        for person_file in bar:
            with open(person_file, 'r', encoding='utf-8') as f:
                person_data = yaml.safe_load(f)
                nodes.append(person_data)

    # Extract relationships (edges) from graph repo
    all_tags = graph_repo.tags
    with click.progressbar(all_tags, label='Finding marriages') as bar:
        for tag in bar:
            if tag.name.startswith("marriage_"):
                # Marriage tags are like marriage_shortid1_shortid2
                parts = tag.name.split('_')
                if len(parts) == 3:
                    id1_short = parts[1]
                    id2_short = parts[2]
                    # Find full IDs from nodes
                    id1_full = next((node['id'] for node in nodes if node['id'].startswith(id1_short)), None)
                    id2_full = next((node['id'] for node in nodes if node['id'].startswith(id2_short)), None)
                    if id1_full and id2_full:
                        edges.append({"from": id1_full, "to": id2_full, "type": "partner"})

    # Pre-build a map of marriage commits to their tags for efficiency
    marriage_tags = [tag for tag in all_tags if tag.name.startswith("marriage_")]
    marriage_commit_to_tag = {tag.commit.hexsha: tag for tag in marriage_tags}

    # Find person tags
    person_tags = [tag for tag in all_tags if not tag.name.startswith("marriage_") and tag.name != "GRAPH_ROOT"]

    with click.progressbar(person_tags, label='Finding parent-child relationships') as bar:
        for tag in bar:
            child_commit = tag.commit
            child_id_short = tag.name
            child_id_full = next((node['id'] for node in nodes if node['id'].startswith(child_id_short)), None)

            if child_id_full and child_commit.parents:
                for parent_commit in child_commit.parents:
                    if parent_commit.hexsha in marriage_commit_to_tag:
                        marriage_tag = marriage_commit_to_tag[parent_commit.hexsha]
                        marriage_tag_name = marriage_tag.name
                        
                        parts = marriage_tag_name.split('_')
                        if len(parts) == 3:
                            p1_short = parts[1]
                            p2_short = parts[2]
                            p1_full = next((node['id'] for node in nodes if node['id'].startswith(p1_short)), None)
                            p2_full = next((node['id'] for node in nodes if node['id'].startswith(p2_short)), None)
                            if p1_full and p2_full:
                                edges.append({"from": p1_full, "to": child_id_full, "type": "child"})
                                edges.append({"from": p2_full, "to": child_id_full, "type": "child"})

    # --- Call the generation calculation function ---
    _calculate_generations(nodes, edges)

    output_data = {
        "nodes": nodes,
        "edges": edges
    }

    build_dir = Path(data_repo.working_dir) / 'build'
    build_dir.mkdir(exist_ok=True)
    output_path = build_dir / output_filename

    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        print(f"Successfully exported data to {output_path}")
        return True
    except Exception as e:
        print(f"Error writing JSON file: {e}")
        return False

def _get_all_people(data_repo):
    """
    Retrieves all people from the data repository.
    Returns a list of dictionaries: [{'id': ..., 'first_name': ..., 'last_name': ..., 'name': ...}]
    """
    people = []
    people_dir = Path(data_repo.working_dir) / 'people'
    for person_file in people_dir.glob('*.yml'):
        with open(person_file, 'r', encoding='utf-8') as f:
            person_data = yaml.safe_load(f)
            people.append({
                'id': person_data.get('id'),
                'first_name': person_data.get('first_name'),
                'last_name': person_data.get('last_name'),
                'name': person_data.get('name')
            })
    return people

def _get_relationships(graph_repo, nodes):
    parents_map = {}
    children_map = {}
    
    # Pre-build a map of marriage commits to their tags for efficiency
    marriage_tags = [tag for tag in graph_repo.tags if tag.name.startswith("marriage_")]
    marriage_commit_to_tag = {tag.commit.hexsha: tag for tag in marriage_tags}

    person_tags = [tag for tag in graph_repo.tags if not tag.name.startswith("marriage_") and tag.name != "GRAPH_ROOT"]

    for tag in person_tags:
        child_commit = tag.commit
        child_id_short = tag.name
        child_id_full = next((node['id'] for node in nodes if node['id'].startswith(child_id_short)), None)

        if child_id_full and child_commit.parents:
            for parent_commit in child_commit.parents:
                if parent_commit.hexsha in marriage_commit_to_tag:
                    marriage_tag = marriage_commit_to_tag[parent_commit.hexsha]
                    marriage_tag_name = marriage_tag.name
                    
                    parts = marriage_tag_name.split('_')
                    if len(parts) == 3:
                        p1_short = parts[1]
                        p2_short = parts[2]
                        p1_full = next((node['id'] for node in nodes if node['id'].startswith(p1_short)), None)
                        p2_full = next((node['id'] for node in nodes if node['id'].startswith(p2_short)), None)
                        if p1_full and p2_full:
                            parents_map[child_id_full] = [p1_full, p2_full]
                            if p1_full not in children_map:
                                children_map[p1_full] = []
                            children_map[p1_full].append(child_id_full)
                            if p2_full not in children_map:
                                children_map[p2_full] = []
                            children_map[p2_full].append(child_id_full)
    return parents_map, children_map

def list_people(name=None, show_children=False, show_parents=False):
    """Lists people with optional details about their children and parents."""
    data_repo, graph_repo = find_repos()
    if not data_repo or not graph_repo:
        print("Error: Must be run from within a valid data repository with a 'family_graph' submodule.")
        return False

    all_people = _get_all_people(data_repo)
    people_to_list = []

    if name:
        name_lower = name.lower()
        for person in all_people:
            if name_lower in person.get('name', '').lower() or \
               name_lower == person.get('first_name', '').lower() or \
               name_lower == person.get('last_name', '').lower():
                people_to_list.append(person)
    else:
        people_to_list = all_people

    if not people_to_list:
        click.secho("No people found.", fg='yellow')
        return False

    click.secho(f"Found {len(people_to_list)} matching records out of {len(all_people)} total records.", fg='blue')

    parents_map, children_map = {}, {}
    if show_children or show_parents:
        parents_map, children_map = _get_relationships(graph_repo, all_people)

    # Create a map of ID to person details for easy lookup
    people_map = {p['id']: p for p in all_people}

    for person in sorted(people_to_list, key=lambda p: p.get('name', '')):
        short_id = person['id'][:8] if person.get('id') else 'N/A'
        click.secho(f"- {person.get('name', 'Unknown')} (ID: {short_id})", fg='cyan')

        if show_parents and person.get('id') in parents_map:
            parent_ids = parents_map[person['id']]
            click.secho("    Parents:", fg='green')
            for parent_id in parent_ids:
                parent_details = people_map.get(parent_id)
                if parent_details:
                    parent_short_id = parent_id[:8]
                    click.echo(f"        - {parent_details.get('name', 'Unknown')} (ID: {parent_short_id})")

        if show_children and person.get('id') in children_map:
            child_ids = children_map[person['id']]
            click.secho("    Children:", fg='yellow')
            for child_id in child_ids:
                child_details = people_map.get(child_id)
                if child_details:
                    child_short_id = child_id[:8]
                    click.echo(f"        - {child_details.get('name', 'Unknown')} (ID: {child_short_id})")
    
    return True