# 📧 KemisEmail Campaign Creator

A professional email campaign generator that creates beautiful, Bahamian-themed email templates for Sendy integration. Built with AI-powered content generation and image creation.

## ✨ Features

- **🤖 AI Content Generation**: Creates engaging email content with Bahamian tone and local references
- **🖼️ AI Image Generation**: Generates custom images using DALL-E 3
- **📤 Sendy Integration**: Direct integration with Sendy for campaign creation
- **🔧 Image Resizer**: Built-in image optimization to prevent large file sizes
- **🎨 Dark Theme UI**: Modern, Sendy-inspired dark interface
- **📱 Responsive Design**: Works on desktop and mobile devices
- **🔗 Custom CTA Links**: Support for custom call-to-action URLs

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- OpenAI API key
- Sendy installation

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/salutethegenius/kemisemail-template-generator.git
   cd kemisemail-template-generator
   ```

2. **Create virtual environment**
   ```bash
   python -m venv kemis_env
   source kemis_env/bin/activate  # On Windows: kemis_env\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   Create a `.env` file in the root directory:
   ```env
   OPENAI_API_KEY=your_openai_api_key_here
   ```

5. **Run the application**
   ```bash
   python template_generator.py
   ```

6. **Access the application**
   Open your browser and go to: `http://localhost:5000`

## 🎯 How to Use

### 1. Create a Campaign
- Enter your campaign description in the text area
- Choose image option: AI-generated, upload your own, or no image
- Optionally add a custom CTA link
- Click "Generate Template"

### 2. Image Options
- **AI Generated**: Let AI create a custom image for your campaign
- **Upload Your Own**: Upload and resize your own image
- **No Image**: Create text-only campaigns

### 3. Image Resizer
- Adjust width (200px - 800px)
- Control quality (20% - 90%)
- Real-time size preview
- Automatic optimization

### 4. Send to Sendy
- Preview your generated template
- Click "Create Campaign in Sendy"
- Campaign is created as a draft in Sendy

## 🏗️ Architecture

### Core Components

- **`template_generator.py`**: Main Flask application
- **`templates/index.html`**: Frontend interface
- **OpenAI Integration**: GPT-4 for content, DALL-E 3 for images
- **Sendy API**: Campaign creation and management

### Key Features

- **Content Generation**: Bahamian-themed email content
- **Image Processing**: Automatic resizing and optimization
- **Sendy Integration**: Direct campaign creation
- **Dark Theme UI**: Modern, professional interface

## 🔧 Configuration

### Environment Variables

```env
OPENAI_API_KEY=your_openai_api_key_here
```

### Sendy Configuration

Update the Sendy settings in `template_generator.py`:

```python
SENDY_API_KEY = 'your_sendy_api_key'
sendy_url = "https://your-domain.com/sendy/api/campaigns/create.php"
list_ids = 'your_list_ids'
brand_id = 'your_brand_id'
```

## 📁 Project Structure

```
kemisemail-template-generator/
├── template_generator.py      # Main application
├── templates/
│   └── index.html            # Frontend interface
├── requirements.txt           # Python dependencies
├── README.md                 # This file
└── .env                      # Environment variables (create this)
```

## 🎨 UI Features

### Dark Theme Design
- Modern dark interface inspired by Sendy
- Professional color scheme
- Responsive design
- Smooth animations

### Interactive Elements
- Real-time image resizer
- Dynamic status loader
- Tabbed content preview
- Progress indicators

## 🔗 Sendy Integration

### Campaign Creation
- Automatic campaign naming with date
- HTML and plain text versions
- Custom CTA links
- Image optimization

### API Endpoints
- Campaign creation
- List management
- Brand configuration

## 🛠️ Development

### Running in Development Mode
```bash
python template_generator.py
```

### File Structure
- Generated templates are saved locally
- Images are optimized automatically
- Logs show generation progress

## 📊 Features Overview

| Feature | Description |
|---------|-------------|
| AI Content | GPT-4 powered email content generation |
| AI Images | DALL-E 3 custom image creation |
| Sendy Integration | Direct campaign creation |
| Image Resizer | Built-in optimization tools |
| Dark Theme | Modern, professional UI |
| Responsive | Works on all devices |

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License.

## 🆘 Support

For support, please contact the development team or create an issue on GitHub.

---

**Built with ❤️ for KemisEmail** 