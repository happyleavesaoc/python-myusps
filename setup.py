from setuptools import setup, find_packages

setup(
    name='myusps',
    version='1.3.0',
    description='Python 3 API for USPS Informed Delivery, a way to track packages and mailpieces.',
    url='https://github.com/happyleavesaoc/python-myusps/',
    license='MIT',
    author='happyleaves',
    author_email='happyleaves.tfr@gmail.com',
    packages=find_packages(),
    install_requires=['bs4==0.0.1', 'python-dateutil==2.6.0', 'requests==2.12.4', 'requests-cache==0.4.13', 'selenium==2.53.6'],
    classifiers=[
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
    ]
)
