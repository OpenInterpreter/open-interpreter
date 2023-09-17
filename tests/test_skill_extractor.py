import interpreter
interpreter.auto_run = True
interpreter.model = "gpt-4"
interpreter.temperature = 0


skill_obj ={
  "skill_name": "extract_pdf_pages",
  "skill_description": "This skill extracts a specified range of pages from a PDF file and saves them as a new PDF file. It uses the PyPDF2 library to read the original PDF, extract the desired pages, and write them to a new PDF.",
  "skill_dependencies": [
    "PyPDF2"
  ],
  "skill_parameters": [
    {
      "param_name": "pdf_path",
      "param_type": "string",
      "param_description": "The path to the original PDF file.",
      "param_required": True,
      "param_default": None
    },
    {
      "param_name": "start_page",
      "param_type": "integer",
      "param_description": "The first page of the range to be extracted. Pages are 1-indexed.",
      "param_required": True,
      "param_default": None
    },
    {
      "param_name": "end_page",
      "param_type": "integer",
      "param_description": "The last page of the range to be extracted. This page is included in the extracted section.",
      "param_required": True,
      "param_default": None
    },
    {
      "param_name": "output_pdf_path",
      "param_type": "string",
      "param_description": "The path where the new PDF file will be saved.",
      "param_required": True,
      "param_default": None
    }
  ],
  "skill_usage_example": "extract_pdf_pages('/Users/gongjunmin/Downloads/creator.pdf', 2, 5, '/Users/gongjunmin/Downloads/extracted_pages.pdf')",
  "skill_return": {
    "return_name": "output_pdf_path",
    "return_type": "string",
    "return_description": "The path where the new PDF file has been saved."
  },
  "skill_tags": [
    "pdf",
    "extract",
    "pages",
    "PyPDF2"
  ],
  "skill_program_language": "python",
  "skill_code": "from PyPDF2 import PdfReader, PdfWriter\n\ndef extract_pdf_pages(pdf_path, start_page, end_page, output_pdf_path):\n    # Open the PDF file\n    pdf = PdfReader(pdf_path)\n\n    # Create a PdfWriter object\n    writer = PdfWriter()\n\n    # Add the specified pages to the writer\n    for i in range(start_page - 1, end_page):\n        writer.add_page(pdf.pages[i])\n\n    # Write the pages to a new PDF file\n    with open(output_pdf_path, 'wb') as output_pdf:\n        writer.write(output_pdf)\n\n    return output_pdf_path",
  "skill_metadata": {
    "created_at": "2023-09-17 19:57:56",
    "author": "gongjunmin",
    "updated_at": "2023-09-17 19:57:56",
    "usage_count": 1
  },
  "conversation_history": [
    {
      "role": "user",
      "content": "help me write a script that can extracts a specified section from a PDF file and saves it as a new PDF"
    },
    {
      "role": "assistant",
      "content": "Sure, I can help with that. Here's a plan:\n\n1. Install necessary packages. We will use PyPDF2, a Python library, to manipulate PDF files.\n2. Ask the user for the name of the PDF file.\n3. Ask the user for the page numbers of the section they want to extract.\n4. Open the PDF file and extract the specified section.\n5. Save the extracted section as a new PDF file.\n6. Confirm the new PDF file has been created.\n\nLet's start with step 1, installing the necessary packages. If you have already installed PyPDF2, you can skip this step."
    },
    {
      "role": "user",
      "content": "skip"
    },
    {
      "role": "assistant",
      "content": "Great, let's move on to the next step. \n\nCould you please provide the name of the PDF file you want to extract a section from?"
    },
    {
      "role": "user",
      "content": "please extract /Users/gongjunmin/Downloads/creator.pdf 2-5 pages"
    },
    {
      "role": "assistant",
      "content": "Alright, we will extract pages 2 to 5 from the PDF file at `/Users/gongjunmin/Downloads/creator.pdf`.\n\nLet's proceed with the following steps:\n\n1. Open the PDF file using PyPDF2.\n2. Extract pages 2 to 5.\n3. Save the extracted pages as a new PDF file.\n\nLet's start with step 1, opening the PDF file.",
      "function_call": {
        "name": "run_code",
        "arguments": "{\n  \"language\": \"python\",\n  \"code\": \"from PyPDF2 import PdfFileReader\\n\\n# Open the PDF file\\npdf_path = '/Users/gongjunmin/Downloads/creator.pdf'\\npdf = PdfFileReader(pdf_path)\\n\\n# Check the number of pages in the PDF\\nnum_pages = pdf.getNumPages()\\nnum_pages\"\n}",
        "parsed_arguments": {
          "language": "python",
          "code": "from PyPDF2 import PdfFileReader\n\n# Open the PDF file\npdf_path = '/Users/gongjunmin/Downloads/creator.pdf'\npdf = PdfFileReader(pdf_path)\n\n# Check the number of pages in the PDF\nnum_pages = pdf.getNumPages()\nnum_pages"
        }
      }
    },
    {
      "role": "function",
      "name": "run_code",
      "content": "File \"<stdin>\", line 4, in <module>\nModuleNotFoundError: No module named 'PyPDF2'"
    },
    {
      "role": "assistant",
      "content": "It seems like the PyPDF2 module is not installed on your machine. I apologize for the confusion earlier. Let's install it now.",
      "function_call": {
        "name": "run_code",
        "arguments": "{\n  \"language\": \"python\",\n  \"code\": \"import os\\n\\n# Install PyPDF2\\nos.system('pip install PyPDF2')\"\n}",
        "parsed_arguments": {
          "language": "python",
          "code": "import os\n\n# Install PyPDF2\nos.system('pip install PyPDF2')"
        }
      }
    },
    {
      "role": "function",
      "name": "run_code",
      "content": "Collecting PyPDF2\nUsing cached pypdf2-3.0.1-py3-none-any.whl (232 kB)\nInstalling collected packages: PyPDF2\nSuccessfully installed PyPDF2-3.0.1\n0"
    },
    {
      "role": "assistant",
      "content": "The PyPDF2 module has been successfully installed. Let's try opening the PDF file again.",
      "function_call": {
        "name": "run_code",
        "arguments": "{\n  \"language\": \"python\",\n  \"code\": \"from PyPDF2 import PdfFileReader\\n\\n# Open the PDF file\\npdf_path = '/Users/gongjunmin/Downloads/creator.pdf'\\npdf = PdfFileReader(pdf_path)\\n\\n# Check the number of pages in the PDF\\nnum_pages = pdf.getNumPages()\\nnum_pages\"\n}",
        "parsed_arguments": {
          "language": "python",
          "code": "from PyPDF2 import PdfFileReader\n\n# Open the PDF file\npdf_path = '/Users/gongjunmin/Downloads/creator.pdf'\npdf = PdfFileReader(pdf_path)\n\n# Check the number of pages in the PDF\nnum_pages = pdf.getNumPages()\nnum_pages"
        }
      }
    },
    {
      "role": "function",
      "name": "run_code",
      "content": "File \"<stdin>\", line 8, in <module>\nFile \"/Users/gongjunmin/miniconda3/envs/open_interpreter_dev/lib/python3.10/site-packages/PyPDF2/_reader.py\", line 1974, in __init__\ndeprecation_with_replacement(\"PdfFileReader\", \"PdfReader\", \"3.0.0\")\nFile \"/Users/gongjunmin/miniconda3/envs/open_interpreter_dev/lib/python3.10/site-packages/PyPDF2/_utils.py\", line 369, in deprecation_with_replacement\ndeprecation(DEPR_MSG_HAPPENED.format(old_name, removed_in, new_name))\nFile \"/Users/gongjunmin/miniconda3/envs/open_interpreter_dev/lib/python3.10/site-packages/PyPDF2/_utils.py\", line 351, in deprecation\nraise DeprecationError(msg)\nPyPDF2.errors.DeprecationError: PdfFileReader is deprecated and was removed in PyPDF2 3.0.0. Use PdfReader instead."
    },
    {
      "role": "assistant",
      "content": "It seems that the `PdfFileReader` class has been deprecated in the version of PyPDF2 that we installed. We should use the `PdfReader` class instead. Let's modify the code and try again.",
      "function_call": {
        "name": "run_code",
        "arguments": "{\n  \"language\": \"python\",\n  \"code\": \"from PyPDF2 import PdfReader\\n\\n# Open the PDF file\\npdf_path = '/Users/gongjunmin/Downloads/creator.pdf'\\npdf = PdfReader(pdf_path)\\n\\n# Check the number of pages in the PDF\\nnum_pages = len(pdf.pages)\\nnum_pages\"\n}",
        "parsed_arguments": {
          "language": "python",
          "code": "from PyPDF2 import PdfReader\n\n# Open the PDF file\npdf_path = '/Users/gongjunmin/Downloads/creator.pdf'\npdf = PdfReader(pdf_path)\n\n# Check the number of pages in the PDF\nnum_pages = len(pdf.pages)\nnum_pages"
        }
      }
    },
    {
      "role": "function",
      "name": "run_code",
      "content": "14"
    },
    {
      "role": "assistant",
      "content": "The PDF file has 14 pages. Now, let's proceed to the next step: extracting pages 2 to 5. \n\nPlease note that page numbers in PyPDF2 are zero-indexed, so pages 2 to 5 correspond to indices 1 to 4 in the code.",
      "function_call": {
        "name": "run_code",
        "arguments": "{\n  \"language\": \"python\",\n  \"code\": \"from PyPDF2 import PdfWriter\\n\\n# Create a PdfWriter object\\nwriter = PdfWriter()\\n\\n# Add pages 2 to 5 to the writer\\nfor i in range(1, 5):\\n    writer.add_page(pdf.pages[i])\\n\\n# Check the number of pages added to the writer\\nnum_pages_added = len(writer.pages)\\nnum_pages_added\"\n}",
        "parsed_arguments": {
          "language": "python",
          "code": "from PyPDF2 import PdfWriter\n\n# Create a PdfWriter object\nwriter = PdfWriter()\n\n# Add pages 2 to 5 to the writer\nfor i in range(1, 5):\n    writer.add_page(pdf.pages[i])\n\n# Check the number of pages added to the writer\nnum_pages_added = len(writer.pages)\nnum_pages_added"
        }
      }
    },
    {
      "role": "function",
      "name": "run_code",
      "content": "Output truncated. Showing the last 2000 characters.\n\n360142800), IndirectObject(98, 0, 4360142800), IndirectObject(99, 0, 4360142800), IndirectObject(100, 0, 4360142800), IndirectObject(101, 0, 4360142800), IndirectObject(102, 0, 4360142800), IndirectObject(103, 0, 4360142800), IndirectObject(104, 0, 4360142800), IndirectObject(105, 0, 4360142800), IndirectObject(106, 0, 4360142800), IndirectObject(107, 0, 4360142800), IndirectObject(108, 0, 4360142800), IndirectObject(109, 0, 4360142800), IndirectObject(110, 0, 4360142800), IndirectObject(111, 0, 4360142800), IndirectObject(112, 0, 4360142800), IndirectObject(113, 0, 4360142800), IndirectObject(114, 0, 4360142800), IndirectObject(115, 0, 4360142800), IndirectObject(116, 0, 4360142800), IndirectObject(117, 0, 4360142800), IndirectObject(118, 0, 4360142800), IndirectObject(119, 0, 4360142800), IndirectObject(120, 0, 4360142800), IndirectObject(121, 0, 4360142800), IndirectObject(122, 0, 4360142800), IndirectObject(123, 0, 4360142800), IndirectObject(124, 0, 4360142800), IndirectObject(125, 0, 4360142800), IndirectObject(126, 0, 4360142800), IndirectObject(127, 0, 4360142800), IndirectObject(128, 0, 4360142800), IndirectObject(129, 0, 4360142800), IndirectObject(130, 0, 4360142800), IndirectObject(131, 0, 4360142800)], '/Contents': IndirectObject(132, 0, 4360142800), '/MediaBox': [0, 0, 595.276, 841.89], '/Resources': IndirectObject(133, 0, 4360142800), '/Parent': IndirectObject(1, 0, 4360142800)}\n{'/Type': '/Page', '/Annots': [IndirectObject(135, 0, 4360142800), IndirectObject(136, 0, 4360142800)], '/Contents': IndirectObject(137, 0, 4360142800), '/Group': IndirectObject(138, 0, 4360142800), '/MediaBox': [0, 0, 595.276, 841.89], '/Resources': IndirectObject(139, 0, 4360142800), '/Parent': IndirectObject(1, 0, 4360142800)}\n{'/Type': '/Page', '/Annots': [IndirectObject(238, 0, 4360142800)], '/Contents': IndirectObject(239, 0, 4360142800), '/MediaBox': [0, 0, 595.276, 841.89], '/Resources': IndirectObject(240, 0, 4360142800), '/Parent': IndirectObject(1, 0, 4360142800)}\n4"
    },
    {
      "role": "assistant",
      "content": "Great, we have successfully added 4 pages (pages 2 to 5) to the writer. \n\nNow, let's proceed to the next step: saving the extracted pages as a new PDF file. We'll name the new file \"extracted_pages.pdf\".",
      "function_call": {
        "name": "run_code",
        "arguments": "{\n  \"language\": \"python\",\n  \"code\": \"output_pdf_path = '/Users/gongjunmin/Downloads/extracted_pages.pdf'\\n\\n# Write the pages to a new PDF file\\nwith open(output_pdf_path, 'wb') as output_pdf:\\n    writer.write(output_pdf)\\n\\noutput_pdf_path\"\n}",
        "parsed_arguments": {
          "language": "python",
          "code": "output_pdf_path = '/Users/gongjunmin/Downloads/extracted_pages.pdf'\n\n# Write the pages to a new PDF file\nwith open(output_pdf_path, 'wb') as output_pdf:\n    writer.write(output_pdf)\n\noutput_pdf_path"
        }
      }
    },
    {
      "role": "function",
      "name": "run_code",
      "content": "(False, <_io.BufferedWriter name='/Users/gongjunmin/Downloads/extracted_pages.pdf'>)\n'/Users/gongjunmin/Downloads/extracted_pages.pdf'"
    },
    {
      "role": "assistant",
      "content": "The extracted pages have been successfully saved as a new PDF file at `/Users/gongjunmin/Downloads/extracted_pages.pdf`.\n\nYou can now open this file to view the extracted pages. Let me know if you need further assistance."
    }
  ]
}


def test_skill_extractor_save_skill():
    interpreter.reset()
    interpreter.load(skill_obj["conversation_history"])
    interpreter.chat("%save_skill ./skill_library")


def test_skill_extractor_load_skill():
    interpreter.reset()
    interpreter.chat("%load_skill ./skill_library/extract_pdf_pages.json")
