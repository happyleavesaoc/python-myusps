from setuptools import setup, find_packages

setup(
    name='myusps',
    version='1.3.2',
    description='Python 3 API for USPS Informed Delivery, a way to track packages and mailpieces.',
    url='https://github.com/happyleavesaoc/python-myusps/',
    license='MIT',
    author='happyleaves',
    author_email='happyleaves.tfr@gmail.com',
    packages=find_packages(),
    install_requires=['beautifulsoup4==4.6.0', 'python-dateutil==2.6.0', 'requests>=2.20.0', 'requests-cache==0.4.13', 'selenium==3.11.0'],
    classifiers=[
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
    ]
)
