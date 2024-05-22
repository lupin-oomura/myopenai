from setuptools import setup, find_packages

setup(
    name='myfunc',
    version='0.2',
    packages=find_packages(),
    install_requires=[
        'openai',
        'python-dotenv',
        'requests',

        #音声認識で使用
        'pydub',
        'speechrecognition',
        'torch',
        'numpy',
        'pyaudio',
    ],
    url='https://github.com/lupin-oomura/myfunc.git',
    author='Shin Oomura',
    author_email='shin.oomura@gmail.com',
    description='A simple OpenAI function package',
)
