from setuptools import setup, find_packages

setup(
    name='myopenai',
    version='0.5.11',
    packages=find_packages(),
    install_requires=[
        'openai',
        'python-dotenv',
        'requests',
    ],
    url='https://github.com/lupin-oomura/myopenai.git',
    author='Shin Oomura',
    author_email='shin.oomura@gmail.com',
    description='A simple OpenAI function package',
)
