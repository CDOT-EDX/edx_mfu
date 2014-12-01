"""Setup for edx-mfu XBlock."""

import os
from setuptools import setup, find_packages


def package_data(pkg, root_list):
    """Generic function to find package_data for `pkg` under `root`."""
    data = []
    for root in root_list:
        for dirname, _, files in os.walk(os.path.join(pkg, root)):
            for fname in files:
                data.append(os.path.relpath(os.path.join(dirname, fname), pkg))

    return {pkg: data}

setup(
    name='edx-mfu',
    version='0.3.1',
    description='edx-mfu Multiple File Upload XBlock',
    license='Affero GNU General Public License v3 (GPLv3)',
    url="https://github.com/wastedelectrons/edx-sga",
    author="MITx",
    zip_safe=False,
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'XBlock',
    ],
    entry_points={
        'xblock.v1': [
            'edx_mfu = edx_mfu:MultipleFileUploadXBlock',
        ]
    },
    package_data=package_data("edx_mfu", ["static", "templates"]),
)
