import uuid
import yaml
import os
from pathlib import Path
import git
from git import Repo, BadName
import subprocess
import json
import click
import shutil

# --- Custom Exceptions ---

class CommitHasChildrenError(Exception):
    pass

# --- Commit Removal Functions ---

def remove_commit(repo_path: str, commit_sha: str):
    """
    Remove a commit from a Git repository if it has no children (is a leaf).
    If HEAD points to the commit, it will be moved to its parent before removal.
    """
    repo = Repo(repo_path)

    # Verify commit exists and get full SHA
    try:
        commit = repo.commit(commit_sha)
    except BadName:
        raise ValueError(f"Commit {commit_sha} not found in {repo_path}")
    full_sha = commit.hexsha

    # Check for children
    children = []
    for ref in repo.references:
        for c in repo.iter_commits(ref):
            if full_sha in [p.hexsha for p in c.parents]:
                children.append(c.hexsha)
    if children:
        raise CommitHasChildrenError(f"Commit {full_sha} has children: {children}")

    # Move HEAD if necessary
    if repo.head.commit.hexsha == full_sha:
        if not commit.parents:
            raise RuntimeError("Cannot remove root commit")
        parent_sha = commit.parents[0].hexsha
        repo.git.checkout(parent_sha)

    # Delete tags pointing to the commit
    for tag in repo.tags:
        if tag.commit.hexsha == full_sha:
            repo.delete_tag(tag)

    # Delete branches pointing to the commit
    for head in repo.heads:
        if head.commit.hexsha == full_sha:
            repo.git.branch("-D", head.name)

    # Drop the commit with git-filter-repo
    # Save remote URLs before git filter-repo operation
    saved_remotes = {}
    try:
        for remote in repo.remotes:
            saved_remotes[remote.name] = list(remote.urls)
    except Exception:
        # If we can't read remotes, continue without saving
        pass
    
    # Clean up any previous git filter-repo state to avoid interactive prompts
    filter_repo_dir = os.path.join(repo_path, '.git', 'filter-repo')
    if os.path.exists(filter_repo_dir):
        import shutil
        shutil.rmtree(filter_repo_dir)
    
    cmd = [
        "git", "filter-repo",
        "--force",
        f"--commit-callback=exec('if commit.original_id == b\"{full_sha}\": commit.skip()')"
    ]
    subprocess.run(cmd, cwd=repo_path, check=True)
    
    # Restore remote URLs if they were removed
    for remote_name, urls in saved_remotes.items():
        try:
            # Check if remote still exists
            current_remotes = [r.name for r in repo.remotes]
            if remote_name not in current_remotes:
                # Remote was removed, recreate it
                if urls:
                    repo.create_remote(remote_name, urls[0])
        except Exception:
            # If we can't restore remotes, continue silently
            pass

    return True

