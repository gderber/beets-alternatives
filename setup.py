from setuptools import setup
import sys

setup(
    name='beets-alternatives',
    version='0.8.3-dev',
    description='beets plugin to manage multiple files',
    long_description=open('README.md').read(),
    author='Thomas Scholtes',
    author_email='thomas-scholtes@gmx.de',
    url='http://www.github.com/geigerzaehler/beets-alternatives',
    license='MIT',
    platforms='ALL',

    test_suite='test',

    packages=['beetsplug'],

    install_requires=(
        ['beets>=1.4.2',
         ] +
        (['futures'] if sys.version_info < (3, 0, 0) else [])
    ),

    classifiers=[
        'Topic :: Multimedia :: Sound/Audio',
        'Topic :: Multimedia :: Sound/Audio :: Players :: MP3',
        'License :: OSI Approved :: MIT License',
        'Environment :: Console',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ],
)
