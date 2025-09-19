import os
from pathlib import Path

import click
from . import main

@click.group()
def cli():
    """A CLI tool to manage family tree data using a dual-repo Git model."""
    pass

@cli.command('init')
@click.argument('root_path', type=click.Path())
def init(root_path):
    """Initializes a new family tree project at the specified path."""
    target_path = Path(root_path)
    if target_path.exists():
        if os.listdir(target_path):
            click.secho(f"Warning: Target directory '{root_path}' is not empty.", fg='yellow')
    else:
        try:
            target_path.mkdir(parents=True, exist_ok=False)
        except OSError as e:
            click.secho(f"Error creating directory '{root_path}': {e}", fg='red')
            return

    click.echo(f"Initializing new project at: {root_path}")
    success = main.initialize_project(root_path)
    if success:
        click.secho("Successfully initialized project!", fg='green')
    else:
        click.secho("Failed to initialize project.", fg='red')


@cli.command('add')
@click.option('-f', '--first-name', required=True, help='The person\'s first name.')
@click.option('-l', '--last-name', required=True, help='The person\'s last name.')
@click.option('-mn', '--middle-name', help='The person\'s middle name.')
@click.option('-b', '--birth-date', help='Birth date in YYYY-MM-DD format.')
@click.option('-g', '--gender', help='The person\'s gender.')
@click.option('-n', '--nickname', help='The person\'s nickname.')
@click.option('--father', 'father_id', help='The father\'s person ID.')
@click.option('--mother', 'mother_id', help='The mother\'s person ID.')
def add(first_name, last_name, middle_name, birth_date, gender, nickname, father_id, mother_id):
    """Adds a new person to the family tree."""
    click.echo(f"Adding person: {first_name} {last_name}...")
    success = main.add_person(first_name, last_name, middle_name, birth_date, gender, nickname, father_id, mother_id)
    if success:
        click.secho("Successfully added person!", fg='green')
    else:
        click.secho("Failed to add person.", fg='red')


@cli.command('marry')
@click.option('-m', '--male', 'male', required=True, help="The male's person ID or name.")
@click.option('-f', '--female', 'female', required=True, help="The female's person ID or name.")
def marry(male, female):
    """Creates a marriage event between two people."""
    click.echo(f"Marrying {male} and {female}...")
    success = main.marry(male, female)
    if success:
        click.secho("Successfully created marriage event!", fg='green')
    else:
        click.secho("Failed to create marriage event.", fg='red')

@cli.command('child')
@click.argument('child_id')
@click.option('-f', '--father', 'father_id', required=True, help="The father's person ID.")
@click.option('-m', '--mother', 'mother_id', required=True, help="The mother's person ID.")
def child(child_id, father_id, mother_id):
    """Adds a child to a couple."""
    click.echo(f"Adding {child_id} as a child of {father_id} and {mother_id}...")
    success = main.add_child(father_id, mother_id, child_id)
    if success:
        click.secho("Successfully added child!", fg='green')
    else:
        click.secho("Failed to add child.", fg='red')

@cli.command('export')
@click.option('--output', default='family_tree.json', help='The output file name.')
def export(output):
    """Exports the family tree to a JSON file."""
    click.echo(f"Exporting family tree to {output}...")
    success = main.export_to_json(output)
    if success:
        click.secho(f"Successfully exported family tree to {output}!", fg='green')
    else:
        click.secho("Failed to export family tree.", fg='red')

@cli.command('set-remote')
@click.option('-d', '--data', 'data_remote', required=True, help='The remote URL for the data repository.')
@click.option('-g', '--graph', 'graph_remote', required=True, help='The remote URL for the graph repository.')
def set_remote(data_remote, graph_remote):
    """Sets the remote URLs for the data and graph repositories."""
    click.echo(f"Setting remote for data repository to: {data_remote}")
    click.echo(f"Setting remote for graph repository to: {graph_remote}")
    success = main.initialize_remotes(data_remote, graph_remote)
    if success:
        click.secho("Successfully set remote URLs!", fg='green')
    else:
        click.secho("Failed to set remote URLs.", fg='red')

@cli.command('push-remote')
@click.option('-f', '--force', is_flag=True, help='Force push to the remote repository.')
def push_remote(force):
    """Pushes changes to the remote repositories."""
    click.echo("Pushing changes to remote repositories...")
    success = main.push_to_remote(force)
    if success:
        click.secho("Successfully pushed changes!", fg='green')
    else:
        click.secho("Failed to push changes.", fg='red')

@cli.command('graph')
def graph():
    """Displays the Git graph log of the graph repository."""
    click.echo("Displaying graph repository log...")
    success = main.display_graph_log()
    if success:
        click.secho("Graph log displayed successfully!", fg='green')
    else:
        click.secho("Failed to display graph log.", fg='red')

@cli.command('find')
@click.argument('name')
def find(name):
    """Finds people by name and lists their full name and short ID."""
    click.echo(f"Searching for people named '{name}'...")
    success = main.find_person_by_name(name)
    if success:
        click.secho("Search complete.", fg='green')
    else:
        click.secho("No people found or an error occurred.", fg='red')


@cli.command('list')
@click.argument('name', required=False)
@click.option('-c', '--children', is_flag=True, help='List the children of the specified person.')
@click.option('-p', '--parents', is_flag=True, help='List the parents of the specified person.')
def list_people(name, children, parents):
    """Lists all people, or people matching a given name, with options to show children and parents."""
    main.list_people(name, children, parents)


@cli.command('report')
def report():
    """Provides a report on the health and statistics of the family tree data."""
    main.run_report()


@cli.command('remove')
@click.argument('person_id')
def remove(person_id):
    """Removes a person from the family tree."""
    main.remove_person(person_id)


if __name__ == '__main__':
    cli()
