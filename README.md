# Family Tree Tool

A command-line tool for managing family tree data using Git repositories. It enables you to build, visualize, and maintain complex family relationships with simple file-based storage—no database required.

## Output Example

Curious what your family tree could look like? Check out this live sample: [family_data_sample](https://github.com/saleh-mehdikhani/family_data_sample) and explore the interactive visualization at [famtool.netlify.app](https://famtool.netlify.app/).

You can build a similar system for yourself—privately and securely—by storing your data in a private GitHub repository and deploying the visualization for free on platforms like Netlify. Your family history, always under your control and accessible anywhere, at zero cost.

## Project Idea

Imagine building and exploring your family tree—without ever touching a database. This tool leverages the power of files and Git to make your family history easy to manage, visualize, and share. Every detail is stored in simple YAML files, and every relationship is tracked through Git commits, so you get full transparency and revision control. No hidden data, no complex setup—just files you can version, backup, and move anywhere.

Two repositories work together: one for people metadata (YAML files), and one as a Git submodule for relationships. Each commit marks a new person or a marriage, making the evolution of your family tree visible and traceable. Add a person, and you add a file and a commit—no database required, just pure Git magic. This approach keeps your data portable, secure, and always under your control.

## Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/saleh-mehdikhani/fam-tool.git
   ```
2. Create a folder outside this project for your family tree data:
   ```bash
   mkdir ~/my-family-tree
   cd ~/my-family-tree
   ```
3. Set up a Python virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
4. Install the tool:
   ```bash
   pip install /path/to/family_tree_tool
   ```
5. Initialize your family tree data:
   ```bash
   fam init .
   ```

## Usage Example

- Add new people:
  ```bash
  fam add -f John -l Smith
  fam add -f Jane -l Doe
  fam marry -m "John Smith" -f "Jane Doe"
  fam add -f Child1 -l Smith --father "John Smith" --mother "Jane Doe"
  fam add -f Child2 -f Child3 -l Smith --father "John Smith" --mother "Jane Doe"
  ```
- Create two empty Github (or other providers) projects and set up remote and push changes:
  ```bash
  fam set-remote -d <remote-url-data-repo> -g <remote-url-graph-repo>
  fam push-remote
  ```

For more details, see the documentation and explore the sample output links above.
