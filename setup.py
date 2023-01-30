import setuptools

# read the contents of your README file
from os import path

this_directory = path.abspath(path.dirname(__file__))
with open(path.join(this_directory, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setuptools.setup(
    name='osm_annotation',
    version="0.1.4",
    description='An easy-to-use Python package that annotate location data with semantic labels from OpenStreetMap',
    url='https://github.com/rexli999/location_annotation_with_openstreetmap',
    long_description=long_description,
    long_description_content_type="text/markdown",
    author='Jixin Li',
    author_email='li.jix@northeastern.edu',
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    packages=setuptools.find_packages(),
    package_data={'osm_annotation': ['label_map/*.csv']},
    include_package_data=True,
    python_requires='>=3.7'
)
