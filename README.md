# PDF Signer

This is a simple PDF signing application built with PyQt5. 
It simulates the process of printing, signing and the scanning a PDF document, which is still common in Germany as of 2024 :(

It allowes users to open PDF files, sign them with custom signatures, and save the signed PDFs as "screenshots of themselves", optionally in greyscale and slightly skewed (to simulate imperfect scanning).

## Features

- Quickly zoom to the disired area on the page.
- Add one or more signatures.
- Save the signed PDFs as a PDF that consists of only one image object.
- Manage multiple custom signatures.

## Getting Started

### Prerequisites

- Python 3.x
- PyQt5 library
- PyMuPDF (MuPDF) library
- at least one signature image (.png), ideally with transparent background

### Installation

#### Linux

1. Install Python: Use your distribution's package manager to install Python, e.g.
   ```bash
   apt install python3

2. Install PyQt5 and PyMuPDF:
   ```bash
   pip install PyQt5 PyMuPDF

3. Clone the repository:

   ```bash
   git clone https://github.com/yourusername/pdfSigner.git
   cd pdfSigner

4. Run the application:

   ```bash
   python pdf_signer_v2.py [path_to_pdf_file]

#### Windows

1. Install Python: Download and install Python from [here](https://www.python.org/downloads/).

2. Open Command Prompt as an administrator and install PyQt5 and PyMuPDF:

   ```cmd
   pip install PyQt5 PyMuPDF

4. Clone the repository:

   ```cmd
   git clone https://github.com/yourusername/pdfSigner.git
   cd pdfSigner

5. Run the application:

   ```cmd
   python pdf_signer_v2.py [path_to_pdf_file]

#### macOS (Not Tested)

1. Install Python: Download and install Python from [here](https://www.python.org/downloads/).

2. Open Terminal and install PyQt5 and PyMuPDF:

   ```
   pip install PyQt5 PyMuPDF

3. Clone the repository:

   ```
   git clone https://github.com/yourusername/pdfSigner.git
   cd pdfSigner

4. Run the application:

   ```
   python pdf_signer_v2.py [path_to_pdf_file]

### Contributing

Contributions are welcome! If you find any issues or have suggestions, please open an issue or create a pull request.

### License

This project is licensed under the GNU General Public License v3.0 - see the LICENSE file for details.
