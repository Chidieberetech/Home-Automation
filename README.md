# Garage Door Control System

This project implements a smart garage door control system with multiple input methods, cloud integration, and a real-time simulator.

## System Overview

The garage door control system provides multiple ways to control your garage door:
- License plate recognition via camera
- Voice commands
- Remote control via MQTT messages
- Manual control through the simulator

The system consists of two main components:
1. **Main Controller** - The core system that processes inputs and controls the door
2. **Simulator** - A visual representation of the garage door with real-time status updates

## Key Features

- **Multi-Modal Control**:
  - Automatic license plate recognition
  - Voice command processing
  - Remote control via MQTT
  - Manual control in simulator

- **Security**:
  - Token-based authentication
  - AWS Rekognition for plate recognition
  - DynamoDB for authorized plates storage

- **Cloud Integration**:
  - AWS IoT Core for MQTT communication
  - AWS Rekognition for license plate recognition
  - DynamoDB for authorized plates database

- **Real-time Visualization**:
  - PyGame-based simulator
  - Smooth door animation
  - Connection status monitoring

## Prerequisites

1. **Hardware**:
   - Raspberry Pi or similar device
   - Logitech C720 webcam (or compatible)
   - Microphone for voice commands

2. **Software**:
   - Python 3.8+
   - Required Python packages (install via `pip install -r requirements.txt`)

3. **AWS Services**:
   - AWS IoT Core (for MQTT communication)
   - AWS Rekognition (for license plate recognition)
   - DynamoDB (for authorized plates storage)

4. **Security Certificates**:
   - AWS IoT certificates (`root-CA.crt`, `certificate.pem.crt`, `private.pem.key`)

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/garage-control-system.git
   cd garage-control-system
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure AWS credentials:
   - Create a `garage_config.py` file with your AWS credentials:
     ```python
     # AWS Credentials
     AWS_ACCESS_KEY_ID = 'your-access-key'
     AWS_SECRET_ACCESS_KEY = 'your-secret-key'
     AWS_REGION = 'your-region'
     
     # IoT Core Endpoint
     IOT_ENDPOINT = 'your-iot-endpoint'
     
     # Security Token
     SECRET_TOKEN = 'your-secure-token'
     
     # DynamoDB Table
     AUTHORIZED_PLATES_TABLE = 'AuthorizedPlates'
     ```

4. Place your AWS IoT certificates in the project directory:
   - `root-CA.crt`
   - `certificate.pem.crt`
   - `private.pem.key`

## Running the System

### Starting the Main Controller
```bash
python garage_controller.py
```

### Starting the Simulator (automatically launched by controller)
```bash
python garage_simulator.py
```

The controller will automatically launch the simulator. Both components can also be run separately for testing.

## System Controls

### Main Controller Controls
- **`p`** - Toggle camera preview
- **`q`** - Quit the application

### Simulator Controls
- **`O`** - Open garage door
- **`C`** - Close garage door
- **`ESC`** - Exit simulator

## Voice Commands
The system responds to natural language commands:
- "Open garage"
- "Close garage"
- "Shut garage"

## MQTT Integration
The system uses MQTT for communication:
- **Subscribes to**: `garage/control`
- **Publishes to**: `garage/state`

### Message Format
```json
{
  "command": "open/close",
  "token": "your-secure-token"
}
```

## Security Considerations

1. **Token Authentication**: All commands require a valid security token
2. **TLS Encryption**: MQTT communication uses TLS 1.2 encryption
3. **Limited Permissions**: AWS credentials should have only necessary permissions
4. **Secure Storage**: Secrets should be stored in environment variables or secure config files

## Troubleshooting

### Common Issues
1. **Camera not detected**:
   - Ensure camera is properly connected
   - Try different USB ports
   - Check camera permissions

2. **MQTT Connection Issues**:
   - Verify certificate files exist
   - Check AWS IoT policy permissions
   - Ensure correct endpoint in configuration

3. **Voice Recognition Problems**:
   - Check microphone connection
   - Reduce background noise
   - Speak clearly and close to microphone

### Logging
Both components output detailed logs to console for debugging purposes.

## Architecture Diagram

```
+----------------+     +-----------------+     +-------------+
|                |     |                 |     |             |
|  Camera Input  +---->+                 |     |  AWS        |
|                |     |                 +---->+  Rekognition|
+----------------+     |                 |     |             |
                       |                 |     +-------------+
+----------------+     |                 |           |
|                |     |                 |           v
|  Voice Input   +---->+  Main Controller+     +-------------+
|                |     |                 +---->+  DynamoDB   |
+----------------+     |                 |     |             |
                       |                 |     +-------------+
+----------------+     |                 |           |
|                |     |                 |           v
|  MQTT Messages +---->+                 |     +-------------+
|                |     |                 +---->+  Simulator  |
+----------------+     +--------+--------+     |             |
                                |              +-------------+
                                |                    ^
                                |                    |
                                +--------------------+
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.