def remove_commit_from_graph(commit_sha, graph_repo=None):
    """
    Wrapper function to remove a commit from the graph repository.
    Uses the new remove_commit implementation.
    Requires a full SHA (40 characters) to be passed.
    """
    if not graph_repo:
        click.secho("Error: graph_repo is required", fg='red')
        return False
    
    # Validate that commit_sha is a full SHA (40 hex characters)
    if not isinstance(commit_sha, str) or len(commit_sha) != 40 or not all(c in '0123456789abcdef' for c in commit_sha.lower()):
        click.secho(f"Error: commit_sha must be a full 40-character SHA, got: {commit_sha}", fg='red')
        return False
    
    try:
        # Use the new remove_commit function with graph repo path and full commit SHA
        remove_commit(graph_repo.working_dir, commit_sha)
        click.echo(f"Successfully removed commit {commit_sha[:8]} from graph repository")
        return True
    except ValueError as e:
        click.secho(f"Error: {e}", fg='red')
        return False
    except CommitHasChildrenError as e:
        click.secho(f"Error: {e}", fg='red')
        return False
    except subprocess.CalledProcessError as e:
        click.secho(f"Error during git filter-repo operation: {e}", fg='red')
        return False
    except Exception as e:
        click.secho(f"Unexpected error removing commit: {e}", fg='red')
        return False

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
    root_path = Path(root_path_str).resolve()
    graph_path = root_path / 'family_graph'

    try:
        # 1. Initialize the main data repo
        data_repo = git.Repo.init(root_path, initial_branch='main')
        readme_data_path = Path(__file__).parent / "resources" / "README_data.md"
        (root_path / 'README.md').write_text(readme_data_path.read_text())
        data_repo.index.add(['README.md'])
        gitignore_template_path = Path(__file__).parent / "resources" / "gitignore_template"
        (root_path / '.gitignore').write_text(gitignore_template_path.read_text())
        data_repo.index.add(['.gitignore'])
        print(f"Initialized data repo at: {root_path}")

        # 2. Initialize the graph repo
        graph_repo = git.Repo.init(graph_path, initial_branch='main')
        readme_graph_path = Path(__file__).parent / "resources" / "README_graph.md"
        (graph_path / 'README.md').write_text(readme_graph_path.read_text())
        graph_repo.index.add(['README.md'])
        gitignore_template_path = Path(__file__).parent / "resources" / "gitignore_template"
        (graph_path / '.gitignore').write_text(gitignore_template_path.read_text())
        graph_repo.index.add(['.gitignore'])
        graph_repo.index.commit("Initial commit")
        graph_repo.git.commit('--allow-empty', '-m', "Graph Root")
        graph_repo.create_tag("GRAPH_ROOT", message="Graph entry point")
        print(f"Initialized graph repo at: {graph_path}")

        # 3. Add the graph repo as a submodule
        subprocess.run(['git', 'submodule', 'add', '-b', 'main', './family_graph', 'family_graph'], check=True, cwd=root_path)
        print("Added family_graph submodule.")

        # 4. Create people directory and initial commit
        (root_path / 'people').mkdir()
        (root_path / 'people' / '.gitkeep').touch()

        data_repo.index.add(['.gitmodules', 'people/.gitkeep'])
        data_repo.index.commit("Initial commit: Add family_graph submodule and people directory")
        print("Created initial commit.")

    except Exception as e:
        print(f"An error occurred: {e}")
        return False

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
            short_id = _get_short_id(person['id'])
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
    short_id = _get_short_id(person_id)
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

            # Check for child-partner conflict
            if _find_marriage_commit(graph_repo, resolved_father_id, person_id) or \
               _find_marriage_commit(graph_repo, resolved_mother_id, person_id):
                print("Error: A person cannot be a child of their partner.")
                return False

            marriage_commit = _find_marriage_commit(graph_repo, resolved_father_id, resolved_mother_id)
            if not marriage_commit:
                father_details = _get_person_name_by_id(data_repo, resolved_father_id)
                mother_details = _get_person_name_by_id(data_repo, resolved_mother_id)
                father_name = click.style(f"{father_details['first_name']} {father_details['last_name']}", fg='yellow', bold=True)
                mother_name = click.style(f"{mother_details['first_name']} {mother_details['last_name']}", fg='yellow', bold=True)
                print(f"Marriage between {father_name} ({resolved_father_id}) and {mother_name} ({resolved_mother_id}) not found.")
                if click.confirm(f"Do you want to create a marriage between {father_name} and {mother_name} now?"):
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

    return short_id

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

    # Check if trying to marry a person to themselves
    if resolved_male_id == resolved_female_id:
        print("Error: A person cannot marry themselves.")
        return False

    nodes = _get_all_people(data_repo)
    parents_map, _ = _get_relationships(graph_repo, nodes)

    male_ancestors = _get_ancestors(resolved_male_id, parents_map)
    female_ancestors = _get_ancestors(resolved_female_id, parents_map)

    if resolved_male_id in female_ancestors or resolved_female_id in male_ancestors:
        if not click.confirm("Warning: You are about to create a marriage between a person and their ancestor. Do you want to proceed?"):
            print("Operation aborted by user.")
            return False

    # Check if this specific marriage pair already exists
    if _find_marriage_commit(graph_repo, resolved_male_id, resolved_female_id):
        print("Error: Marriage already registered.")
        return False

    try:
        male_commit = _find_person_commit_by_id(graph_repo, resolved_male_id)
        female_commit = _find_person_commit_by_id(graph_repo, resolved_female_id)

        if not male_commit or not female_commit:
            print("Error: Could not find one or both persons.")
            return False

        # Create a merge commit
        merge_base = graph_repo.merge_base(male_commit, female_commit)
        graph_repo.index.merge_tree(female_commit, base=merge_base)
        commit_message = f"Marriage: {_get_short_id(resolved_male_id)} and {_get_short_id(resolved_female_id)}"
        marriage_commit = graph_repo.index.commit(commit_message, parent_commits=(male_commit, female_commit))

        # Tag the marriage commit
        marriage_tag = f"marriage_{_get_short_id(resolved_male_id)}_{_get_short_id(resolved_female_id)}"
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



def _find_marriage_commit(repo, id1, id2):
    """Finds a marriage commit by two person IDs."""
    marriage_tag_name1 = f"marriage_{_get_short_id(id1)}_{_get_short_id(id2)}"
    marriage_tag_name2 = f"marriage_{_get_short_id(id2)}_{_get_short_id(id1)}"
    
    if marriage_tag_name1 in repo.tags:
        return repo.tags[marriage_tag_name1].commit
    elif marriage_tag_name2 in repo.tags:
        return repo.tags[marriage_tag_name2].commit
    return None

def _get_person_name_by_id(data_repo, person_id):
    """Retrieves a person's name details (first, last, full) from their YAML file."""
    people_dir = Path(data_repo.working_dir) / 'people'
    for person_file in people_dir.glob(f"{_get_short_id(person_id)}*.yml"):
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
    person_details_by_id = _get_person_name_by_id(data_repo, input_str)
    if person_details_by_id and person_details_by_id['id'] is not None:
        if person_details_by_id['id'] == input_str:
            return input_str
        elif person_details_by_id['id'].startswith(input_str):
            return person_details_by_id['id']

    # If not found as an ID, assume it's a name
    matches = _get_person_id_by_name(data_repo, input_str)

    if not matches:
        # Fallback to graph repo if no data file is found
        _, graph_repo = find_repos()
        if graph_repo:
            try:
                tag = graph_repo.tags[input_str]
                # We can't get the full ID from the tag, but we can confirm the person exists.
                # We will return the short ID and let the caller handle it.
                return input_str
            except (IndexError, KeyError):
                pass

        print(f"Error: No person found matching '{input_str}' for {role}.")
        return None
    elif len(matches) == 1:
        return matches[0]['id']
    else:
        print(f"Multiple people found matching '{input_str}' for {role}:")
        for i, person in enumerate(matches):
            print(f"{i+1}. {person['first_name']} {person['last_name']} (ID: {_get_short_id(person['id'])})") # Display short ID
        
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
            "--force",
            "--preserve-settings"
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

