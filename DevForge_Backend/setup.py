"""Setup configuration for DevForge Backend package."""

from setuptools import find_packages, setup

setup(
    name="devforge-backend",
    version="0.1.0",
    description="DevForge Backend - FastAPI backend for AI-powered developer tools",
    packages=find_packages(),
    python_requires=">=3.11",
    install_requires=[
        # Core dependencies listed in requirements.txt
        # Install with: pip install -e .
    ],
)

