from setuptools import setup, find_packages

with open('README.md', encoding='utf-8') as f:
    long_description = '\n' + f.read()

setup(
    name='symbian_sports_tracker',
    version='0.9.5',
    install_requires=['lxml'],
    author='ekspla',
    description='Read-Symbian-SportsTracker-file',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/ekspla/Read-Symbian-SportsTracker-file',
    keywords='sports-tracker symbian nokia gps gpx',
    packages=find_packages(),
    include_package_data=True,
    license='LGPL',
    classifiers=[
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: GNU Library or Lesser General Public License (LGPL)',
        'Operating System :: OS Independent',
        'Development Status :: 5 - Production/Stable',
    ],
    entry_points = {
        'console_scripts': [
            'convert_nst_files_to_gpx=symbian_sports_tracker.convert_nst_files_to_gpx:main',
            'convert_nst_rec_to_gpx=symbian_sports_tracker.convert_nst_rec_to_gpx:main',
        ]
    },
    python_requires='>=3.6',
)