def export_to_json(output_filename):
    data_repo, graph_repo = find_repos()
    if not data_repo or not graph_repo:
        print("Error: Must be run from within a valid data repository with a 'family_graph' submodule.")
        return False

    nodes = _get_all_people(data_repo)
    edges = _get_edges(graph_repo, nodes)

    # --- Call the generation calculation function ---
    _calculate_generations(nodes, edges)

    output_data = {
        "nodes": nodes,
        "edges": edges
    }

    build_dir = Path(data_repo.working_dir) / 'build'
    build_dir.mkdir(exist_ok=True)
    output_path = build_dir / output_filename
    
    # Create parent directories for the output file if needed
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        # Write the JSON data file
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        print(f"Successfully exported data to {output_path}")
        
        # Copy visualizer files to create a complete static website
        visualizer_dir = Path(__file__).parent.parent / 'visualizer'
        
        if visualizer_dir.exists():
            print("Copying visualizer files for static website deployment...")
            
            # List of files to copy from visualizer directory
            files_to_copy = ['index.html', 'script.js', 'style.css']
            
            for file_name in files_to_copy:
                src_file = visualizer_dir / file_name
                if src_file.exists():
                    dst_file = build_dir / file_name
                    shutil.copy2(src_file, dst_file)
                    print(f"  Copied {file_name}")
                else:
                    print(f"  Warning: {file_name} not found in visualizer directory")
            
            # Copy imgs folder if it exists
            imgs_dir = Path(data_repo.working_dir) / 'imgs'
            if imgs_dir.exists():
                dst_imgs_dir = build_dir / 'imgs'
                if dst_imgs_dir.exists():
                    shutil.rmtree(dst_imgs_dir)
                shutil.copytree(imgs_dir, dst_imgs_dir)
                print(f"  Copied imgs folder with {len(list(imgs_dir.glob('*')))} files")
            else:
                print("  Warning: imgs folder not found in data repository")
            
            # Rename the JSON file to 'data.json' as expected by the visualizer
            if output_filename != 'data.json':
                data_json_path = build_dir / 'data.json'
                shutil.copy2(output_path, data_json_path)
                print(f"  Created data.json for visualizer")
            
            print(f"Static website ready for deployment in: {build_dir}")
            print("You can now deploy the entire 'build' directory to any static web hosting service.")
        else:
            print(f"Warning: Visualizer directory not found at {visualizer_dir}")
            print("Only JSON data exported.")
        
        return True
    except Exception as e:
        print(f"Error during export: {e}")
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
                'name': person_data.get('name'),
                'photo_path': person_data.get('photo_path')
            })
    return people

def _get_relationships(graph_repo, nodes):
    parents_map = {}
    children_map = {}
    
    edges = _get_edges(graph_repo, nodes)

    for edge in edges:
        if edge['type'] == 'child':
            parent_id = edge['from']
            child_id = edge['to']
            
            if child_id not in parents_map:
                parents_map[child_id] = []
            parents_map[child_id].append(parent_id)

            if parent_id not in children_map:
                children_map[parent_id] = []
            children_map[parent_id].append(child_id)
            
    return parents_map, children_map

def _get_ancestors(person_id, parents_map):
    ancestors = set()
    if person_id in parents_map:
        parents = parents_map[person_id]
        for parent_id in parents:
            ancestors.add(parent_id)
            ancestors.update(_get_ancestors(parent_id, parents_map))
    return ancestors

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
        short_id = _get_short_id(person.get('id'))
        click.secho(f"- {person.get('name', 'Unknown')} (ID: {short_id})", fg='cyan')

        if show_parents and person.get('id') in parents_map:
            parent_ids = parents_map[person['id']]
            click.secho("    Parents:", fg='green')
            for parent_id in parent_ids:
                parent_details = people_map.get(parent_id)
                if parent_details:
                    parent_short_id = _get_short_id(parent_id)
                    click.echo(f"        - {parent_details.get('name', 'Unknown')} (ID: {parent_short_id})")

        if show_children and person.get('id') in children_map:
            child_ids = children_map[person['id']]
            click.secho("    Children:", fg='yellow')
            for child_id in child_ids:
                child_details = people_map.get(child_id)
                if child_details:
                    child_short_id = _get_short_id(child_id)
                    click.echo(f"        - {child_details.get('name', 'Unknown')} (ID: {child_short_id})")
    
    return True


