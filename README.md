# Museum Catalog Description Generator

Welcome to the Museum Catalog Description Generator! This tool helps you create professional, detailed descriptions for museum objects using artificial intelligence. Whether you're a museum professional, archivist, or art enthusiast, this tool simplifies the process of cataloging your collection.

## 🚀 Getting Started

### What You'll Need
- A computer with Python 3.8 or higher installed
- An OpenAI API key (get one at [OpenAI's website](https://platform.openai.com/))
- Your collection images ready to be processed

### Quick Setup
1. **Install Python** if you haven't already (download from [python.org](https://www.python.org/downloads/))
2. **Download this project** to your computer
3. **Install requirements** by opening a terminal in the project folder and running:
   ```bash
   pip install -r requirements.txt
   ```
4. **Set up your API key** by creating a file named `.env` in the project folder with this line:
   ```
   OPENAI_API_KEY=your_api_key_here
   ```
   (Replace `your_api_key_here` with your actual OpenAI API key)

## 📂 Preparing Your Images

1. Create a folder named `images` in the project folder if it doesn't exist
2. Inside `images`, create subfolders by year (e.g., `1997`, `1998`, etc.)
3. Place your object images in these year folders
   - Supported formats: JPG, PNG, TIFF, BMP
   - Name your files clearly (e.g., `object123_front.jpg`, `object123_back.jpg`)

## 🔄 How to Use the Tool

This project consists of three main scripts that you'll use in order:

### 1. Organize Your Images
```bash
python scripts/copy_RelevantImages.py
```
This script helps you organize and prepare your images for processing.

### 2. Generate Descriptions
```bash
python scripts/autoOpenAiDescription.py
```
Run this script to generate descriptions for your objects. You can run this multiple times to generate more descriptions.

### 3. Build Your Website
When you're happy with the descriptions and have enough content:
```bash
python scripts/build_site.py
```
This will create a website with your collection catalog.

## 📊 Understanding the Output

After running the description generator, you'll find:
- **Generated descriptions** in the `output/descriptions/` folder
- **Log files** in `output/logs/` to track what was processed
- **Final website** in the `build/` directory after running the build script

## 💡 Tips for Best Results
- **Start small**: Try with a few images first to see how it works
- **Review the output**: AI is powerful but not perfect - always review the generated content
- **Organize your files**: Keep your images well-organized in year folders
- **Be patient**: Processing many images might take some time

## ❓ Need Help?

If you run into any issues:
1. Check the `output/logs/` folder for error messages
2. Make sure your API key is correctly set in the `.env` file
3. Ensure your images are in the correct format and location

## 📄 License

This project is open source and available under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Credits

Created with ❤️ for museum professionals and collection managers. We hope this tool makes your cataloging work easier and more efficient!