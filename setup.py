#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

# Copyright (C) 2011-2014 riot <riot@c-base.org> and others.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os

from setuptools import setup


# TODO: rebuild the package finder using setuptools & pkg_resources

def include_readme():
    readme = open("README.md")
    include = readme.readlines(10)[2:10]
    readme.close()
    return "".join(include)


def is_package(path):
    return (
        os.path.isdir(path) and
        os.path.isfile(os.path.join(path, '__init__.py'))
    )


def find_packages(path, base=""):
    """ Find all packages in path """
    packages = {}
    for item in os.listdir(path):
        dir = os.path.join(path, item)
        if is_package(dir):
            if base:
                module_name = "%(base)s.%(item)s" % vars()
            else:
                module_name = item
            packages[module_name] = dir
            packages.update(find_packages(dir, module_name))
    return packages


packages = find_packages(".")
package_names = list(packages.keys())

print(package_names)

setup(name="matelight-jockey",
      version="0.0.1",
      description="A VJing tool for the Matelight",
      author="riot",
      author_email="riot@c-base.org",
      url="https://github.com/c-base/matelight-jockey",
      license="GNU General Public License v3",
      packages=package_names + ['assets'],
      package_dir=packages,
      package_data={'assets': ['assets/*']},
      scripts=[
          'matejockey.py',
      ],
      data_files=[
      ],

      long_description=include_readme(),
      dependency_links=['https://github.com/Hackerfleet/axon/archive/master.zip#egg=Axon-1.7.0',
                        'https://github.com/Hackerfleet/kamaelia/archive/master.zip#egg=Kamaelia-1.1.2.1',
      ],

      # These versions are not strictly checked, older ones may or may not work.
      install_requires=['Axon==1.7.0',
                        'Kamaelia==1.1.2.1',
      ]

)
