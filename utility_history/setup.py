from setuptools import setup, find_packages

setup(
    name="consolidated_utility",
    version="1.0.0",
    description="Consolidated Python Utility Package — unified toolkit for AI and data-driven projects",
    author="Engineering Team",
    packages=find_packages(),
    python_requires=">=3.9",
    install_requires=[
        "pymongo>=4.6.0",
        "psycopg2-binary>=2.9.9",
        "SQLAlchemy>=2.0.0",
        "python-dotenv>=1.0.0",
        "pydantic>=2.5.0",
        "pytest>=7.4.0",
        "pytest-asyncio>=0.23.0",
        "mongomock>=4.1.0",
        "freezegun>=1.4.0",
    ],
    extras_require={
        "dev": ["black", "isort", "mypy"],
    },
    classifiers=[
        "Programming Language :: Python :: 3.9",
        "Operating System :: OS Independent",
    ],
)
