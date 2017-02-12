from setuptools import setup

setup(
    name='myusps',
    version='1.0.3',
    description='Python 3 API for My USPS, a way to track packages.',
    url='https://github.com/happyleavesaoc/python-myusps/',
    license='MIT',
    author='happyleaves',
    author_email='happyleaves.tfr@gmail.com',
    packages=['myusps'],
    install_requires=['lxml==3.7.1', 'python-dateutil==2.6.0', 'requests==2.12.4'],
    classifiers=[
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
    ]
)
