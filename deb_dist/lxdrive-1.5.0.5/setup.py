#!/usr/bin/env python3
"""
Setup script for lX Drive
"""

from setuptools import setup, find_packages
from pathlib import Path

# Leer README
readme = Path("README.md").read_text(encoding="utf-8")

# Leer requirements
requirements = Path("requirements.txt").read_text(encoding="utf-8").splitlines()
requirements = [r.strip() for r in requirements if r.strip() and not r.startswith("#")]

setup(
    name="lxdrive",
    version="1.5.0.5",
    author="J. Suarez",
    author_email="",
    description="Cliente de sincronización multi-cuenta para Google Drive en Linux",
    long_description=readme,
    long_description_content_type="text/markdown",
    url="https://github.com/jhonyesg/GoogleDriveSyncLinuxgui",
    license="MIT",
    
    packages=find_packages(),
    include_package_data=True,

    data_files=[
        ('/usr/share/applications/', ['lxdrive.desktop']),
        ('/usr/share/icons/', ['lxdrive.png']),
    ],
    
    python_requires=">=3.10",
    install_requires=requirements,
    
    entry_points={
        "console_scripts": [
            "lxdrive=lxdrive.app:main",
            "lx-drive=lxdrive.app:main",
        ],
        "gui_scripts": [
            "lxdrive-gui=lxdrive.app:main",
        ],
    },
    
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: X11 Applications :: Qt",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Internet :: File Transfer Protocol (FTP)",
        "Topic :: System :: Archiving :: Backup",
        "Topic :: Utilities",
    ],
    
    keywords="google-drive cloud sync rclone backup linux deepin",
    
    project_urls={
        "Bug Reports": "https://github.com/jhonyesg/GoogleDriveSyncLinuxgui/issues",
        "Source": "https://github.com/jhonyesg/GoogleDriveSyncLinuxgui",
    },
)
