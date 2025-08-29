from setuptools import setup, find_packages

setup(
    name='fam-tool',
    version='0.1.0',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'Click',
        'PyYAML',
        'GitPython',
    ],
    entry_points={
        'console_scripts': [
            'fam = family_tree_tool.cli:cli',
        ],
    },
)