def remove_person(person_id):
    """Removes a person from the family tree following the correct workflow."""
    data_repo, graph_repo = find_repos()
    if not data_repo or not graph_repo:
        click.secho("Error: Must be run from within a valid data repository with a 'family_graph' submodule.", fg='red')
        return False

    resolved_person_id = _resolve_person_id_input(data_repo, person_id, "person to remove")
    if not resolved_person_id:
        return False

    person_details = _get_person_name_by_id(data_repo, resolved_person_id)
    person_name = person_details.get('name', resolved_person_id)

    # --- Dependency Check ---
    marriages, children = _find_dependent_commits(data_repo, graph_repo, resolved_person_id)

    if marriages or children:
        click.secho(f"Warning: Removing {person_name} will also affect the following:", fg='yellow')
        if marriages:
            click.echo("  - Removing marriages:")
            for marriage_commit, partner_id in marriages:
                partner_details = _get_person_name_by_id(data_repo, partner_id)
                click.echo(f"    - Marriage to {partner_details.get('name', partner_id)}")
        if children:
            click.echo("  - No parents for children:")
            for child_id in children:
                child_details = _get_person_name_by_id(data_repo, child_id)
                click.echo(f"    - {child_details.get('name', child_id)}")
        
        if not click.confirm("Are you sure you want to proceed?"):
            click.echo("Operation aborted.")
            return False

    # Follow the correct workflow:
    # 1. If there are marriages, reparent children to root first
    # 2. Delete marriage commits
    # 3. Delete person commit
    # 4. Remove YAML file
    
    original_cwd = os.getcwd()
    os.chdir(graph_repo.working_dir)
    
    try:
        # Step 1: Reparent children to root if there are marriages with children
        if marriages and children:
            graph_root_commit = graph_repo.tags['GRAPH_ROOT'].commit
            if not _reparent_children_to_root(graph_repo, children, graph_root_commit):
                click.secho("Error: Failed to reparent children.", fg='red')
                return False

        # Step 2: Remove marriage commits
        for marriage_commit, _ in marriages:
            if not remove_commit_from_graph(marriage_commit.hexsha, graph_repo):
                click.secho("Error: Failed to remove marriage commit.", fg='red')
                return False

        # Step 3: Remove person commit
        person_commit = _find_person_commit_by_id(graph_repo, resolved_person_id)
        if person_commit:
            if not remove_commit_from_graph(person_commit.hexsha, graph_repo):
                click.secho("Error: Failed to remove person commit.", fg='red')
                return False

        click.echo("Graph operations completed successfully.")
        
    except Exception as e:
        click.secho(f"Error during graph operations: {e}", fg='red')
        return False
    finally:
        os.chdir(original_cwd)

    # Step 4: Remove YAML file after all graph operations are complete
    if not _delete_person_data(data_repo, resolved_person_id):
        click.secho("Error: Failed to delete person data file. The graph has been modified but data is inconsistent.", fg='red')
        return False

    # --- Final Commit ---
    data_repo.git.add('family_graph')
    data_repo.index.commit(f"feat: Remove person '{person_name}' ({_get_short_id(resolved_person_id)})")
    click.secho(f"Successfully removed {person_name}.", fg='green')
    return True


def _find_dependent_commits(data_repo, graph_repo, person_id):
    """Finds marriage and children commits dependent on a person."""
    marriages = []
    children = []
    
    # Find marriages
    for tag in graph_repo.tags:
        if tag.name.startswith("marriage_"):
            parts = tag.name.split('_')
            if len(parts) == 3:
                id1_short, id2_short = parts[1], parts[2]
                if person_id.startswith(id1_short):
                    partner_id = _get_full_id_from_short(graph_repo, id2_short)
                    marriages.append((tag.commit, partner_id))
                elif person_id.startswith(id2_short):
                    partner_id = _get_full_id_from_short(graph_repo, id1_short)
                    marriages.append((tag.commit, partner_id))

    # Find children
    _, children_map = _get_relationships(graph_repo, _get_all_people(data_repo))
    if person_id in children_map:
        children.extend(children_map[person_id])

    return marriages, children


def _get_full_id_from_short(graph_repo, short_id):
    """Helper to get a full person ID from a short ID by checking tags."""
    for tag in graph_repo.tags:
        if tag.name == short_id:
            # This assumes the tag name is the short_id of a person
            # We need to find the person file to get the full ID
            people_dir = Path(graph_repo.working_dir).parent / 'people'
            for person_file in people_dir.glob(f"{short_id}*.yml"):
                with open(person_file, 'r', encoding='utf-8') as f:
                    person_data = yaml.safe_load(f)
                    return person_data.get('id')
    return short_id # Fallback

def _get_short_id(full_id):
    """Returns the first 8 characters of a full ID."""
    if full_id:
        return full_id[:8]
    return 'N/A'

