from setuptools import setup, find_packages

from lxdrive import __version__, __app_name__

setup(
    name=__app_name__.lower().replace("-", "_"),
    version=__version__,
    description="Cloud sync manager for Linux Mint using rclone",
    author="lX_Drive Team",
    packages=find_packages(),
    install_requires=[
        "PyGObject>=3.48.0",
        "pyxdg>=0.28",
    ],
    entry_points={
        "console_scripts": [
            "lxdrive=lxdrive.main:main",
        ],
    },
    package_data={
        "lxdrive": ["../data/icons/*.svg"],
    },
    include_package_data=True,
    python_requires=">=3.10",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: X11 Applications :: GTK",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: System :: Archiving :: Backup",
        "Topic :: Utilities",
    ],
)
