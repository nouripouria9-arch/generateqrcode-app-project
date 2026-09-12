# Generate QR Code App

A desktop QR code generator built with Python and PySide6. The application converts valid web URLs into high-resolution, scannable QR codes through a graphical user interface.

## Overview

This project provides a practical desktop tool for generating QR codes from web addresses. It includes URL validation, QR code preview, recent URL history, clipboard support, browser launching, and image export.

## Features

- Generate QR codes from HTTP and HTTPS URLs
- High-resolution QR code generation with high error correction
- Desktop graphical interface built with PySide6
- Preview generated QR codes inside the application
- Save QR codes as PNG or JPEG images
- Copy URLs to the clipboard
- Open URLs in the default web browser
- Store and manage recent URL history
- Basic validation and user-friendly status messages
- Local application logging for technical errors

## Technologies

- Python 3.10+
- PySide6
- qrcode
- Pillow (through `qrcode[pil]`)

## Installation

Install the required packages:

```bash
pip install PySide6 "qrcode[pil]"
```

## Run

```bash
python generateqrcode-app.py
```

## Project Note

The original project code is included without changes to its program logic or implementation. The source file has been named `generateqrcode-app.py` as requested.

## Author

Pouria Nouri

Bachelor's Degree Student in Computer Engineering