def _delete_person_data(data_repo, person_id):
    """Deletes the person's YAML file and commits the change."""
    short_id = _get_short_id(person_id)
    person_file_path = None
    for f in (Path(data_repo.working_dir) / 'people').glob(f"{short_id}*.yml"):
        person_file_path = f
        break
    
    if not person_file_path or not person_file_path.exists():
        click.secho(f"Warning: Could not find person file for ID {short_id}. It may have been already deleted.", fg='yellow')
        return True

    person_details = _get_person_name_by_id(data_repo, person_id)
    person_name = person_details.get('name', person_id)
    
    try:
        data_repo.index.remove([str(person_file_path)], working_tree=True)
        data_repo.index.commit(f"feat: Remove data for person '{person_name}' ({_get_short_id(person_id)})")
        click.echo(f"Removed person file: {person_file_path.name}")
        return True
    except Exception as e:
        click.secho(f"Error removing person file: {e}", fg='red')
        return False


def _rewrite_history_for_removal(graph_repo, person_id, marriages, children):
    """Rewrites the graph history to remove a person and their dependent commits."""
    original_cwd = os.getcwd()
    os.chdir(graph_repo.working_dir)

    try:
        # Get data_repo for passing to helper functions
        data_repo, _ = find_repos()
        
        # 1. Reparent children
        if children:
            graph_root_commit = graph_repo.tags['GRAPH_ROOT'].commit
            if not _reparent_children(graph_repo, children, graph_root_commit):
                return False

        # 2. Remove commits using the new helper function
        person_commit = _find_person_commit_by_id(graph_repo, person_id)
        if person_commit:
            if not remove_commit_from_graph(person_commit.hexsha, graph_repo):
                return False
        
        for marriage_commit, _ in marriages:
            if not remove_commit_from_graph(marriage_commit.hexsha, graph_repo):
                return False

        click.echo("Graph history rewrite completed successfully.")
        return True

    except (subprocess.CalledProcessError, git.GitCommandError) as e:
        click.secho(f"Error during history rewrite: {e}", fg='red')
        return False
    finally:
        os.chdir(original_cwd)


def _reparent_children_to_root(graph_repo, children, root_commit):
    """Reparents multiple children commits to the graph root."""
    try:
        # Process each child individually
        for child_id in children:
            child_commit = _find_person_commit_by_id(graph_repo, child_id)
            if child_commit:
                click.echo(f"Reparenting child {_get_short_id(child_id)} to root {_get_short_id(root_commit.hexsha)}")
                
                # Use git replace --graft to reparent the child to root
                subprocess.run([
                    "git", "replace", "--graft", child_commit.hexsha, root_commit.hexsha
                ], check=True, cwd=graph_repo.working_dir)
            else:
                click.secho(f"Warning: Could not find commit for child {_get_short_id(child_id)}", fg='yellow')
        
        # Make all reparenting operations permanent with a single git filter-repo call
        click.echo("Making reparenting permanent with git filter-repo...")
        result = subprocess.run(['git', 'filter-repo', '--replace-refs', 'delete-no-add', '--force'], 
                              cwd=graph_repo.working_dir, 
                              capture_output=True, text=True)
        
        if result.returncode != 0:
            click.secho(f"Error running git filter-repo: {result.stderr}", fg='red')
            return False
            
        click.echo(f"Successfully reparented {len(children)} children to root.")
        return True
        
    except Exception as e:
        click.secho(f"Error reparenting children: {e}", fg='red')
        return False

def _find_person_commit_by_id(graph_repo, person_id):
    """Find the commit that added a specific person using the tag."""
    try:
        # Get the short ID and look for the corresponding tag
        short_id = _get_short_id(person_id)
        tag = graph_repo.tags[short_id]
        return tag.commit
    except (KeyError, IndexError) as e:
        click.secho(f"Error finding person commit for {person_id}: tag '{_get_short_id(person_id)}' not found", fg='red')
        return None
    except Exception as e:
        click.secho(f"Error finding person commit: {e}", fg='red')
        return None


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

    nodes = _get_all_people(data_repo)
    parents_map, _ = _get_relationships(graph_repo, nodes)

    father_ancestors = _get_ancestors(resolved_father_id, parents_map)
    mother_ancestors = _get_ancestors(resolved_mother_id, parents_map)
    
    all_ancestors = father_ancestors.union(mother_ancestors)
    all_ancestors.add(resolved_father_id)
    all_ancestors.add(resolved_mother_id)

    if resolved_child_id in all_ancestors:
        print("Error: A person cannot be an ancestor of their own parents.")
        return False

    if _find_marriage_commit(graph_repo, resolved_child_id, resolved_father_id) or \
       _find_marriage_commit(graph_repo, resolved_child_id, resolved_mother_id):
        print("Error: A person cannot be a child of their partner.")
        return False

    # Check if the child is already a child of other parents
    if resolved_child_id in parents_map:
        child_details = _get_person_name_by_id(data_repo, resolved_child_id)
        current_parents = parents_map[resolved_child_id]
        parent_names = [_get_person_name_by_id(data_repo, p) for p in current_parents]
        parent_names_str = " and ".join([p['name'] for p in parent_names])
        if not click.confirm(f"{child_details['name']} is already a child of {parent_names_str}. Do you want to move them to the new parents?"):
            print("Operation aborted by user.")
            return False

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
        father_name = click.style(f"{father_details['first_name']} {father_details['last_name']}", fg='yellow', bold=True)
        mother_name = click.style(f"{mother_details['first_name']} {mother_details['last_name']}", fg='yellow', bold=True)
        print(f"Marriage between {father_name} ({resolved_father_id}) and {mother_name} ({resolved_mother_id}) not found.")
        if click.confirm(f"Do you want to create a marriage between {father_name} and {mother_name} now?"):
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

    # 3. Rewrite history to make the child a child of the marriage using the new helper function.
    if not change_commit_parent(child_commit.hexsha, marriage_commit.hexsha):
        return False

    print(f"Successfully added {resolved_child_id} as a child of {resolved_father_id} and {resolved_mother_id}.")

    # Commit submodule update to data repo
    data_repo.git.add('family_graph')
    data_repo.index.commit(f"feat: Add child {resolved_child_id} to {resolved_father_id} and {resolved_mother_id}")
    print("Committed child relationship to data repository.")

    return True

