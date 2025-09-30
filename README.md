# Museum Catalog Description Generator

This project is designed to automatically generate professional museum catalog descriptions for objects using AI. It processes images and metadata to create detailed, academic-style descriptions following museum documentation standards.

## Features

- Processes multiple images per museum object
- Generates structured catalog entries with consistent formatting
- Supports various image formats (JPG, PNG, TIFF, BMP)
- Handles batch processing of multiple objects
- Includes error handling and logging
- Configurable settings for image processing and API usage

## Prerequisites

- Python 3.8 or higher
- OpenAI API key
- Required Python packages (see Installation)

## Installation

1. Clone this repository
2. Install the required packages:
   ```bash
   pip install -r requirements.txt
   ```
3. Create a `.env` file in the project root with your OpenAI API key:
   ```
   OPENAI_API_KEY=your_api_key_here
   ```

## Project Structure

```
.
├── images/                  # Directory containing object images
│   └── 2025/               # Year-based subdirectories
├── output/
│   ├── aeg/                 # Processed AEG object data
│   ├── descriptions/        # Generated descriptions
│   └── logs/                # Log files for processing
├── scripts/
│   ├── automatic_description_Hier.py  # Main script for description generation
│   ├── chatapi_Bild_und_Text.py       # API integration for image+text processing
│   └── copy_images_from_excel.py      # Utility for processing image data from Excel
├── .env                    # Environment variables (not in version control)
└── requirements.txt        # Python dependencies
```

## Usage

1. Place your object images in the appropriate subdirectories under `images/`
2. Run the main script:
   ```bash
   python scripts/automatic_description_Hier.py
   ```
3. Generated descriptions will be saved in `output/descriptions/descriptions.xlsx`

## Configuration

You can modify the following settings in `automatic_description_Hier.py`:
- `INPUT_DIRS`: Directories to scan for object images
- `MAX_IMAGES_PER_OBJECT`: Maximum number of images to process per object
- `RESIZE_MAX_SIDE`: Maximum dimension for image resizing (in pixels)
- `REQUEST_COOLDOWN_SEC`: Delay between API requests (to avoid rate limiting)
- `PROMPT`: Customize the AI prompt for description generation

## Output

The system generates an Excel file (`descriptions.xlsx`) containing:
- Object IDs
- Generated descriptions
- Source information
- Technical details
- Historical context
- Conservation notes
- Exhibition history
- Bibliography

## Logging

Log files are created in the `output/logs/` directory to track:
- Successfully processed objects
- Any errors or issues encountered
- API usage and response times

## Notes

- The system is designed to be conservative with API usage to minimize costs
- All generated content should be reviewed by a professional before publication
- The system marks uncertain information and assumptions clearly in the output

## License

This project is licensed under the MIT License - see the LICENSE file for details.
