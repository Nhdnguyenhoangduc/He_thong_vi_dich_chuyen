from setuptools import setup, find_packages

setup(
    name="micro-positioning-system",
    version="1.0.0",
    author="Nguyễn Hoàng Đức",
    author_email="23001599@usth.edu.vn",
    description="Vision-based closed-loop micro-positioning system for microfluidic chip alignment",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/<your-username>/micro-positioning-system",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.8",
    install_requires=[
        "opencv-python>=4.5.0",
        "numpy>=1.21.0",
        "pyserial>=3.5.0",
        "matplotlib>=3.4.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0",
            "pytest-cov>=4.0",
            "flake8>=5.0",
            "black>=22.0",
        ]
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Scientific/Engineering",
        "Topic :: Scientific/Engineering :: Image Processing",
    ],
)