def run_report():
    """Provides a report on the health and statistics of the family tree data."""
    data_repo, graph_repo = find_repos()
    if not data_repo or not graph_repo:
        print("Error: Must be run from within a valid data repository with a 'family_graph' submodule.")
        return

    print("Running report...")
    print("Checking for cycles in the family graph...")
    
    nodes = _get_all_people(data_repo)
    edges = _get_edges(graph_repo, nodes)
    
    cycle = _find_cycle_in_graph(nodes, edges)

    if cycle:
        print("\n--- Cycle Detected! ---")
        print("The following people form a cycle in the family tree, which is not allowed:")
        node_map = {node['id']: node for node in nodes}
        for i, node_id in enumerate(cycle):
            person = node_map.get(node_id)
            print(f"  {i+1}. {person.get('name', 'Unknown')} (ID: {node_id[:8]})")
        print("\nThis is likely due to data corruption. You may need to manually correct the relationships.")
    else:
        print("No cycles found. The graph structure is valid.")

    # Future reports can be added here.

def _find_cycle_in_graph(nodes, edges):
    """Finds a cycle in the graph using DFS."""
    adj_list = {}
    for edge in edges:
        if edge['type'] == 'child':
            parent_id = edge['from']
            child_id = edge['to']
            if parent_id not in adj_list:
                adj_list[parent_id] = []
            adj_list[parent_id].append(child_id)

    white_set = {node['id'] for node in nodes}
    gray_set = set()
    black_set = set()
    recursion_path = []

    for node_id in list(white_set):
        if node_id in white_set:
            cycle = _dfs_cycle_check(node_id, adj_list, white_set, gray_set, black_set, recursion_path)
            if cycle:
                return cycle
    return None

def _dfs_cycle_check(node_id, adj_list, white_set, gray_set, black_set, path):
    white_set.remove(node_id)
    gray_set.add(node_id)
    path.append(node_id)

    for neighbor_id in adj_list.get(node_id, []):
        if neighbor_id in gray_set:
            # Cycle detected
            cycle_start_index = path.index(neighbor_id)
            return path[cycle_start_index:]
        if neighbor_id in white_set:
            cycle = _dfs_cycle_check(neighbor_id, adj_list, white_set, gray_set, black_set, path)
            if cycle:
                return cycle

    path.pop()
    gray_set.remove(node_id)
    black_set.add(node_id)
    return None

def _calculate_generations(nodes, edges):

    node_map = {node['id']: node for node in nodes}

    # Initial setup: find roots (those who are not children) and set their generation to 0.
    child_ids = set(edge['to'] for edge in edges if edge['type'] == 'child')
    for node in nodes:
        node['generation'] = 0 if node['id'] not in child_ids else -1

    # Iteratively propagate generations until no more changes are made
    changed_in_pass = True
    pass_count = 0
    max_passes = len(nodes) * 2 # A generous limit to prevent infinite loops
    
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

def _get_edges(graph_repo, nodes):
    """Extracts all partner and child edges from the graph repository."""
    edges = []
    
    all_tags = graph_repo.tags
    marriage_tags = [tag for tag in all_tags if tag.name.startswith("marriage_")]
    marriage_commit_to_tag = {tag.commit.hexsha: tag for tag in marriage_tags}

    # Find partner edges from marriage tags
    for tag in marriage_tags:
        parts = tag.name.split('_')
        if len(parts) == 3:
            id1_short = parts[1]
            id2_short = parts[2]
            id1_full = next((node['id'] for node in nodes if node['id'].startswith(id1_short)), None)
            id2_full = next((node['id'] for node in nodes if node['id'].startswith(id2_short)), None)
            if id1_full and id2_full:
                edges.append({"from": id1_full, "to": id2_full, "type": "partner"})

    # Find child edges from person tags
    person_tags = [tag for tag in all_tags if not tag.name.startswith("marriage_") and tag.name != "GRAPH_ROOT"]
    for tag in person_tags:
        child_commit = tag.commit
        child_id_short = tag.name
        child_id_full = next((node['id'] for node in nodes if node['id'].startswith(child_id_short)), None)

        if child_id_full and child_commit.parents:
            for parent_commit in child_commit.parents:
                if parent_commit.hexsha in marriage_commit_to_tag:
                    marriage_tag = marriage_commit_to_tag[parent_commit.hexsha]
                    parts = marriage_tag.name.split('_')
                    if len(parts) == 3:
                        parent1_short = parts[1]
                        parent2_short = parts[2]
                        parent1_full = next((node['id'] for node in nodes if node['id'].startswith(parent1_short)), None)
                        parent2_full = next((node['id'] for node in nodes if node['id'].startswith(parent2_short)), None)
                        if parent1_full and parent2_full:
                            edges.append({"from": parent1_full, "to": child_id_full, "type": "child"})
                            edges.append({"from": parent2_full, "to": child_id_full, "type": "child"})

    return edges


