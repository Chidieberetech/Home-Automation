# Garage Door Control System

This project implements a smart garage door control system with multiple input methods, cloud integration, and a real-time simulator.

## System Overview

The garage door control system provides multiple ways to control your garage door:
- License plate recognition via camera (using AWS Rekognition)
- Voice commands (using speech recognition)
- Remote control via MQTT messages
- Manual control through the PyGame-based simulator

The system consists of two main components:
1. **Main Controller** (`garage_system.py`) - The core system that processes inputs and controls the door
2. **Simulator** (`garage_simulator.py`) - A visual representation of the garage door with real-time status updates

## Key Features

- **Multi-Modal Control**:
  - Automatic license plate recognition using AWS Rekognition
  - Voice command processing with speech recognition
  - Remote control via AWS IoT Core MQTT
  - Manual control in PyGame simulator

- **Security**:
  - Token-based authentication for all commands
  - AWS Rekognition for secure plate recognition
  - DynamoDB for authorized plates storage
  - TLS encryption for MQTT communication

- **Cloud Integration**:
  - AWS IoT Core for MQTT communication
  - AWS Rekognition for license plate recognition
  - DynamoDB for authorized plates database
  - Support for both AWS IoT SDK and paho-mqtt fallback

- **Real-time Visualization**:
  - PyGame-based simulator with smooth animations
  - Real-time door position updates
  - Connection status monitoring
  - Camera preview toggle

## Prerequisites

### Hardware Requirements
- Computer with webcam (tested with Logitech C720)
- Microphone for voice commands
- Internet connection for AWS services

### Software Requirements
- Python 3.8 or higher
- Windows, macOS, or Linux
- AWS account with IoT Core, Rekognition, and DynamoDB access

### AWS Services Setup
- **AWS IoT Core**: For MQTT communication
- **AWS Rekognition**: For license plate recognition
- **DynamoDB**: Table named "AuthorizedPlates" for storing authorized license plates
- **IAM**: Proper permissions for IoT, Rekognition, and DynamoDB

## Installation

### 1. Clone or Download the Project
```bash
git clone https://github.com/Chidieberetech/Home-Automation.git
cd House-Automation
```

### 2. Install Python Dependencies
```bash
pip install -r requirements.txt
```

### 3. AWS IoT Core Setup
1. Create an IoT Thing in AWS IoT Core
2. Download the certificates:
   - Root CA certificate (save as `root-CA.crt`)
   - Device certificate (save as `GarageController.cert.pem`)
   - Private key (save as `GarageController.private.key`)
3. Create and attach an IoT policy with necessary permissions

### 4. Configure AWS Credentials
Update `garage_config.py` with your AWS configuration:
```python
# AWS Credentials
AWS_ACCESS_KEY_ID = "access-key-id"
AWS_SECRET_ACCESS_KEY = "secret-access-key"
AWS_REGION = "aws-region"

# IoT Core Configuration
IOT_ENDPOINT = "iot-endpoint.iot.region.amazonaws.com"

# Security Configuration
SECRET_TOKEN = "Random-secure-token"

# DynamoDB Configuration
AUTHORIZED_PLATES_TABLE = "DynmoDB Table Name"
```

### 5. Set Up DynamoDB Table
Create a DynamoDB table named "AuthorizedPlates" with:
- Primary key: `plate_number` (String)
- Add authorized license plates to this table

## Running the System

### Option 1: Using PowerShell Script (Windows)
```powershell
# Set execution policy if needed
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process
.\start.ps1
```

### Option 2: Direct Python Execution
```bash
# Start the main controller (automatically launches simulator)
python garage_system.py

# Or start simulator separately
python garage_simulator.py
```

## System Controls

### Main Controller Interface
- **`p`** - Toggle camera preview window
- **`q`** - Quit the application safely

### Simulator Controls
- **`O`** - Manually open garage door
- **`C`** - Manually close garage door
- **`ESC`** - Exit simulator
- **Mouse clicks** - Interactive control

### Voice Commands
The system recognizes natural language commands:
- "Open garage" / "Open the garage"
- "Close garage" / "Close the garage" / "Shut garage"

### License Plate Recognition
- System automatically captures and analyzes license plates
- Compares against authorized plates in DynamoDB
- Opens door automatically for authorized plates

## MQTT Integration

### Topics
- **Subscribe**: `garage/control` - Receives remote commands
- **Publish**: `garage/state` - Sends door status updates

### Message Format
Control messages:
```json
{
  "command": "open" | "close",
  "token": "security-token"
}
```

Status messages:
```json
{
  "door_open": true | false,
  "timestamp": "2025-07-19T10:30:00Z"
}
```

## Project Structure

```
House-Automation/
├── garage_system.py           # Main controller
├── garage_simulator.py        # PyGame simulator
├── garage_config.py          # AWS configuration
├── requirements.txt          # Python dependencies
├── start.ps1                # PowerShell startup script
├── README.md                # This file
├── root-CA.crt             # AWS root certificate
├── GarageController.cert.pem # Device certificate
├── GarageController.private.key # Private key
└── aws-iot-device-sdk-python-v2/ # AWS IoT SDK
```

## Security Considerations

1. **Credentials Security**: Never commit AWS credentials to version control
2. **Token Authentication**: All MQTT commands require valid security token
3. **TLS Encryption**: All AWS communications use TLS 1.2+
4. **Certificate Management**: Keep IoT certificates secure and rotate regularly
5. **IAM Permissions**: Use principle of least privilege for AWS IAM roles

## Troubleshooting

### Common Issues

**Camera Not Working**:
- Ensure camera is connected and not used by other applications
- Check camera permissions in system settings
- Try different USB ports or cameras

**MQTT Connection Failed**:
- Verify certificate files exist and are named correctly
- Check AWS IoT endpoint URL in configuration
- Ensure IoT policy allows to connect, publish, and subscribe permissions
- Check internet connectivity

**Voice Recognition Issues**:
- Ensure microphone is connected and working
- Reduce background noise
- Speak clearly and close to microphone
- Check audio input permissions

**AWS Service Errors**:
- Verify AWS credentials are correct and have necessary permissions
- Check DynamoDB table exists and is accessible
- Ensure Rekognition service is available in your region

### Debug Mode
Both components output detailed logs to console. Monitor these for error messages and connection status.

## Architecture Overview

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Camera Input  │───▶│                  │───▶│  AWS Rekognition│
└─────────────────┘    │                  │    └─────────────────┘
                       │                  │              │
┌─────────────────┐    │                  │              ▼
│   Voice Input   │───▶│  Main Controller │    ┌─────────────────┐
└─────────────────┘    │  (garage_system) │───▶│    DynamoDB     │
                       │                  │    └─────────────────┘
┌─────────────────┐    │                  │              │
│ MQTT Commands   │───▶│                  │              ▼
└─────────────────┘    └──────────┬───────┘    ┌──────────────────┐
                                  │            │   Simulator      │
                                  │            │(garage_simulator)│
                                  └───────────▶└──────────────────┘
```

## Dependencies

Key Python packages used:
- `opencv-python` - Camera capture and image processing
- `boto3` - AWS SDK for Python
- `pygame` - Simulator graphics and interface
- `speech_recognition` - Voice command processing
- `paho-mqtt` / `awsiot` - MQTT communication
- `pyaudio` - Audio input for voice recognition

## License

This project is open source. Please ensure you comply with AWS service terms and any applicable licenses for dependencies.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

For issues or questions, please open an issue in the repository.
