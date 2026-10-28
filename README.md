# 🌿 AgriTech – AI-Powered Plant Disease Detection System

[![Python](https://img.shields.io/badge/Python-3.9+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-2.0+-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![TensorFlow](https://img.shields.io/badge/TensorFlow-2.12+-FF6F00?style=for-the-badge&logo=tensorflow&logoColor=white)](https://www.tensorflow.org/)
[![Gemini AI](https://img.shields.io/badge/Gemini_AI-Flash-4285F4?style=for-the-badge&logo=google-gemini&logoColor=white)](https://ai.google.dev/)

AgriTech is a professional AI-driven platform designed to empower farmers and gardeners with real-time plant disease diagnosis. By combining **Deep Learning (EfficientNet/MobileNet)** for image recognition and **Generative AI (Google Gemini)** for expert agricultural advice, AgriTech bridge the gap between technology and traditional farming.

---

## ✨ Key Features

*   **🔍 AI Diagnosis**: Instant identification of 15+ plant disease classes using custom-trained CNN models.
*   **🤖 Expert Recommendations**: Integration with **Google Gemini AI** to provide detailed causes, cures, and farmer-specific recommendations.
*   **🔐 Unified User Portal**: Secure authentication system with dashboard for tracking detection history and personal analytics.
*   **📊 Insights & Analytics**: Real-time trends of detected diseases and user feedback visualization.
*   **📱 Responsive Interface**: A modern, leaf-green themed UI optimized for both desktop and mobile users.
*   **🛡️ History & Tracking**: Persistent storage of past detections with confidence scores and original images.

---

## 🛠 Tech Stack

### Backend & AI
*   **Core**: Python (Flask)
*   **Deep Learning**: Keras / TensorFlow (MobileNetV2 based Transfer Learning)
*   **Generative AI**: Google Gemini Pro API
*   **Database**: SQLite3 for User Management and History

### Frontend
*   **Templating**: Jinja2
*   **Styling**: Modern CSS (Glassmorphism & Interactive elements)
*   **Communication**: Fetch API / REST JSON Endpoints

---

## 📁 Project Structure

```text
Agri_Tech/
├── app.py                     # Main application entry point & API routes
├── plant_disease_model_v5.h5  # Trained Deep Learning model weights
├── class_indices_v5.json      # Mapping of model indices to disease names
├── static/                    # CS assets and uploaded media
│   ├── style.css              # Global styling
│   └── uploads/               # User-uploaded leaf images (Ignored in Git)
├── templates/                 # UI components and layouts
│   ├── index.html             # Landing Page
│   ├── Agri_tech.html         # Detection Hub
│   └── dashboard.html         # User Analytics
├── .env.example               # Example environment configuration
├── trained_model.ipynb        # Model training and evaluation notebook
└── requirements.txt           # Dependency manifest
```

---

## ⚙️ Quick Start

### 1. Prerequisites
*   Python 3.9 or higher
*   Google Gemini API Key ([Get it here](https://aistudio.google.com/app/apikey))

### 2. Installation
```bash
# Clone the repository
git clone https://github.com/B-koushik-09/agritech.git
cd Agri_Tech

# Set up virtual environment
python -m venv venv
source venv/bin/activate  # venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Configuration
Create a `.env` file in the root directory (this file is ignored by Git for security):
```env
GEMINI_API_KEY=your_actual_api_key_here
SECRET_KEY=any_random_string_for_sessions
```

### 4. Database Setup
The application uses SQLite. The `users.db` file will be generated automatically in the root directory on the first launch (Ignored in Git).

### 5. Launch
```bash
python app.py
```
Visit `http://127.0.0.1:5050` to start using the app.

## Optional ESP32-CAM Prototype

The low-cost camera prototype uses an **AI Thinker ESP32-CAM with OV2640 camera**, a **0.96-inch SSD1306 I2C OLED (128x64)**, jumper wires, and USB power/programming. The ESP32-CAM captures a leaf image and sends it to the existing Flask `/predict` route. The computer runs the TensorFlow model and returns the disease name and confidence; the ESP32 displays that result. The model is not run on the microcontroller.

### Wiring

| OLED pin | ESP32-CAM AI Thinker pin |
|---|---|
| VCC | 3V3 |
| GND | GND |
| SDA | GPIO 13 |
| SCL | GPIO 14 |

Do not insert a microSD card; GPIO 13 and 14 are shared with the SD interface. The camera is already connected on the ESP32-CAM board. Use an ESP32-CAM-MB USB programmer or a USB-to-serial adapter with 3.3V UART logic. A stable 5V supply is recommended.

### Setup

1. Install Arduino IDE 2, ESP32 board support, **Adafruit SSD1306**, **Adafruit GFX**, and **ArduinoJson** libraries.
2. Start AgriTech on the computer connected to the same Wi-Fi network. Find its private IPv4 address with `ipconfig`; the app listens on port `5050`.
3. In `hardware/esp32_cam_oled.ino`, set `WIFI_SSID`, `WIFI_PASSWORD`, and `SERVER_URL` to `http://<computer-ip>:5050/predict`.
4. Select **AI Thinker ESP32-CAM** in Arduino IDE. Upload the sketch, then open Serial Monitor at `115200` baud.
5. Point the camera at one supported crop leaf. It captures and analyzes an image every 30 seconds; the OLED shows the predicted disease and confidence.

The computer firewall must allow private-network traffic on port `5050`. This prototype uses plain HTTP and the prediction route is not device-authenticated, so keep it on a trusted local network and do not expose it publicly. The ESP32 requires the Flask computer to run the model; it cannot diagnose images when disconnected from that server.

---

## 🧠 Model Information
The system uses a **MobileNetV2** architecture fine-tuned on the **PlantVillage** dataset. It currently supports detection for:
*   **Tomato**: Bacterial Spot, Early Blight, Late Blight, Leaf Mold, etc.
*   **Potato**: Early Blight, Late Blight, Healthy.
*   **Pepper**: Bacterial Spot, Healthy.

---

## 🤝 Contributing
Contributions are what make the open source community such an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**.

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