def change_commit_parent(target_commit_sha, new_parent_sha):
    """
    Changes the parent of a target commit to a new parent commit using git replace + git filter-repo.
    This preserves all tags and maintains child relationships.
    
    Args:
        target_commit_sha (str): The SHA of the commit whose parent should be changed
        new_parent_sha (str): The SHA of the new parent commit
        
    Returns:
        bool: True if successful, False if validation fails or operation fails
        
    Raises:
        ValueError: If either commit SHA doesn't exist
    """
    data_repo, graph_repo = find_repos()
    if not data_repo or not graph_repo:
        click.secho("Error: Must be run from within a valid data repository with a 'family_graph' submodule.", fg='red')
        return False
    
    try:
        # 1. Validate that both commit SHAs exist in the graph repo
        try:
            target_commit = graph_repo.commit(target_commit_sha)
            click.echo(f"Found target commit: {target_commit.hexsha[:8]} - {target_commit.message.strip()}")
        except (git.BadName, git.BadObject):
            click.secho(f"Error: Target commit SHA '{target_commit_sha}' does not exist in the graph repository.", fg='red')
            return False
        
        try:
            new_parent_commit = graph_repo.commit(new_parent_sha)
            click.echo(f"Found new parent commit: {new_parent_commit.hexsha[:8]} - {new_parent_commit.message.strip()}")
        except (git.BadName, git.BadObject):
            click.secho(f"Error: New parent commit SHA '{new_parent_sha}' does not exist in the graph repository.", fg='red')
            return False
        
        # 2. Check if target commit would create a cycle (new parent is descendant of target)
        try:
            if graph_repo.is_ancestor(target_commit, new_parent_commit):
                click.secho(f"Error: Cannot set '{new_parent_sha[:8]}' as parent of '{target_commit_sha[:8]}' - this would create a cycle.", fg='red')
                return False
        except git.GitCommandError:
            # If we can't determine ancestry, proceed with caution
            click.secho("Warning: Could not verify ancestry relationship. Proceeding with caution.", fg='yellow')
        
        # 3. Show current parent information
        current_parents = target_commit.parents
        if current_parents:
            click.echo(f"Current parent(s) of {target_commit_sha[:8]}:")
            for i, parent in enumerate(current_parents):
                click.echo(f"  {i+1}. {parent.hexsha[:8]} - {parent.message.strip()}")
        else:
            click.echo(f"Target commit {target_commit_sha[:8]} is currently a root commit (no parents)")
        
        # 4. Perform the parent change using git replace + git filter-repo
        original_cwd = os.getcwd()
        os.chdir(graph_repo.working_dir)
        
        # Save remote URLs before git filter-repo operation
        saved_remotes = {}
        try:
            for remote in graph_repo.remotes:
                saved_remotes[remote.name] = list(remote.urls)
        except Exception:
            # If we can't read remotes, continue without saving
            pass
        
        try:
            # Step 1: Create a replacement using git replace --graft
            click.echo(f"Creating replacement: {target_commit_sha[:8]} -> {new_parent_sha[:8]}")
            subprocess.run([
                "git", "replace", "--graft", target_commit.hexsha, new_parent_commit.hexsha
            ], check=True, cwd=graph_repo.working_dir)
            
            # Step 2: Verify the replacement (optional, for debugging)
            click.echo("Verifying replacement...")
            result = subprocess.run([
                "git", "log", "--graph", "--oneline", "--decorate", "-n", "10"
            ], capture_output=True, text=True, cwd=graph_repo.working_dir)
            
            # Step 3: Make the replacement permanent using git filter-repo
            click.echo("Making replacement permanent with git filter-repo...")
            
            # Clean up any previous git filter-repo state to avoid interactive prompts
            filter_repo_dir = os.path.join(graph_repo.working_dir, '.git', 'filter-repo')
            if os.path.exists(filter_repo_dir):
                import shutil
                shutil.rmtree(filter_repo_dir)
                click.echo("Cleaned up previous git filter-repo state")
            
            subprocess.run([
                "git", "filter-repo", "--replace-refs", "delete-no-add", "--force"
            ], check=True, cwd=graph_repo.working_dir)
            
            # Step 4: Restore remote URLs if they were removed
            for remote_name, urls in saved_remotes.items():
                try:
                    # Check if remote still exists
                    current_remotes = [r.name for r in graph_repo.remotes]
                    if remote_name not in current_remotes:
                        # Remote was removed, recreate it
                        if urls:
                            graph_repo.create_remote(remote_name, urls[0])
                            click.echo(f"Restored remote '{remote_name}' with URL: {urls[0]}")
                except Exception as e:
                    click.secho(f"Warning: Could not restore remote '{remote_name}': {e}", fg='yellow')
            
            click.secho(f"Successfully changed parent of commit '{target_commit_sha[:8]}' to '{new_parent_sha[:8]}'.", fg='green')
            
            # 5. Commit the submodule update to the data repo
            try:
                data_repo.git.add('family_graph')
                if data_repo.is_dirty():
                    data_repo.index.commit(f"feat: Change parent of commit {target_commit_sha[:8]} to {new_parent_sha[:8]}")
                    click.echo("Committed graph changes to data repository.")
            except git.GitCommandError as e:
                click.secho(f"Warning: Could not commit submodule changes: {e}", fg='yellow')
            
            return True
            
        except subprocess.CalledProcessError as e:
            click.secho(f"Error during git operations: {e}", fg='red')
            # Try to clean up any partial git replace state
            try:
                subprocess.run([
                    "git", "replace", "-d", target_commit.hexsha
                ], cwd=graph_repo.working_dir, check=False)
            except:
                pass
            return False
        finally:
            os.chdir(original_cwd)
            
    except Exception as e:
        click.secho(f"Unexpected error: {e}", fg='red')
        return False


