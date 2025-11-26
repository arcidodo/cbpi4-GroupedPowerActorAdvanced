from setuptools import setup

# read the contents of your README file
from os import path
this_directory = path.abspath(path.dirname(__file__))
with open(path.join(this_directory, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(name='cbpi4-GroupedPowerActorAdvanced',
      version='0.1.0',
      description='CraftBeerPi4 Plugin to Group Actors',
      author='Arco Veenhuizen',
      author_email='info@veenhuizen.net',
      url='https://github.com/arcidodo/cbpi4-GroupedPowerActorAdvanced',
      include_package_data=True,
      package_data={
        # If any package contains *.txt or *.rst files, include them:
      '': ['*.txt', '*.rst', '*.yaml'],
      'cbpi4-GroupedPowerActorAdvanced': ['*','*.txt', '*.rst', '*.yaml']},
      packages=['cbpi4-GroupedPowerActorAdvanced'],
      long_description=long_description,
      long_description_content_type='text/markdown'
     )
