import click
from . import main

@click.group()
def cli():
    """A CLI tool to manage family tree data using a dual-repo Git model."""
    pass

import os
from pathlib import Path

@cli.command('init')
@click.argument('root_path', type=click.Path())
@click.option('--force', is_flag=True, help='Overwrite the target directory if it exists.')
def init(root_path, force):
    """Initializes a new family tree project at the specified path."""
    target_path = Path(root_path)
    if target_path.exists() and os.listdir(target_path):
        if force:
            click.echo(f"--force flag set. Removing existing directory: {target_path}")
        else:
            if not click.confirm(f"Directory '{target_path}' is not empty. Do you want to remove it and start over?"):
                click.echo("Aborting.")
                return
    
    click.echo(f"Initializing new project at: {root_path}")
    success = main.initialize_project(root_path, force=True) # Pass force=True after confirmation
    if success:
        click.secho(f"Successfully initialized project!", fg='green')
    else:
        click.secho("Failed to initialize project.", fg='red')


@cli.command('add')
@click.option('-f', '--first-name', required=True, help='The person\'s first name.')
@click.option('-l', '--last-name', required=True, help='The person\'s last name.')
@click.option('-m', '--middle-name', help='The person\'s middle name.')
@click.option('-b', '--birth-date', help='Birth date in YYYY-MM-DD format.')
@click.option('-g', '--gender', help='The person\'s gender.')
@click.option('-n', '--nickname', help='The person\'s nickname.')
def add(first_name, last_name, middle_name, birth_date, gender, nickname):
    """Adds a new person to the family tree."""
    click.echo(f"Adding person: {first_name} {last_name}...")
    success = main.add_person(first_name, last_name, middle_name, birth_date, gender, nickname)
    if success:
        click.secho("Successfully added person!", fg='green')
    else:
        click.secho("Failed to add person.", fg='red')

if __name__ == '__main__':
    cli()