def unmarry(person1_id, person2_id):
    """Removes a marriage between two people if no children exist from this marriage."""
    data_repo, graph_repo = find_repos()
    if not data_repo or not graph_repo:
        click.secho("Error: Must be run from within a valid data repository with a 'family_graph' submodule.", fg='red')
        return False

    # Resolve person IDs
    resolved_person1_id = _resolve_person_id_input(data_repo, person1_id, "first person")
    if not resolved_person1_id:
        return False
    
    resolved_person2_id = _resolve_person_id_input(data_repo, person2_id, "second person")
    if not resolved_person2_id:
        return False

    # Find the marriage commit
    marriage_commit = _find_marriage_commit(graph_repo, resolved_person1_id, resolved_person2_id)
    if not marriage_commit:
        person1_details = _get_person_name_by_id(data_repo, resolved_person1_id)
        person2_details = _get_person_name_by_id(data_repo, resolved_person2_id)
        person1_name = person1_details.get('name', resolved_person1_id)
        person2_name = person2_details.get('name', resolved_person2_id)
        click.secho(f"Error: No marriage found between {person1_name} ({_get_short_id(resolved_person1_id)}) and {person2_name} ({_get_short_id(resolved_person2_id)}).", fg='red')
        return False

    # Check if this marriage has any children
    children_from_marriage = _find_children_from_marriage(graph_repo, data_repo, marriage_commit)
    if children_from_marriage:
        person1_details = _get_person_name_by_id(data_repo, resolved_person1_id)
        person2_details = _get_person_name_by_id(data_repo, resolved_person2_id)
        person1_name = person1_details.get('name', resolved_person1_id)
        person2_name = person2_details.get('name', resolved_person2_id)
        
        click.secho(f"Error: Cannot remove marriage between {person1_name} ({_get_short_id(resolved_person1_id)}) and {person2_name} ({_get_short_id(resolved_person2_id)}).", fg='red')
        click.secho("The following children exist from this marriage:", fg='red')
        for child_id in children_from_marriage:
            child_details = _get_person_name_by_id(data_repo, child_id)
            child_name = child_details.get('name', child_id)
            click.echo(f"  - {child_name} ({_get_short_id(child_id)})")
        click.secho("Please remove or transfer the children first before removing the marriage.", fg='red')
        return False

    # Remove the marriage commit
    marriage_sha = marriage_commit.hexsha
    success = remove_commit_from_graph(marriage_sha, graph_repo)
    
    if success:
        person1_details = _get_person_name_by_id(data_repo, resolved_person1_id)
        person2_details = _get_person_name_by_id(data_repo, resolved_person2_id)
        person1_name = person1_details.get('name', resolved_person1_id)
        person2_name = person2_details.get('name', resolved_person2_id)
        click.secho(f"Successfully removed marriage between {person1_name} ({_get_short_id(resolved_person1_id)}) and {person2_name} ({_get_short_id(resolved_person2_id)}).", fg='green')
        return True
    else:
        click.secho("Error: Failed to remove marriage commit.", fg='red')
        return False


def _find_children_from_marriage(graph_repo, data_repo, marriage_commit):
    """Finds all children that have the given marriage commit as a parent."""
    children = []
    
    # Get all people and their relationships
    all_people = _get_all_people(data_repo)
    
    # Find all person tags (children) that have this marriage commit as a parent
    all_tags = graph_repo.tags
    person_tags = [tag for tag in all_tags if not tag.name.startswith("marriage_") and tag.name != "GRAPH_ROOT"]
    
    for tag in person_tags:
        child_commit = tag.commit
        child_id_short = tag.name
        child_id_full = next((node['id'] for node in all_people if node['id'].startswith(child_id_short)), None)
        
        if child_id_full and child_commit.parents:
            for parent_commit in child_commit.parents:
                if parent_commit.hexsha == marriage_commit.hexsha:
                    children.append(child_id_full)
                    break
    
    return children
